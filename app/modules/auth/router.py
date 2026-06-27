from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.modules.auth import service as auth_service
from app.modules.auth.dependencies import CurrentUser
from app.modules.auth.schemas import (
    LoginRequest,
    MeResponse,
    RefreshRequest,
    TokenResponse,
    UserCompanyInfo,
)
from app.modules.catalog import service as catalog_service
from app.modules.users.models import UserCompanyRole

router = APIRouter(prefix="/auth", tags=["Auth"])


@router.post("/login", response_model=TokenResponse)
async def login(data: LoginRequest, db: AsyncSession = Depends(get_db)):
    tokens = await auth_service.login(db, data.email, data.password)
    return TokenResponse(**tokens)


@router.post("/refresh", response_model=TokenResponse)
async def refresh(data: RefreshRequest, db: AsyncSession = Depends(get_db)):
    tokens = await auth_service.refresh(db, data.refresh_token)
    return TokenResponse(**tokens)


@router.post("/logout")
async def logout(current_user: CurrentUser, db: AsyncSession = Depends(get_db)):
    await auth_service.logout(db, current_user.id)
    return {"message": "Sesión cerrada exitosamente"}


@router.get("/me", response_model=MeResponse)
async def get_me(current_user: CurrentUser, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(UserCompanyRole)
        .where(
            UserCompanyRole.user_id == current_user.id,
            UserCompanyRole.is_active == True,
        )
    )
    memberships = result.scalars().all()

    companies = []
    for m in memberships:
        # Lazy-load company to check is_active
        from app.modules.companies.models import Company
        co_result = await db.execute(
            select(Company).where(Company.id == m.company_id, Company.is_active == True)
        )
        company = co_result.scalar_one_or_none()
        if not company:
            continue

        active_features = await catalog_service.get_accessible_features(
            db, m.company_id, m.role
        )

        companies.append(UserCompanyInfo(
            id=str(company.id),
            name=company.name,
            role=m.role,
            features=active_features,
        ))

    return MeResponse(
        id=str(current_user.id),
        email=current_user.email,
        full_name=current_user.full_name,
        is_superadmin=current_user.is_superadmin,
        companies=companies,
    )
