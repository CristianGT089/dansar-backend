import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.companies.models import Company, CompanyStatus
from app.modules.companies.schemas import CompanyCreate, CompanyUpdate
from app.shared.exceptions import ConflictError, NotFoundError


async def get_company_or_404(db: AsyncSession, company_id: uuid.UUID) -> Company:
    result = await db.execute(select(Company).where(Company.id == company_id))
    company = result.scalar_one_or_none()
    if not company:
        raise NotFoundError("Empresa")
    return company


async def list_companies(
    db: AsyncSession, page: int = 1, page_size: int = 20
) -> tuple[list[Company], int]:
    offset = (page - 1) * page_size
    total_result = await db.execute(select(func.count()).select_from(Company))
    total = total_result.scalar_one()
    result = await db.execute(select(Company).offset(offset).limit(page_size))
    return result.scalars().all(), total


async def create_company(db: AsyncSession, data: CompanyCreate) -> Company:
    if data.tax_id:
        existing = await db.execute(
            select(Company).where(Company.tax_id == data.tax_id)
        )
        if existing.scalar_one_or_none():
            raise ConflictError("Ya existe una empresa con ese NIT/tax_id")

    company = Company(**data.model_dump(exclude_none=True))
    db.add(company)
    await db.flush()
    await db.refresh(company)
    return company


async def update_company(
    db: AsyncSession, company_id: uuid.UUID, data: CompanyUpdate
) -> Company:
    company = await get_company_or_404(db, company_id)
    for field, value in data.model_dump(exclude_none=True).items():
        setattr(company, field, value)
    await db.flush()
    await db.refresh(company)
    return company


async def toggle_company_status(db: AsyncSession, company_id: uuid.UUID) -> Company:
    company = await get_company_or_404(db, company_id)
    company.is_active = not company.is_active
    company.status = CompanyStatus.active if company.is_active else CompanyStatus.inactive
    await db.flush()
    await db.refresh(company)
    return company
