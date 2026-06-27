import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_create_company(client: AsyncClient, superadmin_token: str):
    response = await client.post(
        "/api/v1/companies",
        json={"name": "Empresa Test", "tax_id": "900123456-1"},
        headers={"Authorization": f"Bearer {superadmin_token}"},
    )
    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "Empresa Test"
    assert data["is_active"] is True


@pytest.mark.asyncio
async def test_create_company_without_tax_id(client: AsyncClient, superadmin_token: str):
    response = await client.post(
        "/api/v1/companies",
        json={"name": "Sin NIT"},
        headers={"Authorization": f"Bearer {superadmin_token}"},
    )
    assert response.status_code == 201
    assert response.json()["tax_id"] is None


@pytest.mark.asyncio
async def test_create_company_duplicate_tax_id(client: AsyncClient, superadmin_token: str):
    await client.post(
        "/api/v1/companies",
        json={"name": "Empresa A", "tax_id": "800000001-1"},
        headers={"Authorization": f"Bearer {superadmin_token}"},
    )
    response = await client.post(
        "/api/v1/companies",
        json={"name": "Empresa B", "tax_id": "800000001-1"},
        headers={"Authorization": f"Bearer {superadmin_token}"},
    )
    assert response.status_code == 409


@pytest.mark.asyncio
async def test_create_company_requires_superadmin(client: AsyncClient, admin_token: str):
    response = await client.post(
        "/api/v1/companies",
        json={"name": "Bloqueada"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_list_companies(client: AsyncClient, superadmin_token: str):
    response = await client.get(
        "/api/v1/companies",
        headers={"Authorization": f"Bearer {superadmin_token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert "items" in data
    assert "total" in data


@pytest.mark.asyncio
async def test_list_companies_pagination(client: AsyncClient, superadmin_token: str):
    response = await client.get(
        "/api/v1/companies?page=1&page_size=1",
        headers={"Authorization": f"Bearer {superadmin_token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert len(data["items"]) <= 1


@pytest.mark.asyncio
async def test_get_company_by_id(client: AsyncClient, superadmin_token: str, company):
    response = await client.get(
        f"/api/v1/companies/{company.id}",
        headers={"Authorization": f"Bearer {superadmin_token}"},
    )
    assert response.status_code == 200
    assert response.json()["id"] == str(company.id)


@pytest.mark.asyncio
async def test_get_nonexistent_company(client: AsyncClient, superadmin_token: str):
    import uuid
    response = await client.get(
        f"/api/v1/companies/{uuid.uuid4()}",
        headers={"Authorization": f"Bearer {superadmin_token}"},
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_update_company(client: AsyncClient, superadmin_token: str, company):
    response = await client.patch(
        f"/api/v1/companies/{company.id}",
        json={"name": "Nombre Actualizado"},
        headers={"Authorization": f"Bearer {superadmin_token}"},
    )
    assert response.status_code == 200
    assert response.json()["name"] == "Nombre Actualizado"


@pytest.mark.asyncio
async def test_toggle_company_status(client: AsyncClient, superadmin_token: str, company):
    response = await client.post(
        f"/api/v1/companies/{company.id}/toggle-status",
        headers={"Authorization": f"Bearer {superadmin_token}"},
    )
    assert response.status_code == 200
    assert response.json()["is_active"] is False

    # Toggle back
    response2 = await client.post(
        f"/api/v1/companies/{company.id}/toggle-status",
        headers={"Authorization": f"Bearer {superadmin_token}"},
    )
    assert response2.json()["is_active"] is True


@pytest.mark.asyncio
async def test_regular_user_cannot_list_companies(client: AsyncClient, regular_user):
    login = await client.post(
        "/api/v1/auth/login",
        json={"email": "user@test.com", "password": "password123"},
    )
    token = login.json()["access_token"]
    response = await client.get(
        "/api/v1/companies",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_admin_empresa_cannot_list_all_companies(client: AsyncClient, admin_token: str):
    response = await client.get(
        "/api/v1/companies",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert response.status_code == 403
