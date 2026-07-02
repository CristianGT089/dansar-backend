"""Seed módulo de contabilidad con árbol de features de 4 niveles

Revision ID: 0007
Revises: 0006
Create Date: 2026-07-01
"""
from typing import Sequence, Union
import uuid
from datetime import datetime, timezone

from alembic import op
import sqlalchemy as sa

revision: str = "0007"
down_revision: Union[str, None] = "0006"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

NOW = datetime.now(timezone.utc)


def _f(key: str, name: str, parent_key: str | None = None, description: str | None = None) -> dict:
    return {
        "id": str(uuid.uuid4()),
        "key": key,
        "name": name,
        "description": description,
        "module": "accounting",
        "parent_key": parent_key,
        "created_at": NOW,
        "updated_at": NOW,
    }


# Árbol de 4 niveles — orden importante: padres antes que hijos
FEATURES = [
    # Nivel 1 — raíz del módulo
    _f("accounting",
       "Contabilidad",
       description="Módulo principal de contabilidad"),

    # Nivel 2
    _f("accounting.reports",
       "Reportes",
       parent_key="accounting",
       description="Informes financieros y estados de cuenta"),
    _f("accounting.journal",
       "Asientos contables",
       parent_key="accounting",
       description="Registro y aprobación de movimientos contables"),
    _f("accounting.settings",
       "Configuración contable",
       parent_key="accounting",
       description="Parametrización del módulo contable"),

    # Nivel 3 — hijos de accounting.reports
    _f("accounting.reports.pyg",
       "Estado de resultados (P&G)",
       parent_key="accounting.reports",
       description="Pérdidas y ganancias por período"),
    _f("accounting.reports.ledger",
       "Libro mayor",
       parent_key="accounting.reports",
       description="Movimientos por cuenta contable"),

    # Nivel 3 — hijos de accounting.journal
    _f("accounting.journal.create",
       "Crear asientos",
       parent_key="accounting.journal",
       description="Registrar nuevos asientos contables"),
    _f("accounting.journal.approve",
       "Aprobar asientos",
       parent_key="accounting.journal",
       description="Validar y aprobar asientos pendientes"),

    # Nivel 3 — hijo de accounting.settings
    _f("accounting.settings.chart_of_accounts",
       "Plan de cuentas",
       parent_key="accounting.settings",
       description="Gestión del catálogo de cuentas contables"),

    # Nivel 4 — hijos de accounting.reports.pyg
    _f("accounting.reports.pyg.quarterly",
       "P&G por trimestres",
       parent_key="accounting.reports.pyg",
       description="Vista trimestral del estado de resultados"),
    _f("accounting.reports.pyg.annual",
       "P&G anual",
       parent_key="accounting.reports.pyg",
       description="Resumen anual consolidado de pérdidas y ganancias"),

    # Nivel 4 — hijos de accounting.reports.ledger
    _f("accounting.reports.ledger.summary",
       "Libro mayor resumido",
       parent_key="accounting.reports.ledger",
       description="Saldos por cuenta sin detalle de movimientos"),
    _f("accounting.reports.ledger.detail",
       "Libro mayor detallado",
       parent_key="accounting.reports.ledger",
       description="Movimiento completo por cuenta con fechas y referencias"),
]


def upgrade() -> None:
    features_table = sa.table(
        "features",
        sa.column("id", sa.String),
        sa.column("key", sa.String),
        sa.column("name", sa.String),
        sa.column("description", sa.String),
        sa.column("module", sa.String),
        sa.column("parent_key", sa.String),
        sa.column("created_at", sa.DateTime),
        sa.column("updated_at", sa.DateTime),
    )
    op.bulk_insert(features_table, FEATURES)


def downgrade() -> None:
    op.execute("""
        DELETE FROM features
        WHERE key LIKE 'accounting%'
    """)
