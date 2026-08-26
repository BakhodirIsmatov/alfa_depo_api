"""make product descriptive fields optional

Revision ID: 20260825_0005
Revises: 20260824_0004
Create Date: 2026-08-25
"""

import sqlalchemy as sa
from alembic import op


revision = "20260825_0005"
down_revision = "20260824_0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column("products", "description", existing_type=sa.Text(), nullable=True)
    op.alter_column("products", "brand", existing_type=sa.String(length=120), nullable=True)
    op.alter_column("products", "color", existing_type=sa.String(length=80), nullable=True)
    op.alter_column("products", "color_code", existing_type=sa.String(length=7), nullable=True)


def downgrade() -> None:
    op.execute(
        "UPDATE products SET description = name WHERE description IS NULL OR btrim(description) = ''"
    )
    op.execute(
        "UPDATE products SET brand = 'Alfateks' WHERE brand IS NULL OR btrim(brand) = ''"
    )
    op.execute(
        "UPDATE products SET color = 'Unknown' WHERE color IS NULL OR btrim(color) = ''"
    )
    op.execute(
        "UPDATE products SET color_code = '#808080' "
        "WHERE color_code IS NULL OR color_code !~ '^#[0-9A-Fa-f]{6}$'"
    )
    op.alter_column("products", "color_code", existing_type=sa.String(length=7), nullable=False)
    op.alter_column("products", "color", existing_type=sa.String(length=80), nullable=False)
    op.alter_column("products", "brand", existing_type=sa.String(length=120), nullable=False)
    op.alter_column("products", "description", existing_type=sa.Text(), nullable=False)
