import hashlib
import uuid

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    verify_password,
)
from sqlalchemy.orm import selectinload

from app.modules.auth.dependencies import CurrentUser
from app.modules.auth.schemas import (
    LoginRequest,
    MeResponse,
    RefreshRequest,
    TokenResponse,
    UserCompanyInfo,
)
from app.modules.companies.models import Company
from app.modules.plans.models import CompanyFeature
from app.modules.users.models import RefreshToken, User, UserCompanyRole
from app.shared.exceptions import UnauthorizedError

router = APIRouter(prefix="/auth", tags=["Auth"])


@router.post("/login", response_model=TokenResponse)
async def login(data: LoginRequest, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.email == data.email))
    user = result.scalar_one_or_none()

    if not user or not verify_password(data.password, user.hashed_password):
        raise UnauthorizedError("Credenciales incorrectas")

    if not user.is_active:
        raise UnauthorizedError("Usuario inactivo")

    access_token = create_access_token(str(user.id))
    refresh_token = create_refresh_token(str(user.id))

    token_hash = hashlib.sha256(refresh_token.encode()).hexdigest()
    db.add(RefreshToken(user_id=user.id, token_hash=token_hash))
    await db.commit()

    return TokenResponse(access_token=access_token, refresh_token=refresh_token)


@router.post("/refresh", response_model=TokenResponse)
async def refresh(data: RefreshRequest, db: AsyncSession = Depends(get_db)):
    payload = decode_token(data.refresh_token)
    if not payload or payload.get("type") != "refresh":
        raise UnauthorizedError("Refresh token inválido")

    token_hash = hashlib.sha256(data.refresh_token.encode()).hexdigest()
    result = await db.execute(
        select(RefreshToken).where(
            RefreshToken.token_hash == token_hash,
            RefreshToken.is_revoked == False,
        )
    )
    stored = result.scalar_one_or_none()
    if not stored:
        raise UnauthorizedError("Refresh token revocado o no encontrado")

    stored.is_revoked = True

    user_id = payload["sub"]
    new_access = create_access_token(user_id)
    new_refresh = create_refresh_token(user_id)

    new_hash = hashlib.sha256(new_refresh.encode()).hexdigest()
    db.add(RefreshToken(user_id=uuid.UUID(user_id), token_hash=new_hash))
    await db.commit()

    return TokenResponse(access_token=new_access, refresh_token=new_refresh)


@router.post("/logout")
async def logout(current_user: CurrentUser, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(RefreshToken).where(
            RefreshToken.user_id == current_user.id,
            RefreshToken.is_revoked == False,
        )
    )
    tokens = result.scalars().all()
    for token in tokens:
        token.is_revoked = True
    await db.commit()
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

        # Build set of enabled parent keys for fast lookup
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
                # Parent feature — include always if enabled
                active_features.append(feature.key)
            else:
                # Subfeature — include only if parent is enabled and role is allowed
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
