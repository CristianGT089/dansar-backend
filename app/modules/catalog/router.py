import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.modules.auth.dependencies import CurrentUser, SuperAdmin
from app.modules.catalog import service
from app.modules.catalog.schemas import (
    AssignModuleRequest,
    CompanyFeaturesResponse,
    FeatureCreate,
    FeatureResponse,
    ModuleResponse,
    SetFeatureRolesRequest,
    ToggleFeatureRequest,
    ToggleSubfeatureRequest,
)
from app.modules.users.models import SystemRole
from app.modules.users.service import assert_user_belongs_to_company, get_user_role_in_company
from app.shared.exceptions import ForbiddenError

router = APIRouter(prefix="/modules", tags=["Modules"])


@router.get("", response_model=list[ModuleResponse])
async def list_modules(
    _: CurrentUser,
    db: AsyncSession = Depends(get_db),
):
    return await service.list_modules(db)


@router.get("/features", response_model=list[FeatureResponse])
async def list_features(
    _: CurrentUser,
    db: AsyncSession = Depends(get_db),
):
    return await service.list_features(db)


@router.post("/features", response_model=FeatureResponse, status_code=201)
async def create_feature(
    data: FeatureCreate,
    _: SuperAdmin,
    db: AsyncSession = Depends(get_db),
):
    return await service.create_feature(db, data.key, data.name, data.description, data.module, data.parent_key)


# ── Features por empresa ──────────────────────────────────────────────────────

company_modules_router = APIRouter(prefix="/companies/{company_id}/module", tags=["Company Modules"])


@company_modules_router.get("", response_model=CompanyFeaturesResponse)
async def get_company_features(
    company_id: uuid.UUID,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
):
    if not current_user.is_superadmin:
        await assert_user_belongs_to_company(db, current_user.id, company_id)
    features = await service.get_company_features(db, company_id)
    return CompanyFeaturesResponse(company_id=company_id, features=features)


@company_modules_router.post("/assign")
async def assign_module(
    company_id: uuid.UUID,
    data: AssignModuleRequest,
    _: SuperAdmin,
    db: AsyncSession = Depends(get_db),
):
    cm = await service.assign_module_to_company(db, company_id, data.module_type)
    return {"company_id": str(company_id), "module_id": str(cm.module_id), "is_active": cm.is_active}


@company_modules_router.post("/features/toggle")
async def toggle_feature(
    company_id: uuid.UUID,
    data: ToggleFeatureRequest,
    _: SuperAdmin,
    db: AsyncSession = Depends(get_db),
):
    return await service.toggle_feature(db, company_id, data.feature_key, data.enabled)


@company_modules_router.patch("/features/{feature_key}/toggle")
async def toggle_subfeature(
    company_id: uuid.UUID,
    feature_key: str,
    data: ToggleSubfeatureRequest,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
):
    if not current_user.is_superadmin:
        await assert_user_belongs_to_company(db, current_user.id, company_id)
        role = await get_user_role_in_company(db, current_user.id, company_id)
        if role != SystemRole.admin:
            raise ForbiddenError("Solo los administradores pueden modificar funcionalidades")
    return await service.toggle_subfeature(db, company_id, feature_key, data.enabled)


@company_modules_router.patch("/features/{feature_key}/roles")
async def set_feature_roles(
    company_id: uuid.UUID,
    feature_key: str,
    data: SetFeatureRolesRequest,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
):
    if not current_user.is_superadmin:
        await assert_user_belongs_to_company(db, current_user.id, company_id)
        role = await get_user_role_in_company(db, current_user.id, company_id)
        if role != SystemRole.admin:
            raise ForbiddenError("Solo los administradores pueden modificar roles de funcionalidades")
    return await service.set_feature_roles(db, company_id, feature_key, data.roles)
