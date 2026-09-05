"""add count to products

Revision ID: 20260904_0006
Revises: 20260825_0005
Create Date: 2026-09-04
"""

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.

revision = "20260904_0006"
down_revision = "20260825_0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "products",
        sa.Column(
            "count",
            sa.Integer(),
            nullable=True,
        ),
    )


def downgrade() -> None:
    op.drop_column("products", "count")
