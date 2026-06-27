import uuid

from sqlalchemy import select, text
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.catalog.models import (
    CompanyFeature,
    CompanyModule,
    Feature,
    Module,
    ModuleType,
)
from app.modules.catalog.schemas import FeatureNode
from app.modules.users.models import SystemRole
from app.shared.exceptions import ConflictError, ForbiddenError, NotFoundError, ValidationError


async def list_modules(db: AsyncSession) -> list[Module]:
    result = await db.execute(select(Module).where(Module.is_active == True))
    return result.scalars().all()


async def list_features(db: AsyncSession) -> list[Feature]:
    result = await db.execute(select(Feature))
    return result.scalars().all()


async def create_feature(
    db: AsyncSession,
    key: str,
    name: str,
    description: str | None,
    module: str | None,
    parent_key: str | None = None,
) -> Feature:
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


async def get_company_features(db: AsyncSession, company_id: uuid.UUID) -> list[FeatureNode]:
    """
    Devuelve el árbol de features con profundidad ilimitada.
    Usa una sola query para cargar todos los features y sus estados,
    luego construye el árbol en Python.
    """
    # Cargar todos los features
    all_features_result = await db.execute(select(Feature))
    all_features: list[Feature] = all_features_result.scalars().all()

    # Cargar estados de la empresa
    cf_result = await db.execute(
        select(CompanyFeature).where(CompanyFeature.company_id == company_id)
    )
    cf_map: dict[uuid.UUID, CompanyFeature] = {
        cf.feature_id: cf for cf in cf_result.scalars().all()
    }

    # Construir nodos indexados por key
    nodes: dict[str, FeatureNode] = {}
    for f in all_features:
        cf = cf_map.get(f.id)
        nodes[f.key] = FeatureNode(
            feature_id=str(f.id),
            key=f.key,
            name=f.name,
            module=f.module,
            is_enabled=cf.is_enabled if cf else False,
            allowed_roles=cf.allowed_roles if cf else [],
            children=[],
        )

    # Ensamblar árbol: asignar cada nodo a su padre
    roots: list[FeatureNode] = []
    for f in all_features:
        node = nodes[f.key]
        if f.parent_key is None:
            roots.append(node)
        elif f.parent_key in nodes:
            nodes[f.parent_key].children.append(node)

    return roots


async def toggle_feature(
    db: AsyncSession, company_id: uuid.UUID, feature_key: str, enabled: bool
) -> dict:
    feature = await _get_feature_or_404(db, feature_key)

    # Al habilitar un nodo no-raíz, el padre inmediato debe estar habilitado
    if enabled and feature.parent_key is not None:
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

    # Cascade a TODOS los descendientes
    descendant_keys = await _get_all_descendant_keys(db, feature_key)
    if descendant_keys:
        desc_result = await db.execute(
            select(Feature).where(Feature.key.in_(descendant_keys))
        )
        for desc in desc_result.scalars().all():
            desc_cf = await _get_or_create_company_feature(db, company_id, desc.id)
            desc_cf.is_enabled = enabled

    await db.flush()
    return {"feature_key": feature_key, "enabled": enabled}


async def toggle_subfeature(
    db: AsyncSession, company_id: uuid.UUID, feature_key: str, enabled: bool
) -> dict:
    """Para nodos no-raíz: verifica que el padre inmediato esté habilitado."""
    feature = await _get_feature_or_404(db, feature_key)

    if feature.parent_key is None:
        raise ForbiddenError("Solo el superadmin puede activar funcionalidades principales")

    # Verificar que el padre inmediato esté habilitado
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
    """Configura allowed_roles en cualquier nivel del árbol.

    En nodos no-raíz los roles deben ser subconjunto de los que el nodo raíz permite.
    Un nodo raíz con allowed_roles=[] significa acceso irrestricto por rol.
    """
    feature = await _get_feature_or_404(db, feature_key)

    valid_roles = {SystemRole.admin, SystemRole.contador, SystemRole.viewer}
    requested = set(roles)
    invalid = requested - valid_roles
    if invalid:
        raise ValidationError(f"Roles inválidos: {invalid}. Opciones: admin, contador, viewer")

    # Para nodos no-raíz: los roles deben ser subconjunto de los del nodo raíz
    if feature.parent_key is not None:
        root_key = await _get_root_key(db, feature_key)
        root_feature = await _get_feature_or_404(db, root_key)
        root_cf_result = await db.execute(
            select(CompanyFeature).where(
                CompanyFeature.company_id == company_id,
                CompanyFeature.feature_id == root_feature.id,
            )
        )
        root_cf = root_cf_result.scalar_one_or_none()
        root_roles = set(root_cf.allowed_roles) if root_cf and root_cf.allowed_roles else set()

        if root_roles:
            invalid_for_child = {r.value for r in requested} - root_roles
            if invalid_for_child:
                raise ValidationError(
                    f"Roles no permitidos por el nodo raíz '{root_key}': {invalid_for_child}"
                )

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
    Verifica acceso recorriendo el árbol desde la raíz hasta el nodo solicitado.
    Cualquier ancestro deshabilitado o con allowed_roles que excluya al rol bloquea el acceso.
    """
    feature_result = await db.execute(
        select(Feature).where(Feature.key == feature_key)
    )
    feature = feature_result.scalar_one_or_none()
    if not feature:
        raise NotFoundError(f"Feature '{feature_key}'")

    # Obtener la cadena completa de ancestros usando CTE recursivo
    ancestor_keys = await _get_ancestor_chain(db, feature_key)
    all_keys = ancestor_keys + [feature_key]

    cf_result = await db.execute(
        select(CompanyFeature)
        .join(Feature, CompanyFeature.feature_id == Feature.id)
        .where(
            CompanyFeature.company_id == company_id,
            Feature.key.in_(all_keys),
        )
    )
    cf_by_key: dict[str, CompanyFeature] = {}
    for cf in cf_result.scalars().all():
        feat_row = (await db.execute(select(Feature).where(Feature.id == cf.feature_id))).scalar_one()
        cf_by_key[feat_row.key] = cf

    for key in all_keys:
        cf = cf_by_key.get(key)
        if not cf or not cf.is_enabled:
            return False
        # Si el nodo tiene allowed_roles y no es la raíz, verificar rol
        if key != all_keys[0] or feature.parent_key is not None:
            if cf.allowed_roles and user_role not in cf.allowed_roles:
                return False

    return True


async def get_accessible_features(
    db: AsyncSession, company_id: uuid.UUID, user_role: str
) -> list[str]:
    """
    Devuelve las claves de features accesibles para un rol dado.
    Un nodo es accesible si:
    - Está habilitado
    - Su allowed_roles está vacío O contiene el rol del usuario
    - Todos sus ancestros también son accesibles
    """
    tree = await get_company_features(db, company_id)
    accessible: list[str] = []

    def traverse(nodes: list[FeatureNode], ancestor_blocked: bool = False) -> None:
        for node in nodes:
            if ancestor_blocked or not node.is_enabled:
                continue
            # Un nodo sin allowed_roles es libre (no restringe por rol)
            role_ok = not node.allowed_roles or user_role in node.allowed_roles
            if role_ok:
                accessible.append(node.key)
                traverse(node.children, ancestor_blocked=False)
            # Si el rol no tiene acceso a este nodo, sus hijos tampoco

    traverse(tree)
    return accessible


async def assign_module_to_company(
    db: AsyncSession, company_id: uuid.UUID, module_type: str
) -> CompanyModule:
    if module_type not in [m.value for m in ModuleType]:
        raise ValidationError(f"Módulo inválido. Opciones: {[m.value for m in ModuleType]}")

    module_result = await db.execute(select(Module).where(Module.type == module_type))
    module = module_result.scalar_one_or_none()
    if not module:
        raise NotFoundError("Módulo")

    existing = await db.execute(
        select(CompanyModule).where(CompanyModule.company_id == company_id)
    )
    cm = existing.scalar_one_or_none()

    if cm:
        cm.module_id = module.id
        cm.is_active = True
    else:
        cm = CompanyModule(company_id=company_id, module_id=module.id)
        db.add(cm)

    await db.flush()
    await db.refresh(cm)
    return cm


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


async def _get_all_descendant_keys(db: AsyncSession, root_key: str) -> list[str]:
    """CTE recursivo para obtener todas las claves descendientes de un nodo."""
    result = await db.execute(
        text("""
            WITH RECURSIVE descendants AS (
                SELECT key FROM features WHERE parent_key = :root_key
                UNION ALL
                SELECT f.key FROM features f
                INNER JOIN descendants d ON f.parent_key = d.key
            )
            SELECT key FROM descendants
        """),
        {"root_key": root_key},
    )
    return [row[0] for row in result.fetchall()]


async def _get_root_key(db: AsyncSession, feature_key: str) -> str:
    """Devuelve la clave del nodo raíz de un feature (el ancestro sin parent_key)."""
    result = await db.execute(
        text("""
            WITH RECURSIVE ancestors AS (
                SELECT key, parent_key FROM features WHERE key = :feature_key
                UNION ALL
                SELECT f.key, f.parent_key FROM features f
                INNER JOIN ancestors a ON f.key = a.parent_key
            )
            SELECT key FROM ancestors WHERE parent_key IS NULL
        """),
        {"feature_key": feature_key},
    )
    row = result.fetchone()
    return row[0] if row else feature_key


async def _get_ancestor_chain(db: AsyncSession, feature_key: str) -> list[str]:
    """CTE recursivo para obtener la cadena de ancestros en orden raíz→padre."""
    result = await db.execute(
        text("""
            WITH RECURSIVE ancestors AS (
                SELECT key, parent_key FROM features WHERE key = :feature_key
                UNION ALL
                SELECT f.key, f.parent_key FROM features f
                INNER JOIN ancestors a ON f.key = a.parent_key
            )
            SELECT key FROM ancestors WHERE key != :feature_key
        """),
        {"feature_key": feature_key},
    )
    # Devolver en orden raíz→padre (invertir, ya que el CTE sube)
    keys = [row[0] for row in result.fetchall()]
    return list(reversed(keys))
