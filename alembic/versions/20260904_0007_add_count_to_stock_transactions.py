"""add count to stock transactions

Revision ID: 20260904_0007
Revises: 20260904_0006
Create Date: 2026-09-04
"""

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.

revision = "20260904_0007"
down_revision = "20260904_0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "stock_transactions",
        sa.Column("count", sa.Integer(), nullable=True),
    )
    op.add_column(
        "stock_transactions",
        sa.Column("previous_count", sa.Integer(), nullable=True),
    )
    op.add_column(
        "stock_transactions",
        sa.Column("new_count", sa.Integer(), nullable=True),
    )
    op.create_check_constraint(
        "stock_count_nonzero",
        "stock_transactions",
        "count IS NULL OR count != 0",
    )
    op.create_check_constraint(
        "stock_previous_count_nonnegative",
        "stock_transactions",
        "previous_count IS NULL OR previous_count >= 0",
    )
    op.create_check_constraint(
        "stock_new_count_nonnegative",
        "stock_transactions",
        "new_count IS NULL OR new_count >= 0",
    )


def downgrade() -> None:
    op.drop_constraint(
        "stock_new_count_nonnegative",
        "stock_transactions",
        type_="check",
    )
    op.drop_constraint(
        "stock_previous_count_nonnegative",
        "stock_transactions",
        type_="check",
    )
    op.drop_constraint(
        "stock_count_nonzero",
        "stock_transactions",
        type_="check",
    )
    op.drop_column("stock_transactions", "new_count")
    op.drop_column("stock_transactions", "previous_count")
    op.drop_column("stock_transactions", "count")
