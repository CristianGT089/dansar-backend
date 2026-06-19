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
from app.shared.exceptions import ConflictError, NotFoundError, ValidationError


async def list_plans(db: AsyncSession) -> list[Plan]:
    result = await db.execute(select(Plan).where(Plan.is_active == True))
    return result.scalars().all()


async def list_features(db: AsyncSession) -> list[Feature]:
    result = await db.execute(select(Feature))
    return result.scalars().all()


async def create_feature(db: AsyncSession, key: str, name: str, description: str | None, module: str | None) -> Feature:
    existing = await db.execute(select(Feature).where(Feature.key == key))
    if existing.scalar_one_or_none():
        raise ConflictError(f"Feature '{key}' ya existe")
    feature = Feature(key=key, name=name, description=description, module=module)
    db.add(feature)
    await db.flush()
    await db.refresh(feature)
    return feature


async def get_company_features(db: AsyncSession, company_id: uuid.UUID) -> list[dict]:
    all_features = await list_features(db)
    result = await db.execute(
        select(CompanyFeature).where(CompanyFeature.company_id == company_id)
    )
    enabled_map = {cf.feature_id: cf.is_enabled for cf in result.scalars().all()}
    return [
        {
            "feature_id": str(f.id),
            "key": f.key,
            "name": f.name,
            "module": f.module,
            "enabled": enabled_map.get(f.id, False),
        }
        for f in all_features
    ]


async def toggle_feature(
    db: AsyncSession, company_id: uuid.UUID, feature_key: str, enabled: bool
) -> dict:
    feature_result = await db.execute(select(Feature).where(Feature.key == feature_key))
    feature = feature_result.scalar_one_or_none()
    if not feature:
        raise NotFoundError("Feature")

    existing = await db.execute(
        select(CompanyFeature).where(
            CompanyFeature.company_id == company_id,
            CompanyFeature.feature_id == feature.id,
        )
    )
    cf = existing.scalar_one_or_none()

    if cf:
        cf.is_enabled = enabled
    else:
        cf = CompanyFeature(company_id=company_id, feature_id=feature.id, is_enabled=enabled)
        db.add(cf)

    await db.flush()
    return {"feature_key": feature_key, "enabled": enabled}


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
