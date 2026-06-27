"""
Tests para el árbol recursivo de features.
Todos estos tests FALLAN antes de implementar el CTE recursivo.
"""
import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession


# ── Fixtures locales de árbol profundo ────────────────────────────────────────

@pytest_asyncio.fixture(scope="session", loop_scope="session")
async def deep_tree(db: AsyncSession):
    """Crea un árbol de 4 niveles: raiz → nivel1 → nivel2 → nivel3."""
    from app.modules.catalog.models import Feature

    raiz  = Feature(key="tree.root",           name="Raíz",    module="tree")
    n1    = Feature(key="tree.root.n1",        name="Nivel 1", module="tree", parent_key="tree.root")
    n2    = Feature(key="tree.root.n1.n2",     name="Nivel 2", module="tree", parent_key="tree.root.n1")
    n3    = Feature(key="tree.root.n1.n2.n3",  name="Nivel 3", module="tree", parent_key="tree.root.n1.n2")

    for f in [raiz, n1, n2, n3]:
        db.add(f)
    await db.commit()
    return {"root": raiz, "n1": n1, "n2": n2, "n3": n3}


@pytest_asyncio.fixture(scope="session", loop_scope="session")
async def tree_company(db: AsyncSession):
    from app.modules.companies.models import Company
    co = Company(name="Tree Company", tax_id="333000333-3")
    db.add(co)
    await db.commit()
    await db.refresh(co)
    return co


# ── Tests del endpoint GET /module (árbol completo) ───────────────────────────

@pytest.mark.asyncio
async def test_company_module_returns_nested_tree(
    client: AsyncClient,
    superadmin_token: str,
    deep_tree,
    tree_company,
):
    """GET /companies/{id}/module debe devolver el árbol anidado, no una lista plana."""
    response = await client.get(
        f"/api/v1/companies/{tree_company.id}/module",
        headers={"Authorization": f"Bearer {superadmin_token}"},
    )
    assert response.status_code == 200
    features = response.json()["features"]

    # La raíz debe aparecer con children anidados recursivamente
    root = next((f for f in features if f["key"] == "tree.root"), None)
    assert root is not None, "La raíz no aparece en la respuesta"

    n1 = next((c for c in root["children"] if c["key"] == "tree.root.n1"), None)
    assert n1 is not None, "Nivel 1 no aparece como hijo de raíz"

    n2 = next((c for c in n1["children"] if c["key"] == "tree.root.n1.n2"), None)
    assert n2 is not None, "Nivel 2 no aparece como hijo de nivel 1"

    n3 = next((c for c in n2["children"] if c["key"] == "tree.root.n1.n2.n3"), None)
    assert n3 is not None, "Nivel 3 no aparece como hijo de nivel 2"


@pytest.mark.asyncio
async def test_toggle_cascades_disable_to_all_descendants(
    client: AsyncClient,
    superadmin_token: str,
    deep_tree,
    tree_company,
    db: AsyncSession,
):
    """Deshabilitar la raíz debe deshabilitar TODOS los descendientes (no solo hijos directos)."""
    from sqlalchemy import select
    from app.modules.catalog.models import CompanyFeature, Feature

    # Habilitar toda la cadena
    for key in ["tree.root", "tree.root.n1", "tree.root.n1.n2", "tree.root.n1.n2.n3"]:
        await client.post(
            f"/api/v1/companies/{tree_company.id}/module/features/toggle",
            json={"feature_key": key, "enabled": True},
            headers={"Authorization": f"Bearer {superadmin_token}"},
        )

    # Deshabilitar raíz
    await client.post(
        f"/api/v1/companies/{tree_company.id}/module/features/toggle",
        json={"feature_key": "tree.root", "enabled": False},
        headers={"Authorization": f"Bearer {superadmin_token}"},
    )

    # Verificar que n2 y n3 también quedaron deshabilitados
    for key in ["tree.root.n1", "tree.root.n1.n2", "tree.root.n1.n2.n3"]:
        feat = (await db.execute(select(Feature).where(Feature.key == key))).scalar_one()
        cf = (await db.execute(
            select(CompanyFeature).where(
                CompanyFeature.company_id == tree_company.id,
                CompanyFeature.feature_id == feat.id,
            )
        )).scalar_one_or_none()
        assert cf is not None and cf.is_enabled is False, f"{key} debería estar deshabilitado"


@pytest.mark.asyncio
async def test_toggle_intermediate_node_requires_parent_enabled(
    client: AsyncClient,
    superadmin_token: str,
    deep_tree,
    tree_company,
):
    """Habilitar n2 debe fallar si n1 no está habilitado."""
    response = await client.post(
        f"/api/v1/companies/{tree_company.id}/module/features/toggle",
        json={"feature_key": "tree.root.n1.n2", "enabled": True},
        headers={"Authorization": f"Bearer {superadmin_token}"},
    )
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_allowed_roles_apply_at_any_depth(
    client: AsyncClient,
    superadmin_token: str,
    deep_tree,
    tree_company,
    db: AsyncSession,
):
    """allowed_roles en un nodo intermedio debe restringir el acceso en ese nivel."""
    from app.core.security import create_access_token, hash_password
    from app.modules.users.models import User, UserCompanyRole

    # Habilitar árbol completo
    for key in ["tree.root", "tree.root.n1", "tree.root.n1.n2"]:
        await client.post(
            f"/api/v1/companies/{tree_company.id}/module/features/toggle",
            json={"feature_key": key, "enabled": True},
            headers={"Authorization": f"Bearer {superadmin_token}"},
        )

    # Asignar allowed_roles=["admin"] en n1 (nodo intermedio)
    await client.patch(
        f"/api/v1/companies/{tree_company.id}/module/features/tree.root.n1/roles",
        json={"roles": ["admin"]},
        headers={"Authorization": f"Bearer {superadmin_token}"},
    )

    # Crear usuario viewer
    viewer = User(
        email="tree_viewer@test.com",
        full_name="Tree Viewer",
        hashed_password=hash_password("password123"),
    )
    db.add(viewer)
    await db.commit()
    await db.refresh(viewer)
    db.add(UserCompanyRole(user_id=viewer.id, company_id=tree_company.id, role="viewer", is_active=True))
    await db.commit()

    token = create_access_token(str(viewer.id))
    response = await client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200

    company_data = next(
        (c for c in response.json()["companies"] if str(c["id"]) == str(tree_company.id)),
        None,
    )
    assert company_data is not None
    features = company_data["features"]

    # tree.root es visible (sin roles restringidos)
    assert "tree.root" in features
    # tree.root.n1 NO debe ser visible para viewer (allowed_roles=["admin"])
    assert "tree.root.n1" not in features
    # tree.root.n1.n2 tampoco (su ancestro n1 está restringido)
    assert "tree.root.n1.n2" not in features
