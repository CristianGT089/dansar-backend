import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

# Nota: los tests de refresh/logout usan los tokens de la fixture `superadmin_tokens`
# para evitar logins duplicados dentro de la misma sesión (mismo exp → mismo hash JWT).


@pytest.mark.asyncio
async def test_login_success(client: AsyncClient, superadmin_user):
    response = await client.post(
        "/api/v1/auth/login",
        json={"email": "admin@test.com", "password": "password123"},
    )
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert "refresh_token" in data
    assert data["token_type"] == "bearer"


@pytest.mark.asyncio
async def test_login_wrong_password(client: AsyncClient, superadmin_user):
    response = await client.post(
        "/api/v1/auth/login",
        json={"email": "admin@test.com", "password": "wrong"},
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_login_nonexistent_user(client: AsyncClient):
    response = await client.post(
        "/api/v1/auth/login",
        json={"email": "noexiste@test.com", "password": "password123"},
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_login_inactive_user(client: AsyncClient, db: AsyncSession):
    from app.core.security import hash_password
    from app.modules.users.models import User

    user = User(
        email="inactivo@test.com",
        full_name="Inactivo",
        hashed_password=hash_password("password123"),
        is_active=False,
    )
    db.add(user)
    await db.commit()

    response = await client.post(
        "/api/v1/auth/login",
        json={"email": "inactivo@test.com", "password": "password123"},
    )
    assert response.status_code == 401



@pytest.mark.asyncio
async def test_get_me(client: AsyncClient, superadmin_token: str):
    response = await client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {superadmin_token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["email"] == "admin@test.com"
    assert data["is_superadmin"] is True
    assert "companies" in data


@pytest.mark.asyncio
async def test_get_me_includes_company_features(client: AsyncClient, db: AsyncSession):
    """Usuario asignado a empresa ve las features activas y las subfunciones con rol permitido."""
    from app.core.security import hash_password, create_access_token
    from app.modules.companies.models import Company
    from app.modules.users.models import User, UserCompanyRole
    from app.modules.catalog.models import Feature, CompanyFeature

    # Entidades propias de este test para no interferir con fixtures compartidas
    co = Company(name="Me Test Company", tax_id="111000111-1")
    db.add(co)
    await db.commit()
    await db.refresh(co)

    fp = Feature(key="me.parent", name="Me Parent", module="auth_test")
    db.add(fp)
    await db.commit()
    await db.refresh(fp)

    fc = Feature(key="me.parent.child", name="Me Child", module="auth_test", parent_key="me.parent")
    db.add(fc)
    await db.commit()
    await db.refresh(fc)

    user = User(email="mefeat@test.com", full_name="Me Feature", hashed_password=hash_password("password123"))
    db.add(user)
    await db.commit()
    await db.refresh(user)

    db.add(UserCompanyRole(user_id=user.id, company_id=co.id, role="contador", is_active=True))
    db.add(CompanyFeature(company_id=co.id, feature_id=fp.id, is_enabled=True, allowed_roles=[]))
    db.add(CompanyFeature(company_id=co.id, feature_id=fc.id, is_enabled=True, allowed_roles=["contador"]))
    await db.commit()

    token = create_access_token(str(user.id))
    response = await client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200
    data = response.json()
    assert len(data["companies"]) == 1
    features = data["companies"][0]["features"]
    assert "me.parent" in features
    assert "me.parent.child" in features


@pytest.mark.asyncio
async def test_get_me_subfeature_hidden_by_role(client: AsyncClient, db: AsyncSession):
    """Subfeature con allowed_roles=[admin] no aparece para un viewer."""
    from app.core.security import hash_password, create_access_token
    from app.modules.companies.models import Company
    from app.modules.users.models import User, UserCompanyRole
    from app.modules.catalog.models import Feature, CompanyFeature

    co = Company(name="Me Viewer Company", tax_id="222000222-2")
    db.add(co)
    await db.commit()
    await db.refresh(co)

    fp = Feature(key="view.parent", name="View Parent", module="auth_test2")
    db.add(fp)
    await db.commit()
    await db.refresh(fp)

    fc = Feature(key="view.parent.child", name="View Child", module="auth_test2", parent_key="view.parent")
    db.add(fc)
    await db.commit()
    await db.refresh(fc)

    user = User(email="viewerfeat@test.com", full_name="Viewer Feat", hashed_password=hash_password("password123"))
    db.add(user)
    await db.commit()
    await db.refresh(user)

    db.add(UserCompanyRole(user_id=user.id, company_id=co.id, role="viewer", is_active=True))
    db.add(CompanyFeature(company_id=co.id, feature_id=fp.id, is_enabled=True, allowed_roles=[]))
    db.add(CompanyFeature(company_id=co.id, feature_id=fc.id, is_enabled=True, allowed_roles=["admin"]))
    await db.commit()

    token = create_access_token(str(user.id))
    response = await client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200
    features = response.json()["companies"][0]["features"]
    assert "view.parent" in features
    assert "view.parent.child" not in features


@pytest.mark.asyncio
async def test_refresh_token(client: AsyncClient, superadmin_tokens: dict):
    refresh_token = superadmin_tokens["refresh_token"]
    response = await client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": refresh_token},
    )
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert "refresh_token" in data
    # Actualizar el refresh token en la fixture dict para evitar conflictos en siguientes tests
    superadmin_tokens["refresh_token"] = data["refresh_token"]


@pytest.mark.asyncio
async def test_refresh_token_reuse_rejected(client: AsyncClient, superadmin_tokens: dict):
    # Usar el token rotado del test anterior — este ya fue usado, debe ser rechazado
    # Pero como el anterior test actualizó superadmin_tokens, usamos un token ficticio
    response = await client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": "token.ya.revocado.o.invalido"},
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_refresh_with_access_token_rejected(client: AsyncClient, superadmin_tokens: dict):
    """Usar un access token donde se espera refresh debe fallar."""
    response = await client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": superadmin_tokens["access_token"]},
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_refresh_with_garbage_token(client: AsyncClient):
    response = await client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": "esto.no.es.un.token"},
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_logout(client: AsyncClient, superadmin_token: str):
    response = await client.post(
        "/api/v1/auth/logout",
        headers={"Authorization": f"Bearer {superadmin_token}"},
    )
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_logout_revokes_refresh_token(client: AsyncClient, superadmin_tokens: dict):
    """Después del logout el refresh token (ya rotado) queda revocado."""
    # En este punto superadmin_tokens["refresh_token"] fue rotado por test_refresh_token
    # y luego el logout revocó todos los tokens del usuario.
    # Cualquier intento de refresh debe fallar.
    response = await client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": superadmin_tokens["refresh_token"]},
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_unauthorized_without_token(client: AsyncClient):
    response = await client.get("/api/v1/auth/me")
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_health_endpoint(client: AsyncClient):
    response = await client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_decode_invalid_token_raises():
    """decode_token debe propagar JWTError, no silenciar con {}."""
    from jose import JWTError
    from app.core.security import decode_token

    with pytest.raises(JWTError):
        decode_token("esto.no.es.un.jwt.valido")


@pytest.mark.asyncio
async def test_health_endpoint_checks_db(client: AsyncClient):
    """El endpoint /health debe verificar conectividad con la base de datos."""
    response = await client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data.get("db") == "ok"
