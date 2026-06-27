"""Add unique constraints to user_company_roles and company_features

Revision ID: 0005
Revises: 0004
Create Date: 2026-06-27
"""
from typing import Sequence, Union

from alembic import op

revision: str = "0005"
down_revision: Union[str, None] = "0004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Remove duplicate rows before adding constraint (keep newest by id)
    op.execute("""
        DELETE FROM user_company_roles a
        USING user_company_roles b
        WHERE a.id < b.id
          AND a.user_id = b.user_id
          AND a.company_id = b.company_id
    """)
    op.create_unique_constraint(
        "uq_user_company_roles_user_company",
        "user_company_roles",
        ["user_id", "company_id"],
    )

    op.execute("""
        DELETE FROM company_features a
        USING company_features b
        WHERE a.id < b.id
          AND a.company_id = b.company_id
          AND a.feature_id = b.feature_id
    """)
    op.create_unique_constraint(
        "uq_company_features_company_feature",
        "company_features",
        ["company_id", "feature_id"],
    )


def downgrade() -> None:
    op.drop_constraint("uq_company_features_company_feature", "company_features", type_="unique")
    op.drop_constraint("uq_user_company_roles_user_company", "user_company_roles", type_="unique")
