import uuid
from typing import Annotated

from fastapi import Depends, Path
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import decode_token
from app.modules.users.models import User, SystemRole, UserCompanyRole
from app.shared.exceptions import UnauthorizedError, ForbiddenError

security = HTTPBearer()


async def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials, Depends(security)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> User:
    payload = decode_token(credentials.credentials)
    if not payload or payload.get("type") != "access":
        raise UnauthorizedError("Token inválido o expirado")

    user_id = payload.get("sub")
    result = await db.execute(select(User).where(User.id == uuid.UUID(user_id)))
    user = result.scalar_one_or_none()

    if not user or not user.is_active:
        raise UnauthorizedError("Usuario no encontrado o inactivo")

    return user


async def require_superadmin(
    current_user: Annotated[User, Depends(get_current_user)],
) -> User:
    if not current_user.is_superadmin:
        raise ForbiddenError("Se requieren permisos de superadministrador")
    return current_user


async def require_company_access(
    company_id: Annotated[uuid.UUID, Path()],
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> UserCompanyRole:
    if current_user.is_superadmin:
        from app.modules.companies.models import Company
        result = await db.execute(select(Company).where(Company.id == company_id, Company.is_active == True))
        company = result.scalar_one_or_none()
        if not company:
            raise ForbiddenError("Empresa no encontrada")
        return UserCompanyRole(user_id=current_user.id, company_id=company_id, role=SystemRole.superadmin)

    result = await db.execute(
        select(UserCompanyRole).where(
            UserCompanyRole.user_id == current_user.id,
            UserCompanyRole.company_id == company_id,
            UserCompanyRole.is_active == True,
        )
    )
    membership = result.scalar_one_or_none()
    if not membership:
        raise ForbiddenError("No tienes acceso a esta empresa")
    return membership


CurrentUser = Annotated[User, Depends(get_current_user)]
SuperAdmin = Annotated[User, Depends(require_superadmin)]
CompanyMember = Annotated[UserCompanyRole, Depends(require_company_access)]
