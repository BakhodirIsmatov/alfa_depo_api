"""Create Alpha users, products, and stock transactions.

Revision ID: 20260820_0001
Revises:
Create Date: 2026-08-20
"""

import sqlalchemy as sa

from alembic import op

revision = "20260820_0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("username", sa.String(length=50), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column("full_name", sa.String(length=120), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default="true", nullable=False),
        sa.Column("is_admin", sa.Boolean(), server_default="false", nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_users")),
    )
    op.create_index(op.f("ix_users_email"), "users", ["email"], unique=True)
    op.create_index(op.f("ix_users_username"), "users", ["username"], unique=True)

    op.create_table(
        "products",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("product_code", sa.String(length=32), nullable=False),
        sa.Column("name", sa.String(length=180), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("material", sa.String(length=120), nullable=True),
        sa.Column("composition", sa.String(length=255), nullable=True),
        sa.Column("color", sa.String(length=80), nullable=True),
        sa.Column("color_code", sa.String(length=32), nullable=True),
        sa.Column("width", sa.Numeric(precision=10, scale=2), nullable=True),
        sa.Column("gsm", sa.Numeric(precision=10, scale=2), nullable=True),
        sa.Column("unit", sa.String(length=20), server_default="meter", nullable=False),
        sa.Column("roll_number", sa.String(length=100), nullable=True),
        sa.Column("lot_number", sa.String(length=100), nullable=True),
        sa.Column("batch_number", sa.String(length=100), nullable=True),
        sa.Column("qr_code", sa.String(length=255), nullable=False),
        sa.Column("barcode", sa.String(length=255), nullable=True),
        sa.Column(
            "current_stock", sa.Numeric(precision=14, scale=3), server_default="0", nullable=False
        ),
        sa.Column(
            "minimum_stock", sa.Numeric(precision=14, scale=3), server_default="0", nullable=False
        ),
        sa.Column("created_by", sa.Integer(), nullable=False),
        sa.Column("updated_by", sa.Integer(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "minimum_stock >= 0", name=op.f("ck_products_minimum_stock_nonnegative")
        ),
        sa.ForeignKeyConstraint(
            ["created_by"],
            ["users.id"],
            name=op.f("fk_products_created_by_users"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["updated_by"],
            ["users.id"],
            name=op.f("fk_products_updated_by_users"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_products")),
    )
    op.create_index(op.f("ix_products_barcode"), "products", ["barcode"], unique=True)
    op.create_index(op.f("ix_products_color"), "products", ["color"], unique=False)
    op.create_index(op.f("ix_products_lot_number"), "products", ["lot_number"], unique=False)
    op.create_index(op.f("ix_products_name"), "products", ["name"], unique=False)
    op.create_index("ix_products_name_lower", "products", ["name"], unique=False)
    op.create_index(op.f("ix_products_product_code"), "products", ["product_code"], unique=True)
    op.create_index(op.f("ix_products_qr_code"), "products", ["qr_code"], unique=True)
    op.create_index(op.f("ix_products_roll_number"), "products", ["roll_number"], unique=False)

    transaction_type = sa.Enum("IN", "OUT", "ADJUSTMENT", name="stock_transaction_type")
    op.create_table(
        "stock_transactions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("product_id", sa.Integer(), nullable=False),
        sa.Column("transaction_type", transaction_type, nullable=False),
        sa.Column("quantity", sa.Numeric(precision=14, scale=3), nullable=False),
        sa.Column("previous_stock", sa.Numeric(precision=14, scale=3), nullable=False),
        sa.Column("new_stock", sa.Numeric(precision=14, scale=3), nullable=False),
        sa.Column("note", sa.String(length=500), nullable=True),
        sa.Column("created_by", sa.Integer(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["created_by"],
            ["users.id"],
            name=op.f("fk_stock_transactions_created_by_users"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["product_id"],
            ["products.id"],
            name=op.f("fk_stock_transactions_product_id_products"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_stock_transactions")),
    )
    op.create_index(
        op.f("ix_stock_transactions_created_at"), "stock_transactions", ["created_at"], unique=False
    )
    op.create_index(
        op.f("ix_stock_transactions_product_id"), "stock_transactions", ["product_id"], unique=False
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_stock_transactions_product_id"), table_name="stock_transactions")
    op.drop_index(op.f("ix_stock_transactions_created_at"), table_name="stock_transactions")
    op.drop_table("stock_transactions")
    sa.Enum(name="stock_transaction_type").drop(op.get_bind(), checkfirst=True)
    op.drop_index(op.f("ix_products_roll_number"), table_name="products")
    op.drop_index(op.f("ix_products_qr_code"), table_name="products")
    op.drop_index(op.f("ix_products_product_code"), table_name="products")
    op.drop_index("ix_products_name_lower", table_name="products")
    op.drop_index(op.f("ix_products_name"), table_name="products")
    op.drop_index(op.f("ix_products_lot_number"), table_name="products")
    op.drop_index(op.f("ix_products_color"), table_name="products")
    op.drop_index(op.f("ix_products_barcode"), table_name="products")
    op.drop_table("products")
    op.drop_index(op.f("ix_users_username"), table_name="users")
    op.drop_index(op.f("ix_users_email"), table_name="users")
    op.drop_table("users")
