"""Add fixed RBAC, server sessions, immutable audit, and soft deletion.

Revision ID: 20260824_0004
Revises: 20260821_0003
Create Date: 2026-08-24
"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op
from app.core.permissions import (
    DEFAULT_ROLE_PERMISSIONS,
    PERMISSION_CATALOG,
    ROLE_NAMES,
    UserRole,
)

revision = "20260824_0004"
down_revision = "20260821_0003"
branch_labels = None
depends_on = None


def _timestamps() -> list[sa.Column]:
    return [
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
    ]


def upgrade() -> None:
    op.create_table(
        "roles",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("code", sa.String(length=32), nullable=False),
        sa.Column("name", sa.String(length=80), nullable=False),
        sa.Column("is_system", sa.Boolean(), server_default="true", nullable=False),
        sa.Column("version", sa.Integer(), server_default="1", nullable=False),
        *_timestamps(),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_roles")),
    )
    op.create_index(op.f("ix_roles_code"), "roles", ["code"], unique=True)

    op.create_table(
        "permissions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("code", sa.String(length=80), nullable=False),
        sa.Column("module", sa.String(length=40), nullable=False),
        sa.Column("description", sa.String(length=255), nullable=False),
        sa.Column("is_assignable", sa.Boolean(), server_default="true", nullable=False),
        *_timestamps(),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_permissions")),
    )
    op.create_index(op.f("ix_permissions_code"), "permissions", ["code"], unique=True)
    op.create_index(op.f("ix_permissions_module"), "permissions", ["module"], unique=False)

    roles_table = sa.table(
        "roles",
        sa.column("id", sa.Integer()),
        sa.column("code", sa.String()),
        sa.column("name", sa.String()),
        sa.column("is_system", sa.Boolean()),
        sa.column("version", sa.Integer()),
    )
    role_ids = {role: index for index, role in enumerate(UserRole, start=1)}
    op.bulk_insert(
        roles_table,
        [
            {
                "id": role_ids[role],
                "code": role.value,
                "name": ROLE_NAMES[role],
                "is_system": True,
                "version": 1,
            }
            for role in UserRole
        ],
    )

    permissions_table = sa.table(
        "permissions",
        sa.column("id", sa.Integer()),
        sa.column("code", sa.String()),
        sa.column("module", sa.String()),
        sa.column("description", sa.String()),
        sa.column("is_assignable", sa.Boolean()),
    )
    permission_ids = {
        definition.code: index for index, definition in enumerate(PERMISSION_CATALOG, start=1)
    }
    op.bulk_insert(
        permissions_table,
        [
            {
                "id": permission_ids[item.code],
                "code": item.code.value,
                "module": item.module,
                "description": item.description,
                "is_assignable": item.is_assignable,
            }
            for item in PERMISSION_CATALOG
        ],
    )
    op.execute(
        "SELECT setval(pg_get_serial_sequence('roles', 'id'), "
        "GREATEST((SELECT max(id) FROM roles), 1))"
    )
    op.execute(
        "SELECT setval(pg_get_serial_sequence('permissions', 'id'), "
        "GREATEST((SELECT max(id) FROM permissions), 1))"
    )

    op.add_column("users", sa.Column("role_id", sa.Integer(), nullable=True))
    op.add_column(
        "users", sa.Column("auth_version", sa.Integer(), server_default="1", nullable=False)
    )
    op.add_column("users", sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("users", sa.Column("last_activity_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("users", sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("users", sa.Column("deleted_by", sa.Integer(), nullable=True))
    op.execute(
        f"UPDATE users SET role_id = CASE WHEN is_admin THEN {role_ids[UserRole.ADMIN]} "
        f"ELSE {role_ids[UserRole.MANAGER]} END"
    )
    op.alter_column("users", "role_id", nullable=False)
    op.create_foreign_key(
        op.f("fk_users_role_id_roles"), "users", "roles", ["role_id"], ["id"], ondelete="RESTRICT"
    )
    op.create_foreign_key(
        op.f("fk_users_deleted_by_users"),
        "users",
        "users",
        ["deleted_by"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index(op.f("ix_users_role_id"), "users", ["role_id"], unique=False)
    op.create_index(op.f("ix_users_deleted_at"), "users", ["deleted_at"], unique=False)

    op.create_table(
        "role_permissions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("role_id", sa.Integer(), nullable=False),
        sa.Column("permission_id", sa.Integer(), nullable=False),
        sa.Column("granted_by", sa.Integer(), nullable=True),
        sa.Column(
            "granted_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["permission_id"],
            ["permissions.id"],
            name=op.f("fk_role_permissions_permission_id_permissions"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["role_id"],
            ["roles.id"],
            name=op.f("fk_role_permissions_role_id_roles"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["granted_by"],
            ["users.id"],
            name=op.f("fk_role_permissions_granted_by_users"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_role_permissions")),
        sa.UniqueConstraint("role_id", "permission_id", name=op.f("uq_role_permissions_role_id")),
    )
    op.create_index(op.f("ix_role_permissions_role_id"), "role_permissions", ["role_id"])
    op.create_index(
        op.f("ix_role_permissions_permission_id"), "role_permissions", ["permission_id"]
    )
    role_permissions_table = sa.table(
        "role_permissions",
        sa.column("role_id", sa.Integer()),
        sa.column("permission_id", sa.Integer()),
    )
    op.bulk_insert(
        role_permissions_table,
        [
            {"role_id": role_ids[role], "permission_id": permission_ids[code]}
            for role, codes in DEFAULT_ROLE_PERMISSIONS.items()
            for code in codes
        ],
    )

    op.create_table(
        "user_sessions",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("auth_version", sa.Integer(), nullable=False),
        sa.Column("issued_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_by", sa.Integer(), nullable=True),
        sa.Column("revoke_reason", sa.String(length=80), nullable=True),
        sa.Column("login_ip", sa.String(length=45), nullable=True),
        sa.Column("user_agent", sa.String(length=512), nullable=True),
        sa.Column("device_label", sa.String(length=120), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["revoked_by"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_user_sessions")),
    )
    op.create_index(op.f("ix_user_sessions_user_id"), "user_sessions", ["user_id"])
    op.create_index(op.f("ix_user_sessions_expires_at"), "user_sessions", ["expires_at"])
    op.create_index(op.f("ix_user_sessions_revoked_at"), "user_sessions", ["revoked_at"])
    op.create_index(
        "ix_user_sessions_user_active", "user_sessions", ["user_id", "revoked_at", "expires_at"]
    )

    op.create_table(
        "auth_events",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("event_type", sa.String(length=40), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=True),
        sa.Column("normalized_identity", sa.String(length=255), nullable=True),
        sa.Column(
            "occurred_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("ip_address", sa.String(length=45), nullable=True),
        sa.Column("user_agent", sa.String(length=512), nullable=True),
        sa.Column("request_id", sa.String(length=64), nullable=False),
        sa.Column("success", sa.Boolean(), nullable=False),
        sa.Column("reason_code", sa.String(length=80), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_auth_events")),
    )
    for column in ("event_type", "occurred_at", "request_id"):
        op.create_index(op.f(f"ix_auth_events_{column}"), "auth_events", [column])
    op.create_index(
        "ix_auth_events_identity_time", "auth_events", ["normalized_identity", "occurred_at"]
    )
    op.create_index("ix_auth_events_ip_time", "auth_events", ["ip_address", "occurred_at"])

    json_type = sa.JSON().with_variant(postgresql.JSONB(), "postgresql")
    op.create_table(
        "audit_events",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("request_id", sa.String(length=64), nullable=False),
        sa.Column(
            "occurred_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("actor_user_id", sa.Integer(), nullable=True),
        sa.Column("actor_username", sa.String(length=50), nullable=True),
        sa.Column("actor_full_name", sa.String(length=120), nullable=True),
        sa.Column("actor_role", sa.String(length=32), nullable=True),
        sa.Column("category", sa.String(length=32), nullable=False),
        sa.Column("action", sa.String(length=80), nullable=False),
        sa.Column("outcome", sa.String(length=16), nullable=False),
        sa.Column("http_method", sa.String(length=10), nullable=False),
        sa.Column("path", sa.String(length=500), nullable=False),
        sa.Column("status_code", sa.Integer(), nullable=False),
        sa.Column("resource_type", sa.String(length=50), nullable=True),
        sa.Column("resource_id", sa.String(length=80), nullable=True),
        sa.Column("resource_label", sa.String(length=255), nullable=True),
        sa.Column("before", json_type, nullable=True),
        sa.Column("after", json_type, nullable=True),
        sa.Column("changes", json_type, nullable=True),
        sa.Column("metadata", json_type, nullable=True),
        sa.Column("ip_address", sa.String(length=45), nullable=True),
        sa.Column("user_agent", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["actor_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_audit_events")),
    )
    for column in (
        "request_id",
        "occurred_at",
        "actor_user_id",
        "actor_role",
        "category",
        "action",
        "outcome",
        "resource_type",
        "resource_id",
    ):
        op.create_index(op.f(f"ix_audit_events_{column}"), "audit_events", [column])
    op.create_index("ix_audit_events_actor_time", "audit_events", ["actor_user_id", "occurred_at"])
    op.create_index("ix_audit_events_category_action", "audit_events", ["category", "action"])
    op.create_index("ix_audit_events_resource", "audit_events", ["resource_type", "resource_id"])
    op.create_index("ix_audit_events_outcome_time", "audit_events", ["outcome", "occurred_at"])

    op.add_column("products", sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("products", sa.Column("deleted_by", sa.Integer(), nullable=True))
    op.create_foreign_key(
        op.f("fk_products_deleted_by_users"),
        "products",
        "users",
        ["deleted_by"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index(op.f("ix_products_deleted_at"), "products", ["deleted_at"])

    for name, column_type in (
        ("actor_username", sa.String(length=50)),
        ("actor_full_name", sa.String(length=120)),
        ("actor_role", sa.String(length=32)),
        ("product_code", sa.String(length=32)),
        ("product_name", sa.String(length=180)),
    ):
        op.add_column("stock_transactions", sa.Column(name, column_type, nullable=True))
    op.execute(
        "UPDATE stock_transactions st SET "
        "actor_username = u.username, actor_full_name = u.full_name, "
        "actor_role = CASE WHEN u.is_admin THEN 'admin' ELSE 'manager' END, "
        "product_code = p.product_code, product_name = p.name "
        "FROM users u, products p WHERE st.created_by = u.id AND st.product_id = p.id"
    )
    for name in ("actor_username", "actor_full_name", "actor_role", "product_code", "product_name"):
        op.alter_column("stock_transactions", name, nullable=False)
    op.drop_constraint(
        op.f("fk_stock_transactions_product_id_products"), "stock_transactions", type_="foreignkey"
    )
    op.create_foreign_key(
        op.f("fk_stock_transactions_product_id_products"),
        "stock_transactions",
        "products",
        ["product_id"],
        ["id"],
        ondelete="RESTRICT",
    )


def downgrade() -> None:
    op.drop_constraint(
        op.f("fk_stock_transactions_product_id_products"), "stock_transactions", type_="foreignkey"
    )
    op.create_foreign_key(
        op.f("fk_stock_transactions_product_id_products"),
        "stock_transactions",
        "products",
        ["product_id"],
        ["id"],
        ondelete="CASCADE",
    )
    for name in ("product_name", "product_code", "actor_role", "actor_full_name", "actor_username"):
        op.drop_column("stock_transactions", name)
    op.drop_index(op.f("ix_products_deleted_at"), table_name="products")
    op.drop_constraint(op.f("fk_products_deleted_by_users"), "products", type_="foreignkey")
    op.drop_column("products", "deleted_by")
    op.drop_column("products", "deleted_at")
    op.drop_table("audit_events")
    op.drop_table("auth_events")
    op.drop_table("user_sessions")
    op.drop_table("role_permissions")
    op.drop_index(op.f("ix_users_deleted_at"), table_name="users")
    op.drop_index(op.f("ix_users_role_id"), table_name="users")
    op.drop_constraint(op.f("fk_users_deleted_by_users"), "users", type_="foreignkey")
    op.drop_constraint(op.f("fk_users_role_id_roles"), "users", type_="foreignkey")
    for name in (
        "deleted_by",
        "deleted_at",
        "last_activity_at",
        "last_login_at",
        "auth_version",
        "role_id",
    ):
        op.drop_column("users", name)
    op.drop_table("permissions")
    op.drop_table("roles")
