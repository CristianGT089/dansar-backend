import uuid
from enum import Enum
from typing import Optional

from sqlalchemy import Boolean, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import JSON, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.shared.models import TimeStampedModel


class PlanType(str, Enum):
    basic = "basic"
    professional = "professional"
    enterprise = "enterprise"


class Plan(TimeStampedModel):
    __tablename__ = "plans"

    name: Mapped[str] = mapped_column(String(100), nullable=False)
    type: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    companies: Mapped[list["CompanyPlan"]] = relationship(back_populates="plan")


class Feature(TimeStampedModel):
    __tablename__ = "features"

    key: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=True)
    module: Mapped[str] = mapped_column(String(100), nullable=True)
    parent_key: Mapped[Optional[str]] = mapped_column(
        String(100), ForeignKey("features.key", ondelete="CASCADE"), nullable=True
    )

    children: Mapped[list["Feature"]] = relationship(
        "Feature", back_populates="parent", foreign_keys="Feature.parent_key"
    )
    parent: Mapped[Optional["Feature"]] = relationship(
        "Feature", back_populates="children", foreign_keys="Feature.parent_key", remote_side="Feature.key"
    )
    company_features: Mapped[list["CompanyFeature"]] = relationship(back_populates="feature")


class CompanyPlan(TimeStampedModel):
    __tablename__ = "company_plans"

    company_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, unique=True
    )
    plan_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("plans.id"), nullable=False
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    company: Mapped["Company"] = relationship(back_populates="plan")
    plan: Mapped["Plan"] = relationship(back_populates="companies")


class CompanyFeature(TimeStampedModel):
    __tablename__ = "company_features"

    company_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("companies.id", ondelete="CASCADE"), nullable=False
    )
    feature_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("features.id", ondelete="CASCADE"), nullable=False
    )
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    allowed_roles: Mapped[list] = mapped_column(JSON, default=list)

    company: Mapped["Company"] = relationship(back_populates="features")
    feature: Mapped["Feature"] = relationship(back_populates="company_features")
