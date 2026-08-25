"""Simplify products for the mobile Alpha workflow.

Revision ID: 20260821_0002
Revises: 20260820_0001
Create Date: 2026-08-21
"""

import sqlalchemy as sa

from alembic import op

revision = "20260821_0002"
down_revision = "20260820_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("products", sa.Column("brand", sa.String(length=120), nullable=True))
    op.add_column("products", sa.Column("image_url", sa.String(length=500), nullable=True))
    op.execute("UPDATE products SET brand = 'Alfateks' WHERE brand IS NULL OR btrim(brand) = ''")
    op.execute("UPDATE products SET color = 'Unknown' WHERE color IS NULL OR btrim(color) = ''")
    op.execute(
        "UPDATE products SET lot_number = product_code "
        "WHERE lot_number IS NULL OR btrim(lot_number) = ''"
    )
    op.execute("UPDATE products SET unit = 'kg'")
    op.execute(
        "UPDATE products SET barcode = product_code WHERE barcode IS NULL OR btrim(barcode) = ''"
    )
    op.alter_column("products", "brand", nullable=False)
    op.alter_column("products", "color", nullable=False)
    op.alter_column("products", "lot_number", nullable=False)
    op.alter_column("products", "barcode", nullable=False)
    op.alter_column("products", "unit", server_default="kg", existing_type=sa.String(20))
    op.create_check_constraint("ck_products_unit_kg_only", "products", "unit = 'kg'")
    op.create_index(op.f("ix_products_brand"), "products", ["brand"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_products_brand"), table_name="products")
    op.drop_constraint("ck_products_unit_kg_only", "products", type_="check")
    op.alter_column("products", "unit", server_default="meter", existing_type=sa.String(20))
    op.alter_column("products", "barcode", nullable=True)
    op.alter_column("products", "lot_number", nullable=True)
    op.alter_column("products", "color", nullable=True)
    op.drop_column("products", "image_url")
    op.drop_column("products", "brand")
