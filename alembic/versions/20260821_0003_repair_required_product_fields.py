"""Repair required product fields left nullable by the deployed 0002 migration.

Revision ID: 20260821_0003
Revises: 20260821_0002
Create Date: 2026-08-21
"""

import sqlalchemy as sa

from alembic import op

revision = "20260821_0003"
down_revision = "20260821_0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "UPDATE products SET color_code = '#808080' "
        "WHERE color_code IS NULL OR color_code !~ '^#[0-9A-Fa-f]{6}$'"
    )
    op.execute(
        "UPDATE products SET description = name "
        "WHERE description IS NULL OR btrim(description) = ''"
    )
    op.alter_column(
        "products",
        "color_code",
        nullable=False,
        type_=sa.String(length=7),
        existing_type=sa.String(length=32),
    )
    op.alter_column("products", "description", nullable=False)


def downgrade() -> None:
    # The repair is intentionally irreversible: restoring NULL values would break
    # the Alpha API contract. Revision 0002 remains compatible with stricter data.
    pass
