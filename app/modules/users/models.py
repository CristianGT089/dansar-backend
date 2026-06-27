import uuid
from enum import Enum

from sqlalchemy import Boolean, ForeignKey, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.shared.models import TimeStampedModel


class SystemRole(str, Enum):
    superadmin = "superadmin"
    admin = "admin"
    contador = "contador"
    viewer = "viewer"


class User(TimeStampedModel):
    __tablename__ = "users"

    email: Mapped[str] = mapped_column(String(200), nullable=False, unique=True, index=True)
    full_name: Mapped[str] = mapped_column(String(200), nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(200), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    is_superadmin: Mapped[bool] = mapped_column(Boolean, default=False)

    # Relationships
    company_roles: Mapped[list["UserCompanyRole"]] = relationship(back_populates="user")
    refresh_tokens: Mapped[list["RefreshToken"]] = relationship(back_populates="user")


class UserCompanyRole(TimeStampedModel):
    __tablename__ = "user_company_roles"
    __table_args__ = (UniqueConstraint("user_id", "company_id", name="uq_user_company_roles_user_company"),)

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    company_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("companies.id", ondelete="CASCADE"), nullable=False
    )
    role: Mapped[str] = mapped_column(String(50), default=SystemRole.viewer)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    user: Mapped["User"] = relationship(back_populates="company_roles")
    company: Mapped["Company"] = relationship(back_populates="user_roles")


class RefreshToken(TimeStampedModel):
    __tablename__ = "refresh_tokens"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    token_hash: Mapped[str] = mapped_column(String(200), nullable=False, unique=True)
    is_revoked: Mapped[bool] = mapped_column(Boolean, default=False)

    user: Mapped["User"] = relationship(back_populates="refresh_tokens")
