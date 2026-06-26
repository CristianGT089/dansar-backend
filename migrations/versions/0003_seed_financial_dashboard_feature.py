"""Seed financial dashboard feature

Revision ID: 0003
Revises: 0002
Create Date: 2026-06-26
"""
from typing import Sequence, Union
import uuid
from datetime import datetime, timezone

from alembic import op
import sqlalchemy as sa

revision: str = "0003"
down_revision: Union[str, None] = "0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

NOW = datetime.now(timezone.utc)


def upgrade() -> None:
    op.execute(f"""
        INSERT INTO features (id, key, name, description, module, created_at, updated_at)
        VALUES ('{uuid.uuid4()}', 'financial_dashboard', 'Dashboard Financiero', NULL, 'financial', '{NOW}', '{NOW}')
        ON CONFLICT (key) DO NOTHING
    """)


def downgrade() -> None:
    op.execute("DELETE FROM features WHERE key = 'financial_dashboard'")
