import hashlib
import uuid

import structlog
from jose import JWTError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    verify_password,
)
from app.modules.users.models import RefreshToken, User
from app.shared.exceptions import UnauthorizedError

logger = structlog.get_logger()


async def login(db: AsyncSession, email: str, password: str) -> dict:
    result = await db.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()

    if not user or not verify_password(password, user.hashed_password):
        await logger.ainfo("user_login_failed", email=email, reason="bad_credentials")
        raise UnauthorizedError("Credenciales incorrectas")
    if not user.is_active:
        await logger.ainfo("user_login_failed", email=email, reason="inactive_user")
        raise UnauthorizedError("Usuario inactivo")

    access_token = create_access_token(str(user.id))
    refresh_token = create_refresh_token(str(user.id))

    token_hash = hashlib.sha256(refresh_token.encode()).hexdigest()
    db.add(RefreshToken(user_id=user.id, token_hash=token_hash))
    await db.commit()

    await logger.ainfo("user_login", user_id=str(user.id), email=user.email)
    return {"access_token": access_token, "refresh_token": refresh_token}


async def refresh(db: AsyncSession, refresh_token: str) -> dict:
    try:
        payload = decode_token(refresh_token)
    except JWTError:
        raise UnauthorizedError("Refresh token inválido")

    if payload.get("type") != "refresh":
        raise UnauthorizedError("Refresh token inválido")

    token_hash = hashlib.sha256(refresh_token.encode()).hexdigest()
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

    return {"access_token": new_access, "refresh_token": new_refresh}


async def logout(db: AsyncSession, user_id: uuid.UUID) -> None:
    result = await db.execute(
        select(RefreshToken).where(
            RefreshToken.user_id == user_id,
            RefreshToken.is_revoked == False,
        )
    )
    for token in result.scalars().all():
        token.is_revoked = True
    await db.commit()

    await logger.ainfo("user_logout", user_id=str(user_id))
