"""Seed planes y features base

Revision ID: 0002
Revises: 0001
Create Date: 2026-06-10
"""
from typing import Sequence, Union
import uuid
from datetime import datetime, timezone

from alembic import op
import sqlalchemy as sa

revision: str = "0002"
down_revision: Union[str, None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

NOW = datetime.now(timezone.utc)

PLANS = [
    {"id": str(uuid.uuid4()), "name": "Básico", "type": "basic", "description": "Funcionalidades esenciales"},
    {"id": str(uuid.uuid4()), "name": "Profesional", "type": "professional", "description": "Funcionalidades avanzadas"},
    {"id": str(uuid.uuid4()), "name": "Empresarial", "type": "enterprise", "description": "Todas las funcionalidades"},
]

FEATURES = [
    # Módulo: Usuarios
    {"key": "users.manage", "name": "Gestión de usuarios", "module": "users"},
    {"key": "users.roles", "name": "Gestión de roles", "module": "users"},
    # Módulo: Contabilidad (fase 2+)
    {"key": "accounting.chart_of_accounts", "name": "Plan de cuentas", "module": "accounting"},
    {"key": "accounting.journal_entries", "name": "Asientos contables", "module": "accounting"},
    {"key": "accounting.reports", "name": "Reportes contables", "module": "accounting"},
    # Módulo: Facturación (fase 2+)
    {"key": "billing.invoices", "name": "Facturación", "module": "billing"},
    {"key": "billing.electronic", "name": "Facturación electrónica DIAN", "module": "billing"},
    # Módulo: Archivos
    {"key": "files.upload", "name": "Subida de archivos", "module": "files"},
    {"key": "files.storage_extended", "name": "Almacenamiento extendido", "module": "files"},
]


def upgrade() -> None:
    plans_table = sa.table(
        "plans",
        sa.column("id", sa.String),
        sa.column("name", sa.String),
        sa.column("type", sa.String),
        sa.column("description", sa.String),
        sa.column("is_active", sa.Boolean),
        sa.column("created_at", sa.DateTime),
        sa.column("updated_at", sa.DateTime),
    )
    op.bulk_insert(plans_table, [
        {**p, "is_active": True, "created_at": NOW, "updated_at": NOW}
        for p in PLANS
    ])

    features_table = sa.table(
        "features",
        sa.column("id", sa.String),
        sa.column("key", sa.String),
        sa.column("name", sa.String),
        sa.column("description", sa.String),
        sa.column("module", sa.String),
        sa.column("created_at", sa.DateTime),
        sa.column("updated_at", sa.DateTime),
    )
    op.bulk_insert(features_table, [
        {
            "id": str(uuid.uuid4()),
            "key": f["key"],
            "name": f["name"],
            "description": None,
            "module": f["module"],
            "created_at": NOW,
            "updated_at": NOW,
        }
        for f in FEATURES
    ])


def downgrade() -> None:
    op.execute("DELETE FROM features")
    op.execute("DELETE FROM plans")
