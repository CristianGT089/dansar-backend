import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_admin_dashboard_superadmin(client: AsyncClient, superadmin_token: str):
    response = await client.get(
        "/api/v1/admin/dashboard",
        headers={"Authorization": f"Bearer {superadmin_token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert "companies" in data
    assert "users" in data
    assert "total" in data["companies"]
    assert "active" in data["companies"]
    assert "inactive" in data["companies"]
    assert "total" in data["users"]


@pytest.mark.asyncio
async def test_admin_dashboard_counts_include_created_entities(
    client: AsyncClient, superadmin_token: str, company, superadmin_user
):
    response = await client.get(
        "/api/v1/admin/dashboard",
        headers={"Authorization": f"Bearer {superadmin_token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["companies"]["total"] >= 1
    assert data["users"]["total"] >= 1


@pytest.mark.asyncio
async def test_admin_dashboard_blocked_for_regular_user(client: AsyncClient, regular_user):
    login = await client.post(
        "/api/v1/auth/login",
        json={"email": "user@test.com", "password": "password123"},
    )
    token = login.json()["access_token"]

    response = await client.get(
        "/api/v1/admin/dashboard",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_admin_dashboard_blocked_for_admin_empresa(
    client: AsyncClient, admin_token: str
):
    response = await client.get(
        "/api/v1/admin/dashboard",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_admin_dashboard_requires_auth(client: AsyncClient):
    response = await client.get("/api/v1/admin/dashboard")
    assert response.status_code == 403
