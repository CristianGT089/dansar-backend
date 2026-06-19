import uuid
from typing import Optional

from pydantic import BaseModel


class PlanResponse(BaseModel):
    id: uuid.UUID
    name: str
    type: str
    description: Optional[str]
    is_active: bool

    model_config = {"from_attributes": True}


class FeatureResponse(BaseModel):
    id: uuid.UUID
    key: str
    name: str
    description: Optional[str]
    module: Optional[str]

    model_config = {"from_attributes": True}


class FeatureCreate(BaseModel):
    key: str
    name: str
    description: Optional[str] = None
    module: Optional[str] = None


class CompanyFeaturesResponse(BaseModel):
    company_id: uuid.UUID
    features: list[dict]


class ToggleFeatureRequest(BaseModel):
    feature_key: str
    enabled: bool


class AssignPlanRequest(BaseModel):
    plan_type: str
