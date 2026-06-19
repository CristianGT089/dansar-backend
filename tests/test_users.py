import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_create_user(client: AsyncClient, superadmin_token: str):
    response = await client.post(
        "/api/v1/users",
        json={"email": "nuevo@test.com", "full_name": "Nuevo Usuario", "password": "segura123"},
        headers={"Authorization": f"Bearer {superadmin_token}"},
    )
    assert response.status_code == 201
    data = response.json()
    assert data["email"] == "nuevo@test.com"
    assert data["is_superadmin"] is False


@pytest.mark.asyncio
async def test_create_user_weak_password(client: AsyncClient, superadmin_token: str):
    response = await client.post(
        "/api/v1/users",
        json={"email": "weak@test.com", "full_name": "Weak", "password": "123"},
        headers={"Authorization": f"Bearer {superadmin_token}"},
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_assign_user_to_company(client: AsyncClient, superadmin_token: str):
    company = await client.post(
        "/api/v1/companies",
        json={"name": "Empresa Asignacion"},
        headers={"Authorization": f"Bearer {superadmin_token}"},
    )
    company_id = company.json()["id"]

    user = await client.post(
        "/api/v1/users",
        json={"email": "asignar@test.com", "full_name": "Para Asignar", "password": "segura123"},
        headers={"Authorization": f"Bearer {superadmin_token}"},
    )
    user_id = user.json()["id"]

    response = await client.post(
        f"/api/v1/companies/{company_id}/users",
        json={"user_id": user_id, "role": "contador"},
        headers={"Authorization": f"Bearer {superadmin_token}"},
    )
    assert response.status_code == 201
    assert response.json()["role"] == "contador"


@pytest.mark.asyncio
async def test_change_password(client: AsyncClient, superadmin_token: str):
    response = await client.post(
        "/api/v1/users/me/change-password",
        json={"current_password": "password123", "new_password": "nuevasegura456"},
        headers={"Authorization": f"Bearer {superadmin_token}"},
    )
    assert response.status_code == 200
