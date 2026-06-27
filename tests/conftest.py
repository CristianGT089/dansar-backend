import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.database import Base, get_db
from app.main import app

TEST_DATABASE_URL = "postgresql+asyncpg://test:test@localhost:5432/dansar_test"

engine = create_async_engine(TEST_DATABASE_URL, echo=False)
TestSession = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


# ── Infraestructura ───────────────────────────────────────────────────────────

@pytest_asyncio.fixture(scope="session", loop_scope="session")
async def setup_database():
    import app.core.models_registry  # noqa: F401
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest_asyncio.fixture(scope="session", loop_scope="session")
async def db(setup_database):
    """Sesión única para toda la suite. Las fixtures crean datos una sola vez."""
    async with TestSession() as session:
        yield session


@pytest_asyncio.fixture(scope="session", loop_scope="session")
async def client(setup_database):
    """
    Cada request HTTP obtiene su propia sesión con commit automático,
    idéntico al comportamiento de get_db en producción.
    La DB de test se configura vía DATABASE_URL en el env antes de importar la app.
    """
    async def override_get_db():
        async with TestSession() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    app.dependency_overrides[get_db] = override_get_db
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c
    app.dependency_overrides.clear()


# ── Usuarios base ─────────────────────────────────────────────────────────────

@pytest_asyncio.fixture(scope="session", loop_scope="session")
async def superadmin_user(db: AsyncSession):
    from app.core.security import hash_password
    from app.modules.users.models import User

    user = User(
        email="admin@test.com",
        full_name="Super Admin",
        hashed_password=hash_password("password123"),
        is_superadmin=True,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


@pytest_asyncio.fixture(scope="session", loop_scope="session")
async def regular_user(db: AsyncSession):
    from app.core.security import hash_password
    from app.modules.users.models import User

    user = User(
        email="user@test.com",
        full_name="Regular User",
        hashed_password=hash_password("password123"),
        is_superadmin=False,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


@pytest_asyncio.fixture(scope="session", loop_scope="session")
async def superadmin_tokens(client, superadmin_user):
    """Devuelve {'access_token': ..., 'refresh_token': ...} para toda la sesión."""
    response = await client.post(
        "/api/v1/auth/login",
        json={"email": "admin@test.com", "password": "password123"},
    )
    return response.json()


@pytest_asyncio.fixture(scope="session", loop_scope="session")
async def superadmin_token(superadmin_tokens):
    return superadmin_tokens["access_token"]


# ── Empresa ───────────────────────────────────────────────────────────────────

@pytest_asyncio.fixture(scope="session", loop_scope="session")
async def company(db: AsyncSession):
    from app.modules.companies.models import Company

    c = Company(name="Empresa Test", tax_id="900000001-1")
    db.add(c)
    await db.commit()
    await db.refresh(c)
    return c


# ── Planes y features ─────────────────────────────────────────────────────────

@pytest_asyncio.fixture(scope="session", loop_scope="session")
async def plan_basic(db: AsyncSession):
    from app.modules.catalog.models import Module

    plan = Module(name="Básico", type="basic", description="Plan básico de prueba", is_active=True)
    db.add(plan)
    await db.commit()
    await db.refresh(plan)
    return plan


@pytest_asyncio.fixture(scope="session", loop_scope="session")
async def feature_parent(db: AsyncSession):
    from app.modules.catalog.models import Feature

    f = Feature(key="test.module", name="Módulo Test", module="test")
    db.add(f)
    await db.commit()
    await db.refresh(f)
    return f


@pytest_asyncio.fixture(scope="session", loop_scope="session")
async def feature_child(db: AsyncSession, feature_parent):
    from app.modules.catalog.models import Feature

    f = Feature(
        key="test.module.sub",
        name="Sub Módulo Test",
        module="test",
        parent_key=feature_parent.key,
    )
    db.add(f)
    await db.commit()
    await db.refresh(f)
    return f


# ── Usuario admin de empresa ──────────────────────────────────────────────────

@pytest_asyncio.fixture(scope="session", loop_scope="session")
async def admin_user(db: AsyncSession):
    from app.core.security import hash_password
    from app.modules.users.models import User

    user = User(
        email="admin_empresa@test.com",
        full_name="Admin Empresa",
        hashed_password=hash_password("password123"),
        is_superadmin=False,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


@pytest_asyncio.fixture(scope="session", loop_scope="session")
async def admin_user_in_company(db: AsyncSession, admin_user, company):
    from app.modules.users.models import UserCompanyRole

    role = UserCompanyRole(user_id=admin_user.id, company_id=company.id, role="admin", is_active=True)
    db.add(role)
    await db.commit()
    return role


@pytest_asyncio.fixture(scope="session", loop_scope="session")
async def admin_token(client, admin_user, admin_user_in_company):
    response = await client.post(
        "/api/v1/auth/login",
        json={"email": "admin_empresa@test.com", "password": "password123"},
    )
    return response.json()["access_token"]
