import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.modules.auth.dependencies import CurrentUser, SuperAdmin
from app.modules.users import service
from app.shared.exceptions import ForbiddenError
from app.modules.users.schemas import (
    AssignUserToCompanyRequest,
    ChangePasswordRequest,
    ChangeRoleRequest,
    CreateUserForCompanyRequest,
    UserCompanyRoleResponse,
    UserCreate,
    UserListResponse,
    UserResponse,
    UserUpdate,
)

router = APIRouter(prefix="/users", tags=["Users"])


@router.get("", response_model=UserListResponse)
async def list_users(
    _: SuperAdmin,
    db: AsyncSession = Depends(get_db),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    items, total = await service.list_users(db, page, page_size)
    return UserListResponse(items=items, total=total, page=page, page_size=page_size)


@router.post("", response_model=UserResponse, status_code=201)
async def create_user(
    data: UserCreate,
    _: SuperAdmin,
    db: AsyncSession = Depends(get_db),
):
    return await service.create_user(db, data)


@router.get("/me/companies")
async def my_companies(
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
):
    from sqlalchemy import select
    from sqlalchemy.orm import selectinload
    from app.modules.users.models import UserCompanyRole

    result = await db.execute(
        select(UserCompanyRole)
        .where(
            UserCompanyRole.user_id == current_user.id,
            UserCompanyRole.is_active == True,
        )
        .options(selectinload(UserCompanyRole.company))
    )
    roles = result.scalars().all()
    return [
        {"company_id": str(r.company_id), "company_name": r.company.name, "role": r.role}
        for r in roles
    ]


@router.get("/{user_id}/companies", response_model=list[UserCompanyRoleResponse])
async def get_user_companies(
    user_id: uuid.UUID,
    _: SuperAdmin,
    db: AsyncSession = Depends(get_db),
):
    return await service.list_company_users_by_user(db, user_id)


@router.get("/{user_id}", response_model=UserResponse)
async def get_user(
    user_id: uuid.UUID,
    _: SuperAdmin,
    db: AsyncSession = Depends(get_db),
):
    return await service.get_user_or_404(db, user_id)


@router.patch("/{user_id}", response_model=UserResponse)
async def update_user(
    user_id: uuid.UUID,
    data: UserUpdate,
    _: SuperAdmin,
    db: AsyncSession = Depends(get_db),
):
    return await service.update_user(db, user_id, data)


@router.post("/me/change-password")
async def change_password(
    data: ChangePasswordRequest,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
):
    await service.change_password(db, current_user, data.current_password, data.new_password)
    return {"message": "Contraseña actualizada exitosamente"}


# ── Usuarios por empresa ─────────────────────────────────────────────────────

company_router = APIRouter(prefix="/companies/{company_id}/users", tags=["Company Users"])


@company_router.get("", response_model=list[UserCompanyRoleResponse])
async def list_company_users(
    company_id: uuid.UUID,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
):
    if not current_user.is_superadmin:
        await service.assert_user_belongs_to_company(db, current_user.id, company_id)
    return await service.list_company_users(db, company_id)


@company_router.post("", response_model=UserCompanyRoleResponse, status_code=201)
async def assign_user(
    company_id: uuid.UUID,
    data: AssignUserToCompanyRequest,
    _: SuperAdmin,
    db: AsyncSession = Depends(get_db),
):
    return await service.assign_user_to_company(db, company_id, data)


@company_router.post("/create", response_model=UserCompanyRoleResponse, status_code=201)
async def create_user_for_company(
    company_id: uuid.UUID,
    data: CreateUserForCompanyRequest,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
):
    """Admin or superadmin — creates a new user and assigns them to the company."""
    if not current_user.is_superadmin:
        requester_role = await service.get_user_role_in_company(db, current_user.id, company_id)
        if requester_role != "admin":
            raise ForbiddenError("Solo los administradores pueden crear usuarios")
    else:
        requester_role = "superadmin"

    return await service.create_user_for_company(db, company_id, data, requester_role)


@company_router.patch("/{user_id}/role", response_model=UserCompanyRoleResponse)
async def change_user_role(
    company_id: uuid.UUID,
    user_id: uuid.UUID,
    data: ChangeRoleRequest,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
):
    """Admin or superadmin — change a user's role within the company."""
    requester_role = None
    if not current_user.is_superadmin:
        requester_role = await service.get_user_role_in_company(db, current_user.id, company_id)
        if requester_role != "admin":
            raise ForbiddenError("Solo los administradores pueden cambiar roles")
    return await service.change_user_role_in_company(db, company_id, user_id, data.role, requester_role)


@company_router.delete("/{user_id}", status_code=204)
async def remove_user(
    company_id: uuid.UUID,
    user_id: uuid.UUID,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
):
    if not current_user.is_superadmin:
        requester_role = await service.get_user_role_in_company(db, current_user.id, company_id)
        if requester_role != "admin":
            raise ForbiddenError("Solo los administradores pueden remover usuarios")
    await service.remove_user_from_company(db, company_id, user_id)
