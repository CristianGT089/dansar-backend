from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.modules.auth.dependencies import SuperAdmin
from app.modules.companies.models import Company, CompanyStatus
from app.modules.users.models import User

router = APIRouter(prefix="/admin", tags=["Admin"])


@router.get("/dashboard")
async def dashboard(
    _: SuperAdmin,
    db: AsyncSession = Depends(get_db),
):
    total_companies = (await db.execute(select(func.count()).select_from(Company))).scalar_one()
    active_companies = (
        await db.execute(
            select(func.count()).select_from(Company).where(Company.is_active == True)
        )
    ).scalar_one()
    total_users = (await db.execute(select(func.count()).select_from(User))).scalar_one()
    active_users = (
        await db.execute(
            select(func.count()).select_from(User).where(User.is_active == True)
        )
    ).scalar_one()

    return {
        "companies": {
            "total": total_companies,
            "active": active_companies,
            "inactive": total_companies - active_companies,
        },
        "users": {
            "total": total_users,
            "active": active_users,
            "inactive": total_users - active_users,
        },
    }
