import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.modules.auth.dependencies import CurrentUser, SuperAdmin
from app.modules.companies import service
from app.modules.companies.schemas import (
    CompanyCreate,
    CompanyListResponse,
    CompanyResponse,
    CompanyUpdate,
)

router = APIRouter(prefix="/companies", tags=["Companies"])


@router.get("", response_model=CompanyListResponse)
async def list_companies(
    _: SuperAdmin,
    db: AsyncSession = Depends(get_db),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    items, total = await service.list_companies(db, page, page_size)
    return CompanyListResponse(items=items, total=total, page=page, page_size=page_size)


@router.post("", response_model=CompanyResponse, status_code=201)
async def create_company(
    data: CompanyCreate,
    _: SuperAdmin,
    db: AsyncSession = Depends(get_db),
):
    return await service.create_company(db, data)


@router.get("/{company_id}", response_model=CompanyResponse)
async def get_company(
    company_id: uuid.UUID,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
):
    from app.modules.users.service import assert_user_belongs_to_company
    if not current_user.is_superadmin:
        await assert_user_belongs_to_company(db, current_user.id, company_id)
    return await service.get_company_or_404(db, company_id)


@router.patch("/{company_id}", response_model=CompanyResponse)
async def update_company(
    company_id: uuid.UUID,
    data: CompanyUpdate,
    _: SuperAdmin,
    db: AsyncSession = Depends(get_db),
):
    return await service.update_company(db, company_id, data)


@router.post("/{company_id}/toggle-status", response_model=CompanyResponse)
async def toggle_status(
    company_id: uuid.UUID,
    _: SuperAdmin,
    db: AsyncSession = Depends(get_db),
):
    return await service.toggle_company_status(db, company_id)
