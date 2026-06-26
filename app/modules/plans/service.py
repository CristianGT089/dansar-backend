import uuid

from sqlalchemy import select
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.plans.models import (
    CompanyFeature,
    CompanyPlan,
    Feature,
    Plan,
    PlanType,
)
from app.modules.plans.schemas import FeatureStatus, SubFeatureStatus
from app.modules.users.models import SystemRole
from app.shared.exceptions import ConflictError, ForbiddenError, NotFoundError, ValidationError


async def list_plans(db: AsyncSession) -> list[Plan]:
    result = await db.execute(select(Plan).where(Plan.is_active == True))
    return result.scalars().all()


async def list_features(db: AsyncSession) -> list[Feature]:
    result = await db.execute(select(Feature))
    return result.scalars().all()


async def create_feature(db: AsyncSession, key: str, name: str, description: str | None, module: str | None, parent_key: str | None = None) -> Feature:
    existing = await db.execute(select(Feature).where(Feature.key == key))
    if existing.scalar_one_or_none():
        raise ConflictError(f"Feature '{key}' ya existe")

    if parent_key:
        parent = await db.execute(select(Feature).where(Feature.key == parent_key))
        if not parent.scalar_one_or_none():
            raise NotFoundError(f"Feature padre '{parent_key}' no existe")

    feature = Feature(key=key, name=name, description=description, module=module, parent_key=parent_key)
    db.add(feature)
    await db.flush()
    await db.refresh(feature)
    return feature


async def get_company_features(db: AsyncSession, company_id: uuid.UUID) -> list[FeatureStatus]:
    # Load all features with their children
    all_features_result = await db.execute(
        select(Feature).where(Feature.parent_key == None)
    )
    parent_features = all_features_result.scalars().all()

    children_result = await db.execute(
        select(Feature).where(Feature.parent_key != None)
    )
    all_children = children_result.scalars().all()

    # Load company feature states
    cf_result = await db.execute(
        select(CompanyFeature).where(CompanyFeature.company_id == company_id)
    )
    cf_map: dict[uuid.UUID, CompanyFeature] = {cf.feature_id: cf for cf in cf_result.scalars().all()}

    children_by_parent: dict[str, list[Feature]] = {}
    for child in all_children:
        children_by_parent.setdefault(child.parent_key, []).append(child)

    result = []
    for parent in parent_features:
        parent_cf = cf_map.get(parent.id)
        children_status = []
        for child in children_by_parent.get(parent.key, []):
            child_cf = cf_map.get(child.id)
            children_status.append(SubFeatureStatus(
                feature_id=str(child.id),
                key=child.key,
                name=child.name,
                module=child.module,
                is_enabled=child_cf.is_enabled if child_cf else False,
                allowed_roles=child_cf.allowed_roles if child_cf else [],
            ))
        result.append(FeatureStatus(
            feature_id=str(parent.id),
            key=parent.key,
            name=parent.name,
            module=parent.module,
            is_enabled=parent_cf.is_enabled if parent_cf else False,
            children=children_status,
        ))

    return result


async def toggle_feature(
    db: AsyncSession, company_id: uuid.UUID, feature_key: str, enabled: bool
) -> dict:
    """Superadmin only — toggles any feature (parent or child)."""
    feature = await _get_feature_or_404(db, feature_key)

    cf = await _get_or_create_company_feature(db, company_id, feature.id)
    cf.is_enabled = enabled

    # When disabling a parent, disable all children too
    if not enabled and feature.parent_key is None:
        children_result = await db.execute(
            select(Feature).where(Feature.parent_key == feature_key)
        )
        for child in children_result.scalars().all():
            child_cf = await _get_or_create_company_feature(db, company_id, child.id)
            child_cf.is_enabled = False

    await db.flush()
    return {"feature_key": feature_key, "enabled": enabled}


async def toggle_subfeature(
    db: AsyncSession, company_id: uuid.UUID, feature_key: str, enabled: bool
) -> dict:
    """Admin or superadmin — only for subfeatures (has parent_key)."""
    feature = await _get_feature_or_404(db, feature_key)

    if feature.parent_key is None:
        raise ForbiddenError("Solo el superadmin puede activar funcionalidades principales")

    # Verify parent is enabled
    parent = await _get_feature_or_404(db, feature.parent_key)
    parent_cf_result = await db.execute(
        select(CompanyFeature).where(
            CompanyFeature.company_id == company_id,
            CompanyFeature.feature_id == parent.id,
        )
    )
    parent_cf = parent_cf_result.scalar_one_or_none()
    if not parent_cf or not parent_cf.is_enabled:
        raise ForbiddenError(f"La funcionalidad '{parent.name}' no está activa para esta empresa")

    cf = await _get_or_create_company_feature(db, company_id, feature.id)
    cf.is_enabled = enabled
    if enabled and not cf.allowed_roles:
        cf.allowed_roles = [SystemRole.admin.value]

    await db.flush()
    return {"feature_key": feature_key, "enabled": enabled, "allowed_roles": cf.allowed_roles}


async def set_feature_roles(
    db: AsyncSession, company_id: uuid.UUID, feature_key: str, roles: list[SystemRole]
) -> dict:
    """Admin or superadmin — sets which roles can access a subfeature."""
    feature = await _get_feature_or_404(db, feature_key)

    if feature.parent_key is None:
        raise ForbiddenError("Los roles solo se configuran en subfuncionalidades")

    valid_roles = [SystemRole.admin, SystemRole.contador, SystemRole.viewer]
    for role in roles:
        if role not in valid_roles:
            raise ValidationError(f"Rol inválido: {role}. Opciones: admin, contador, viewer")

    cf = await _get_or_create_company_feature(db, company_id, feature.id)
    cf.allowed_roles = [r.value for r in roles]

    await db.flush()
    return {"feature_key": feature_key, "allowed_roles": cf.allowed_roles}


async def check_feature_access(
    db: AsyncSession,
    company_id: uuid.UUID,
    feature_key: str,
    user_role: str,
) -> bool:
    """
    Returns True if the user's role has access to this feature.
    For subfeatures: checks parent is enabled + subfeature is enabled + role is in allowed_roles.
    For parent features: just checks is_enabled.
    Empty allowed_roles means no one has access.
    """
    feature_result = await db.execute(
        select(Feature)
        .where(Feature.key == feature_key)
        .options(selectinload(Feature.parent))
    )
    feature = feature_result.scalar_one_or_none()
    if not feature:
        raise NotFoundError(f"Feature '{feature_key}'")

    feature_ids = [feature.id]
    if feature.parent_key and feature.parent:
        feature_ids.append(feature.parent.id)

    cf_result = await db.execute(
        select(CompanyFeature).where(
            CompanyFeature.company_id == company_id,
            CompanyFeature.feature_id.in_(feature_ids),
        )
    )
    cf_map = {cf.feature_id: cf for cf in cf_result.scalars().all()}

    if feature.parent_key and feature.parent:
        parent_cf = cf_map.get(feature.parent.id)
        if not parent_cf or not parent_cf.is_enabled:
            return False

    cf = cf_map.get(feature.id)
    if not cf or not cf.is_enabled:
        return False

    if feature.parent_key:
        if not cf.allowed_roles:
            return False
        return user_role in cf.allowed_roles

    return True


# ── Helpers ───────────────────────────────────────────────────────────────────

async def _get_feature_or_404(db: AsyncSession, key: str) -> Feature:
    result = await db.execute(select(Feature).where(Feature.key == key))
    feature = result.scalar_one_or_none()
    if not feature:
        raise NotFoundError(f"Feature '{key}'")
    return feature


async def _get_or_create_company_feature(
    db: AsyncSession, company_id: uuid.UUID, feature_id: uuid.UUID
) -> CompanyFeature:
    result = await db.execute(
        select(CompanyFeature).where(
            CompanyFeature.company_id == company_id,
            CompanyFeature.feature_id == feature_id,
        )
    )
    cf = result.scalar_one_or_none()
    if not cf:
        cf = CompanyFeature(company_id=company_id, feature_id=feature_id, is_enabled=False, allowed_roles=[])
        db.add(cf)
        await db.flush()
    return cf


async def assign_plan_to_company(
    db: AsyncSession, company_id: uuid.UUID, plan_type: str
) -> CompanyPlan:
    if plan_type not in [p.value for p in PlanType]:
        raise ValidationError(f"Plan inválido. Opciones: {[p.value for p in PlanType]}")

    plan_result = await db.execute(select(Plan).where(Plan.type == plan_type))
    plan = plan_result.scalar_one_or_none()
    if not plan:
        raise NotFoundError("Plan")

    existing = await db.execute(
        select(CompanyPlan).where(CompanyPlan.company_id == company_id)
    )
    cp = existing.scalar_one_or_none()

    if cp:
        cp.plan_id = plan.id
        cp.is_active = True
    else:
        cp = CompanyPlan(company_id=company_id, plan_id=plan.id)
        db.add(cp)

    await db.flush()
    await db.refresh(cp)
    return cp
