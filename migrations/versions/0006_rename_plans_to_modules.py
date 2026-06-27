"""Rename plans/company_plans tables to modules/company_modules

Revision ID: 0006
Revises: 0005
Create Date: 2026-06-27
"""
from typing import Sequence, Union

from alembic import op

revision: str = "0006"
down_revision: Union[str, None] = "0005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.rename_table("plans", "modules")
    op.rename_table("company_plans", "company_modules")

    # Update FK constraint name on company_modules (rename reflects new table name)
    op.execute("ALTER TABLE company_modules RENAME CONSTRAINT company_plans_company_id_fkey TO company_modules_company_id_fkey")
    op.execute("ALTER TABLE company_modules RENAME CONSTRAINT company_plans_plan_id_fkey TO company_modules_module_id_fkey")

    # Rename column plan_id → module_id in company_modules
    op.alter_column("company_modules", "plan_id", new_column_name="module_id")

    # Add index on features.parent_key if not already present
    op.create_index("ix_features_parent_key", "features", ["parent_key"])


def downgrade() -> None:
    op.drop_index("ix_features_parent_key", "features")
    op.alter_column("company_modules", "module_id", new_column_name="plan_id")
    op.execute("ALTER TABLE company_modules RENAME CONSTRAINT company_modules_module_id_fkey TO company_plans_plan_id_fkey")
    op.execute("ALTER TABLE company_modules RENAME CONSTRAINT company_modules_company_id_fkey TO company_plans_company_id_fkey")
    op.rename_table("company_modules", "company_plans")
    op.rename_table("modules", "plans")
