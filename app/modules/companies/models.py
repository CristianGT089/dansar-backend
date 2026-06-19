import uuid
from enum import Enum

from sqlalchemy import Boolean, ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.shared.models import TimeStampedModel


class CompanyStatus(str, Enum):
    active = "active"
    inactive = "inactive"
    suspended = "suspended"


class Company(TimeStampedModel):
    __tablename__ = "companies"

    name: Mapped[str] = mapped_column(String(200), nullable=False)
    legal_name: Mapped[str] = mapped_column(String(200), nullable=True)
    tax_id: Mapped[str] = mapped_column(String(50), nullable=True, unique=True)
    email: Mapped[str] = mapped_column(String(200), nullable=True)
    phone: Mapped[str] = mapped_column(String(50), nullable=True)
    address: Mapped[str] = mapped_column(String(500), nullable=True)
    status: Mapped[str] = mapped_column(String(20), default=CompanyStatus.active)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    # Relationships
    user_roles: Mapped[list["UserCompanyRole"]] = relationship(back_populates="company")
    plan: Mapped["CompanyPlan"] = relationship(back_populates="company", uselist=False)
    features: Mapped[list["CompanyFeature"]] = relationship(back_populates="company")
