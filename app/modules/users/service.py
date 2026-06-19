import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.security import hash_password, verify_password
from app.modules.users.models import User, UserCompanyRole
from app.modules.users.schemas import (
    AssignUserToCompanyRequest,
    UserCreate,
    UserUpdate,
)
from app.shared.exceptions import ConflictError, ForbiddenError, NotFoundError, ValidationError


async def get_user_or_404(db: AsyncSession, user_id: uuid.UUID) -> User:
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise NotFoundError("Usuario")
    return user


async def assert_user_belongs_to_company(
    db: AsyncSession, user_id: uuid.UUID, company_id: uuid.UUID
) -> UserCompanyRole:
    result = await db.execute(
        select(UserCompanyRole).where(
            UserCompanyRole.user_id == user_id,
            UserCompanyRole.company_id == company_id,
            UserCompanyRole.is_active == True,
        )
    )
    role = result.scalar_one_or_none()
    if not role:
        raise ForbiddenError("No tienes acceso a esta empresa")
    return role


async def list_users(
    db: AsyncSession, page: int = 1, page_size: int = 20
) -> tuple[list[User], int]:
    offset = (page - 1) * page_size
    total = (await db.execute(select(func.count()).select_from(User))).scalar_one()
    result = await db.execute(select(User).offset(offset).limit(page_size))
    return result.scalars().all(), total


async def create_user(db: AsyncSession, data: UserCreate) -> User:
    existing = await db.execute(select(User).where(User.email == data.email))
    if existing.scalar_one_or_none():
        raise ConflictError("Ya existe un usuario con ese email")

    user = User(
        email=data.email,
        full_name=data.full_name,
        hashed_password=hash_password(data.password),
        is_superadmin=data.is_superadmin,
    )
    db.add(user)
    await db.flush()
    await db.refresh(user)
    return user


async def update_user(db: AsyncSession, user_id: uuid.UUID, data: UserUpdate) -> User:
    user = await get_user_or_404(db, user_id)
    for field, value in data.model_dump(exclude_none=True).items():
        setattr(user, field, value)
    await db.flush()
    await db.refresh(user)
    return user


async def change_password(
    db: AsyncSession, user: User, current_password: str, new_password: str
) -> None:
    if not verify_password(current_password, user.hashed_password):
        raise ValidationError("Contraseña actual incorrecta")
    user.hashed_password = hash_password(new_password)
    await db.flush()


async def list_company_users(
    db: AsyncSession, company_id: uuid.UUID
) -> list[UserCompanyRole]:
    result = await db.execute(
        select(UserCompanyRole)
        .where(
            UserCompanyRole.company_id == company_id,
            UserCompanyRole.is_active == True,
        )
        .options(selectinload(UserCompanyRole.user))
    )
    return result.scalars().all()


async def assign_user_to_company(
    db: AsyncSession, company_id: uuid.UUID, data: AssignUserToCompanyRequest
) -> UserCompanyRole:
    await get_user_or_404(db, data.user_id)

    existing = await db.execute(
        select(UserCompanyRole).where(
            UserCompanyRole.user_id == data.user_id,
            UserCompanyRole.company_id == company_id,
        )
    )
    role_entry = existing.scalar_one_or_none()

    if role_entry:
        role_entry.role = data.role
        role_entry.is_active = True
    else:
        role_entry = UserCompanyRole(
            user_id=data.user_id,
            company_id=company_id,
            role=data.role,
        )
        db.add(role_entry)

    await db.flush()
    await db.refresh(role_entry, ["user"])
    return role_entry


async def remove_user_from_company(
    db: AsyncSession, company_id: uuid.UUID, user_id: uuid.UUID
) -> None:
    result = await db.execute(
        select(UserCompanyRole).where(
            UserCompanyRole.user_id == user_id,
            UserCompanyRole.company_id == company_id,
        )
    )
    role_entry = result.scalar_one_or_none()
    if not role_entry:
        raise NotFoundError("Asignación de usuario")
    role_entry.is_active = False
    await db.flush()
