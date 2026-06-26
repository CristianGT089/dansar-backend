"""Feature hierarchy and role-based access

Revision ID: 0004
Revises: 0003
Create Date: 2026-06-26
"""
from typing import Sequence, Union
import uuid
from datetime import datetime, timezone

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSON

revision: str = "0004"
down_revision: Union[str, None] = "0003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

NOW = datetime.now(timezone.utc)

SUBFEATURES = [
    {"key": "financial.charts",       "name": "Gráficas",     "module": "financial", "parent_key": "financial_dashboard"},
    {"key": "financial.kpis",         "name": "KPIs",         "module": "financial", "parent_key": "financial_dashboard"},
    {"key": "financial.libro_mayor",  "name": "Libro Mayor",  "module": "financial", "parent_key": "financial_dashboard"},
]


def upgrade() -> None:
    op.add_column("features", sa.Column("parent_key", sa.String(100), sa.ForeignKey("features.key", ondelete="CASCADE"), nullable=True))
    op.add_column("company_features", sa.Column("allowed_roles", JSON, nullable=False, server_default="[]"))

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
    op.bulk_insert(features_table, [
        {
            "id": str(uuid.uuid4()),
            "key": f["key"],
            "name": f["name"],
            "description": None,
            "module": f["module"],
            "parent_key": f["parent_key"],
            "created_at": NOW,
            "updated_at": NOW,
        }
        for f in SUBFEATURES
    ])


def downgrade() -> None:
    op.execute("DELETE FROM features WHERE key IN ('financial.charts', 'financial.kpis', 'financial.libro_mayor')")
    op.drop_column("company_features", "allowed_roles")
    op.drop_column("features", "parent_key")
