import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession


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
async def test_create_user_duplicate_email(client: AsyncClient, superadmin_token: str):
    await client.post(
        "/api/v1/users",
        json={"email": "dup@test.com", "full_name": "Primero", "password": "segura123"},
        headers={"Authorization": f"Bearer {superadmin_token}"},
    )
    response = await client.post(
        "/api/v1/users",
        json={"email": "dup@test.com", "full_name": "Segundo", "password": "segura123"},
        headers={"Authorization": f"Bearer {superadmin_token}"},
    )
    assert response.status_code == 409


@pytest.mark.asyncio
async def test_create_user_weak_password(client: AsyncClient, superadmin_token: str):
    response = await client.post(
        "/api/v1/users",
        json={"email": "weak@test.com", "full_name": "Weak", "password": "123"},
        headers={"Authorization": f"Bearer {superadmin_token}"},
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_create_user_requires_superadmin(client: AsyncClient, admin_token: str):
    response = await client.post(
        "/api/v1/users",
        json={"email": "blocked@test.com", "full_name": "Blocked", "password": "segura123"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_list_users_superadmin(client: AsyncClient, superadmin_token: str, superadmin_user):
    response = await client.get(
        "/api/v1/users",
        headers={"Authorization": f"Bearer {superadmin_token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert "items" in data
    assert "total" in data
    assert data["total"] >= 1


@pytest.mark.asyncio
async def test_list_users_blocked_for_non_superadmin(client: AsyncClient, admin_token: str):
    response = await client.get(
        "/api/v1/users",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_get_user_by_id(client: AsyncClient, superadmin_token: str, regular_user):
    response = await client.get(
        f"/api/v1/users/{regular_user.id}",
        headers={"Authorization": f"Bearer {superadmin_token}"},
    )
    assert response.status_code == 200
    assert response.json()["email"] == "user@test.com"


@pytest.mark.asyncio
async def test_get_nonexistent_user(client: AsyncClient, superadmin_token: str):
    import uuid
    response = await client.get(
        f"/api/v1/users/{uuid.uuid4()}",
        headers={"Authorization": f"Bearer {superadmin_token}"},
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_assign_user_to_company(client: AsyncClient, superadmin_token: str, company, regular_user):
    response = await client.post(
        f"/api/v1/companies/{company.id}/users",
        json={"user_id": str(regular_user.id), "role": "contador"},
        headers={"Authorization": f"Bearer {superadmin_token}"},
    )
    assert response.status_code == 201
    assert response.json()["role"] == "contador"


@pytest.mark.asyncio
async def test_assign_user_invalid_role(client: AsyncClient, superadmin_token: str, company, regular_user):
    response = await client.post(
        f"/api/v1/companies/{company.id}/users",
        json={"user_id": str(regular_user.id), "role": "dios"},
        headers={"Authorization": f"Bearer {superadmin_token}"},
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_list_company_users(
    client: AsyncClient, superadmin_token: str, company, admin_user_in_company
):
    response = await client.get(
        f"/api/v1/companies/{company.id}/users",
        headers={"Authorization": f"Bearer {superadmin_token}"},
    )
    assert response.status_code == 200
    assert isinstance(response.json(), list)
    assert len(response.json()) >= 1


@pytest.mark.asyncio
async def test_admin_can_list_own_company_users(
    client: AsyncClient, admin_token: str, company, admin_user_in_company
):
    response = await client.get(
        f"/api/v1/companies/{company.id}/users",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_change_user_role(
    client: AsyncClient, superadmin_token: str, company, regular_user
):
    assign = await client.post(
        f"/api/v1/companies/{company.id}/users",
        json={"user_id": str(regular_user.id), "role": "viewer"},
        headers={"Authorization": f"Bearer {superadmin_token}"},
    )
    assert assign.status_code == 201

    response = await client.patch(
        f"/api/v1/companies/{company.id}/users/{regular_user.id}/role",
        json={"role": "contador"},
        headers={"Authorization": f"Bearer {superadmin_token}"},
    )
    assert response.status_code == 200
    assert response.json()["role"] == "contador"


@pytest.mark.asyncio
async def test_remove_user_from_company(
    client: AsyncClient, superadmin_token: str, company, regular_user
):
    await client.post(
        f"/api/v1/companies/{company.id}/users",
        json={"user_id": str(regular_user.id), "role": "viewer"},
        headers={"Authorization": f"Bearer {superadmin_token}"},
    )

    response = await client.delete(
        f"/api/v1/companies/{company.id}/users/{regular_user.id}",
        headers={"Authorization": f"Bearer {superadmin_token}"},
    )
    assert response.status_code == 204


@pytest.mark.asyncio
async def test_create_user_for_company(
    client: AsyncClient, admin_token: str, company
):
    response = await client.post(
        f"/api/v1/companies/{company.id}/users/create",
        json={"email": "nuevo_empresa@test.com", "full_name": "Nuevo Empresa", "password": "segura123", "role": "viewer"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert response.status_code == 201
    assert response.json()["role"] == "viewer"


@pytest.mark.asyncio
async def test_change_password(client: AsyncClient, superadmin_token: str, superadmin_user):
    response = await client.post(
        "/api/v1/users/me/change-password",
        json={"current_password": "password123", "new_password": "nuevasegura456"},
        headers={"Authorization": f"Bearer {superadmin_token}"},
    )
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_change_password_wrong_current(client: AsyncClient, superadmin_token: str, superadmin_user):
    response = await client.post(
        "/api/v1/users/me/change-password",
        json={"current_password": "incorrecta", "new_password": "nuevasegura456"},
        headers={"Authorization": f"Bearer {superadmin_token}"},
    )
    # El service lanza ValidationError (422) para contraseña incorrecta
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_my_companies(
    client: AsyncClient, admin_token: str, company, admin_user_in_company
):
    response = await client.get(
        "/api/v1/users/me/companies",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert len(data) >= 1
    assert any(str(r["company_id"]) == str(company.id) for r in data)
