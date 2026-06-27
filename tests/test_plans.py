import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession


# ── Plans ─────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_list_plans_returns_active(client: AsyncClient, superadmin_token: str, plan_basic):
    response = await client.get(
        "/api/v1/plans",
        headers={"Authorization": f"Bearer {superadmin_token}"},
    )
    assert response.status_code == 200
    keys = [p["type"] for p in response.json()]
    assert "basic" in keys


@pytest.mark.asyncio
async def test_list_plans_requires_auth(client: AsyncClient):
    response = await client.get("/api/v1/plans")
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_assign_plan_to_company(client: AsyncClient, superadmin_token: str, company, plan_basic):
    response = await client.post(
        f"/api/v1/companies/{company.id}/plan/assign",
        json={"plan_type": "basic"},
        headers={"Authorization": f"Bearer {superadmin_token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["is_active"] is True
    assert str(data["company_id"]) == str(company.id)


@pytest.mark.asyncio
async def test_assign_plan_invalid_type(client: AsyncClient, superadmin_token: str, company):
    response = await client.post(
        f"/api/v1/companies/{company.id}/plan/assign",
        json={"plan_type": "nonexistent"},
        headers={"Authorization": f"Bearer {superadmin_token}"},
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_assign_plan_requires_superadmin(client: AsyncClient, admin_token: str, company, plan_basic):
    response = await client.post(
        f"/api/v1/companies/{company.id}/plan/assign",
        json={"plan_type": "basic"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert response.status_code == 403


# ── Features catalog ──────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_list_features(client: AsyncClient, superadmin_token: str, feature_parent):
    response = await client.get(
        "/api/v1/plans/features",
        headers={"Authorization": f"Bearer {superadmin_token}"},
    )
    assert response.status_code == 200
    keys = [f["key"] for f in response.json()]
    assert feature_parent.key in keys


@pytest.mark.asyncio
async def test_create_feature_superadmin(client: AsyncClient, superadmin_token: str):
    response = await client.post(
        "/api/v1/plans/features",
        json={"key": "new.feature", "name": "Nueva Feature", "module": "test"},
        headers={"Authorization": f"Bearer {superadmin_token}"},
    )
    assert response.status_code == 201
    assert response.json()["key"] == "new.feature"


@pytest.mark.asyncio
async def test_create_feature_duplicate_key(client: AsyncClient, superadmin_token: str, feature_parent):
    response = await client.post(
        "/api/v1/plans/features",
        json={"key": feature_parent.key, "name": "Duplicada", "module": "test"},
        headers={"Authorization": f"Bearer {superadmin_token}"},
    )
    assert response.status_code == 409


@pytest.mark.asyncio
async def test_create_feature_with_invalid_parent(client: AsyncClient, superadmin_token: str):
    response = await client.post(
        "/api/v1/plans/features",
        json={"key": "orphan.feature", "name": "Orphan", "module": "test", "parent_key": "no.existe"},
        headers={"Authorization": f"Bearer {superadmin_token}"},
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_create_feature_with_valid_parent(client: AsyncClient, superadmin_token: str, feature_parent):
    response = await client.post(
        "/api/v1/plans/features",
        json={
            "key": "test.module.child2",
            "name": "Hijo 2",
            "module": "test",
            "parent_key": feature_parent.key,
        },
        headers={"Authorization": f"Bearer {superadmin_token}"},
    )
    assert response.status_code == 201
    assert response.json()["parent_key"] == feature_parent.key


@pytest.mark.asyncio
async def test_create_feature_requires_superadmin(client: AsyncClient, admin_token: str):
    response = await client.post(
        "/api/v1/plans/features",
        json={"key": "blocked.feature", "name": "Bloqueada", "module": "test"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert response.status_code == 403


# ── Company features ──────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_get_company_features_empty(client: AsyncClient, superadmin_token: str, company):
    response = await client.get(
        f"/api/v1/companies/{company.id}/plan",
        headers={"Authorization": f"Bearer {superadmin_token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert "features" in data
    assert isinstance(data["features"], list)


@pytest.mark.asyncio
async def test_toggle_feature_enable(client: AsyncClient, superadmin_token: str, company, feature_parent):
    response = await client.post(
        f"/api/v1/companies/{company.id}/plan/features/toggle",
        json={"feature_key": feature_parent.key, "enabled": True},
        headers={"Authorization": f"Bearer {superadmin_token}"},
    )
    assert response.status_code == 200
    assert response.json()["enabled"] is True


@pytest.mark.asyncio
async def test_toggle_feature_disable_cascades_to_children(
    client: AsyncClient,
    superadmin_token: str,
    company,
    feature_parent,
    feature_child,
    db: AsyncSession,
):
    from sqlalchemy import select
    from app.modules.plans.models import CompanyFeature, Feature

    # Enable parent
    await client.post(
        f"/api/v1/companies/{company.id}/plan/features/toggle",
        json={"feature_key": feature_parent.key, "enabled": True},
        headers={"Authorization": f"Bearer {superadmin_token}"},
    )
    # Enable child
    await client.patch(
        f"/api/v1/companies/{company.id}/plan/features/{feature_child.key}/toggle",
        json={"enabled": True},
        headers={"Authorization": f"Bearer {superadmin_token}"},
    )

    # Now disable parent — child should cascade to disabled
    await client.post(
        f"/api/v1/companies/{company.id}/plan/features/toggle",
        json={"feature_key": feature_parent.key, "enabled": False},
        headers={"Authorization": f"Bearer {superadmin_token}"},
    )

    child_feature = (await db.execute(select(Feature).where(Feature.key == feature_child.key))).scalar_one()
    cf = (
        await db.execute(
            select(CompanyFeature).where(
                CompanyFeature.company_id == company.id,
                CompanyFeature.feature_id == child_feature.id,
            )
        )
    ).scalar_one_or_none()
    assert cf is not None
    assert cf.is_enabled is False


@pytest.mark.asyncio
async def test_toggle_subfeature_requires_parent_enabled(
    client: AsyncClient, superadmin_token: str, company, feature_parent, feature_child
):
    # Parent is disabled (default) — toggling subfeature should fail
    response = await client.patch(
        f"/api/v1/companies/{company.id}/plan/features/{feature_child.key}/toggle",
        json={"enabled": True},
        headers={"Authorization": f"Bearer {superadmin_token}"},
    )
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_toggle_parent_via_subfeature_endpoint_rejected(
    client: AsyncClient, superadmin_token: str, company, feature_parent
):
    response = await client.patch(
        f"/api/v1/companies/{company.id}/plan/features/{feature_parent.key}/toggle",
        json={"enabled": True},
        headers={"Authorization": f"Bearer {superadmin_token}"},
    )
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_admin_can_toggle_subfeature(
    client: AsyncClient,
    superadmin_token: str,
    admin_token: str,
    company,
    feature_parent,
    feature_child,
):
    # Superadmin enables parent first
    await client.post(
        f"/api/v1/companies/{company.id}/plan/features/toggle",
        json={"feature_key": feature_parent.key, "enabled": True},
        headers={"Authorization": f"Bearer {superadmin_token}"},
    )

    response = await client.patch(
        f"/api/v1/companies/{company.id}/plan/features/{feature_child.key}/toggle",
        json={"enabled": True},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert response.status_code == 200
    assert response.json()["enabled"] is True


# ── Feature roles ─────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_set_feature_roles(
    client: AsyncClient, superadmin_token: str, company, feature_parent, feature_child
):
    # Enable parent first
    await client.post(
        f"/api/v1/companies/{company.id}/plan/features/toggle",
        json={"feature_key": feature_parent.key, "enabled": True},
        headers={"Authorization": f"Bearer {superadmin_token}"},
    )

    response = await client.patch(
        f"/api/v1/companies/{company.id}/plan/features/{feature_child.key}/roles",
        json={"roles": ["admin", "contador"]},
        headers={"Authorization": f"Bearer {superadmin_token}"},
    )
    assert response.status_code == 200
    assert set(response.json()["allowed_roles"]) == {"admin", "contador"}


@pytest.mark.asyncio
async def test_set_roles_on_parent_rejected(
    client: AsyncClient, superadmin_token: str, company, feature_parent
):
    response = await client.patch(
        f"/api/v1/companies/{company.id}/plan/features/{feature_parent.key}/roles",
        json={"roles": ["admin"]},
        headers={"Authorization": f"Bearer {superadmin_token}"},
    )
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_set_invalid_role_rejected(
    client: AsyncClient, superadmin_token: str, company, feature_parent, feature_child
):
    await client.post(
        f"/api/v1/companies/{company.id}/plan/features/toggle",
        json={"feature_key": feature_parent.key, "enabled": True},
        headers={"Authorization": f"Bearer {superadmin_token}"},
    )

    response = await client.patch(
        f"/api/v1/companies/{company.id}/plan/features/{feature_child.key}/roles",
        json={"roles": ["superadmin"]},
        headers={"Authorization": f"Bearer {superadmin_token}"},
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_viewer_cannot_set_roles(
    client: AsyncClient,
    superadmin_token: str,
    company,
    feature_parent,
    feature_child,
    db: AsyncSession,
):
    from app.core.security import hash_password
    from app.modules.users.models import User, UserCompanyRole

    viewer = User(
        email="viewer@test.com",
        full_name="Viewer",
        hashed_password=hash_password("password123"),
    )
    db.add(viewer)
    await db.commit()
    db.add(UserCompanyRole(user_id=viewer.id, company_id=company.id, role="viewer", is_active=True))
    await db.commit()

    login = await client.post(
        "/api/v1/auth/login",
        json={"email": "viewer@test.com", "password": "password123"},
    )
    viewer_token = login.json()["access_token"]

    response = await client.patch(
        f"/api/v1/companies/{company.id}/plan/features/{feature_child.key}/roles",
        json={"roles": ["viewer"]},
        headers={"Authorization": f"Bearer {viewer_token}"},
    )
    assert response.status_code == 403
