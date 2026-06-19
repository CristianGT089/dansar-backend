from pydantic import BaseModel
from typing import Any


class PygRow(BaseModel):
    label: str
    level: int
    values: dict[str, Any]


class PygResponse(BaseModel):
    columns: list[dict]
    rows: list[dict]


class KpiPeriod(BaseModel):
    label: str
    ingresos: float
    utilidad_bruta: float
    margen_bruto: float


class CascadePeriod(BaseModel):
    label: str
    ingresos: float
    utilidad_bruta: float
    utilidad_operacional: float
    utilidad_neta: float
    margen_bruta: float
    margen_operacional: float
    margen_neto: float


class SalesTrendPoint(BaseModel):
    mes: str
    v2024: float
    v2025: float
    v2026: float | None


class SalesMixItem(BaseModel):
    categoria: str
    valor: float


class QuarterlySalesItem(BaseModel):
    trimestre: str
    v2024: float
    v2025: float


class CategorySalesResponse(BaseModel):
    data: list[SalesMixItem]
    last_month: str


class LibroRecord(BaseModel):
    model_config = {"extra": "allow"}


class LibroResponse(BaseModel):
    total: int
    page: int
    page_size: int
    records: list[dict]
    centers: list[str]
    years: list[int]


class MetaResponse(BaseModel):
    lm_months_2026: list[str]
    pyg24_accounts: int
    pyg25_accounts: int
