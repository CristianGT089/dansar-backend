from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

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
from app.modules.catalog.models import CompanyFeature
from app.modules.companies.models import Company
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
        .options(
            selectinload(UserCompanyRole.company).selectinload(Company.features).selectinload(CompanyFeature.feature)
        )
    )
    memberships = result.scalars().all()

    companies = []
    for m in memberships:
        if not m.company or not m.company.is_active:
            continue

        enabled_parents = {
            cf.feature.key
            for cf in m.company.features
            if cf.is_enabled and cf.feature and cf.feature.parent_key is None
        }

        active_features = []
        for cf in m.company.features:
            if not cf.is_enabled or not cf.feature:
                continue
            feature = cf.feature
            if feature.parent_key is None:
                active_features.append(feature.key)
            else:
                if feature.parent_key in enabled_parents:
                    allowed = cf.allowed_roles or []
                    if not allowed or m.role in allowed:
                        active_features.append(feature.key)

        companies.append(UserCompanyInfo(
            id=str(m.company.id),
            name=m.company.name,
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
