import uuid
from typing import Optional

from pydantic import BaseModel

from app.modules.users.models import SystemRole


class ModuleResponse(BaseModel):
    id: uuid.UUID
    name: str
    type: str
    description: Optional[str]
    is_active: bool

    model_config = {"from_attributes": True}


class SubFeatureStatus(BaseModel):
    feature_id: str
    key: str
    name: str
    module: Optional[str]
    is_enabled: bool
    allowed_roles: list[str]


class FeatureStatus(BaseModel):
    feature_id: str
    key: str
    name: str
    module: Optional[str]
    is_enabled: bool
    children: list[SubFeatureStatus] = []


class CompanyFeaturesResponse(BaseModel):
    company_id: uuid.UUID
    features: list[FeatureStatus]


class FeatureResponse(BaseModel):
    id: uuid.UUID
    key: str
    name: str
    description: Optional[str]
    module: Optional[str]
    parent_key: Optional[str] = None

    model_config = {"from_attributes": True}


class FeatureCreate(BaseModel):
    key: str
    name: str
    description: Optional[str] = None
    module: Optional[str] = None
    parent_key: Optional[str] = None


class ToggleFeatureRequest(BaseModel):
    feature_key: str
    enabled: bool


class ToggleSubfeatureRequest(BaseModel):
    enabled: bool


class SetFeatureRolesRequest(BaseModel):
    roles: list[SystemRole]


class AssignModuleRequest(BaseModel):
    module_type: str
