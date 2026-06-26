import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.modules.auth.dependencies import get_current_user
from app.modules.plans import service as plans_service
from app.modules.users.service import assert_user_belongs_to_company, get_user_role_in_company
from app.shared.exceptions import ForbiddenError

from . import service
from .schemas import (
    CategorySalesResponse,
    LibroResponse,
    MetaResponse,
)

router = APIRouter(prefix="/companies/{company_id}/financial", tags=["Financial"])


def _require_feature(feature_key: str):
    """Factory that returns a FastAPI dependency checking a specific feature + role."""
    async def dependency(
        company_id: uuid.UUID,
        current_user: Annotated[object, Depends(get_current_user)],
        db: Annotated[AsyncSession, Depends(get_db)],
    ):
        if current_user.is_superadmin:
            return

        await assert_user_belongs_to_company(db, current_user.id, company_id)
        role = await get_user_role_in_company(db, current_user.id, company_id)

        has_access = await plans_service.check_feature_access(db, company_id, feature_key, role)
        if not has_access:
            raise ForbiddenError(f"No tienes acceso a esta funcionalidad ({feature_key})")

    return dependency


ChartsAccess = Annotated[None, Depends(_require_feature("financial.charts"))]
KpisAccess = Annotated[None, Depends(_require_feature("financial.kpis"))]
LibroAccess = Annotated[None, Depends(_require_feature("financial.libro_mayor"))]


@router.get("/meta", response_model=MetaResponse)
async def get_meta(_: KpisAccess):
    return service.get_meta()


@router.get("/pyg/mensual")
async def pyg_mensual(
    _: ChartsAccess,
    year_a: int = Query(2024),
    year_b: int = Query(2026),
):
    periods = [
        (year_a, "M01", f"{year_a}_M01"),
        (year_a, "M02", f"{year_a}_M02"),
        (year_a, "M03", f"{year_a}_M03"),
        (year_a, "M04", f"{year_a}_M04"),
        (year_a, "M05", f"{year_a}_M05"),
        (year_a, "M06", f"{year_a}_M06"),
        (year_a, "M07", f"{year_a}_M07"),
        (year_a, "M08", f"{year_a}_M08"),
        (year_a, "M09", f"{year_a}_M09"),
        (year_a, "M10", f"{year_a}_M10"),
        (year_a, "M11", f"{year_a}_M11"),
        (year_a, "M12", f"{year_a}_M12"),
        (year_b, "M01", f"{year_b}_M01"),
        (year_b, "M02", f"{year_b}_M02"),
        (year_b, "M03", f"{year_b}_M03"),
        (year_b, "M04", f"{year_b}_M04"),
        (year_b, "M05", f"{year_b}_M05"),
        (year_b, "M06", f"{year_b}_M06"),
    ]
    rows = service.build_pyg_rows(periods)
    cols_a = [f"{year_a}_M{m:02d}" for m in range(1, 13)]
    cols_b = [f"{year_b}_M{m:02d}" for m in range(1, 7)]
    delta_pairs = [(f"{year_a}_M{m:02d}", f"{year_b}_M{m:02d}", f"delta_M{m:02d}")
                   for m in range(1, 7)]
    rows = service.add_deltas(rows, delta_pairs)

    MESES = {1:"Ene",2:"Feb",3:"Mar",4:"Abr",5:"May",6:"Jun",7:"Jul",8:"Ago",9:"Sep",10:"Oct",11:"Nov",12:"Dic"}
    columns = (
        [{"key": f"{year_a}_M{m:02d}", "label": MESES[m], "year": year_a, "type": "data"} for m in range(1, 13)] +
        [{"key": f"{year_b}_M{m:02d}", "label": MESES[m], "year": year_b, "type": "data"} for m in range(1, 7)] +
        [{"key": f"delta_M{m:02d}", "label": f"Δ{MESES[m]}", "year": None, "type": "delta"} for m in range(1, 7)]
    )
    return {"columns": columns, "rows": rows, "year_a": year_a, "year_b": year_b}


@router.get("/pyg/trimestral")
async def pyg_trimestral(
    _: ChartsAccess,
    year_a: int = Query(2024),
    year_b: int = Query(2025),
):
    periods = [
        (year_a, "Q1", f"{year_a}_Q1"), (year_a, "Q2", f"{year_a}_Q2"),
        (year_a, "Q3", f"{year_a}_Q3"), (year_a, "Q4", f"{year_a}_Q4"),
        (year_b, "Q1", f"{year_b}_Q1"), (year_b, "Q2", f"{year_b}_Q2"),
        (year_b, "Q3", f"{year_b}_Q3"), (year_b, "Q4", f"{year_b}_Q4"),
    ]
    rows = service.build_pyg_rows(periods)
    delta_pairs = [(f"{year_a}_Q{q}", f"{year_b}_Q{q}", f"delta_Q{q}") for q in range(1, 5)]
    rows = service.add_deltas(rows, delta_pairs)

    columns = (
        [{"key": f"{year_a}_Q{q}", "label": f"Q{q}", "year": year_a, "type": "data"} for q in range(1, 5)] +
        [{"key": f"{year_b}_Q{q}", "label": f"Q{q}", "year": year_b, "type": "data"} for q in range(1, 5)] +
        [{"key": f"delta_Q{q}", "label": f"ΔQ{q}", "year": None, "type": "delta"} for q in range(1, 5)]
    )
    return {"columns": columns, "rows": rows, "year_a": year_a, "year_b": year_b}


@router.get("/kpis")
async def get_kpis(
    _: KpisAccess,
    year_a: int = Query(2024),
    year_b: int = Query(2026),
    period: str = Query("anual"),
):
    pk = "Q1" if period == "Q1" else "Q2" if period == "Q2" else "Q3" if period == "Q3" else "Q4" if period == "Q4" else "M01"
    if period == "anual":
        MESES_KEYS = [f"M{m:02d}" for m in range(1, 13)]
        def sum_period(year):
            rows = service.build_pyg_rows([(year, pk, "v") for pk in MESES_KEYS])
            return rows
    periods = [(year_a, "M06", f"{year_a}"), (year_b, "M06", f"{year_b}")]
    return service.get_kpis(periods)


@router.get("/cascade")
async def get_cascade(
    _: KpisAccess,
    year_a: int = Query(2024),
    year_b: int = Query(2026),
):
    df, _, pyg24, pyg25, lm_months_2026 = service.load_all() if False else (None,None,None,None,[])
    from .data import load_all, MESES
    df, _, pyg24, pyg25, lm_months_2026 = load_all()
    last_month = max(lm_months_2026) if lm_months_2026 else 6
    periods_a = [(year_a, f"M{m:02d}", f"M{m:02d}") for m in range(1, last_month + 1)]
    periods_b = [(year_b, f"M{m:02d}", f"M{m:02d}") for m in range(1, last_month + 1)]

    def sum_cascade(periods):
        kpis = service.get_kpis([(y, pk, lbl) for y, pk, lbl in periods])
        ing = sum(k["ingresos"] for k in kpis)
        ub  = sum(k["utilidad_bruta"] for k in kpis)
        mg  = round(ub / ing * 100, 1) if ing else 0
        return {"ingresos": ing, "utilidad_bruta": ub, "margen_bruta": mg}

    result_a = sum_cascade(periods_a)
    result_b = sum_cascade(periods_b)
    result_a["label"] = str(year_a)
    result_b["label"] = str(year_b)
    return [result_a, result_b]


@router.get("/charts/sales-trend")
async def sales_trend(_: ChartsAccess):
    return service.get_sales_trend()


@router.get("/charts/sales-mix")
async def sales_mix(_: ChartsAccess, year: int = Query(2024)):
    return service.get_sales_mix(year)


@router.get("/charts/quarterly-sales")
async def quarterly_sales(_: ChartsAccess):
    return service.get_quarterly_sales()


@router.get("/charts/category-sales", response_model=CategorySalesResponse)
async def category_sales(_: ChartsAccess):
    return service.get_category_sales_ytd()


@router.get("/libro", response_model=LibroResponse)
async def libro_mayor(
    _: LibroAccess,
    year: int | None = Query(None),
    month: int | None = Query(None),
    account: str | None = Query(None),
    cost_center: str | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
):
    return service.get_libro_mayor(year, month, account, cost_center, page, page_size)
