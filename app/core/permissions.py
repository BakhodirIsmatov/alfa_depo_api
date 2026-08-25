from dataclasses import dataclass
from enum import StrEnum


class UserRole(StrEnum):
    ADMIN = "admin"
    MANAGER = "manager"
    USER = "user"
    REPORTER = "reporter"


class PermissionCode(StrEnum):
    DASHBOARD_VIEW = "dashboard.view"
    PRODUCTS_VIEW = "products.view"
    PRODUCTS_CREATE = "products.create"
    PRODUCTS_UPDATE = "products.update"
    PRODUCTS_MANAGE_IMAGE = "products.manage_image"
    PRODUCTS_USE_OCR = "products.use_ocr"
    PRODUCTS_DELETE = "products.delete"
    STOCK_VIEW = "stock.view"
    STOCK_HISTORY_VIEW = "stock.history.view"
    STOCK_IN = "stock.in"
    STOCK_OUT = "stock.out"
    STOCK_ADJUST = "stock.adjust"
    REPORTS_VIEW = "reports.view"
    REPORTS_EXPORT = "reports.export"
    AUDIT_OPERATIONS_VIEW = "audit.operations.view"
    AUDIT_SECURITY_VIEW = "audit.security.view"
    USERS_VIEW = "users.view"
    USERS_CREATE = "users.create"
    USERS_UPDATE = "users.update"
    USERS_DEACTIVATE = "users.deactivate"
    USERS_RESET_PASSWORD = "users.reset_password"
    ROLES_VIEW = "roles.view"
    ROLES_UPDATE_PERMISSIONS = "roles.update_permissions"
    SESSIONS_VIEW = "sessions.view"
    SESSIONS_REVOKE = "sessions.revoke"


@dataclass(frozen=True)
class PermissionDefinition:
    code: PermissionCode
    module: str
    description: str
    is_assignable: bool = True


_SECURITY_CODES = {
    PermissionCode.USERS_VIEW,
    PermissionCode.USERS_CREATE,
    PermissionCode.USERS_UPDATE,
    PermissionCode.USERS_DEACTIVATE,
    PermissionCode.USERS_RESET_PASSWORD,
    PermissionCode.ROLES_VIEW,
    PermissionCode.ROLES_UPDATE_PERMISSIONS,
    PermissionCode.SESSIONS_VIEW,
    PermissionCode.SESSIONS_REVOKE,
    PermissionCode.AUDIT_SECURITY_VIEW,
}

PERMISSION_CATALOG = tuple(
    PermissionDefinition(
        code=code,
        module=code.value.split(".", 1)[0],
        description=code.value.replace(".", " ").replace("_", " ").title(),
        is_assignable=code not in _SECURITY_CODES,
    )
    for code in PermissionCode
)

_MANAGER = {code for code in PermissionCode if code not in _SECURITY_CODES}

DEFAULT_ROLE_PERMISSIONS: dict[UserRole, frozenset[PermissionCode]] = {
    UserRole.ADMIN: frozenset(PermissionCode),
    UserRole.MANAGER: frozenset(_MANAGER),
    UserRole.USER: frozenset(
        {
            PermissionCode.PRODUCTS_VIEW,
            PermissionCode.STOCK_VIEW,
            PermissionCode.STOCK_OUT,
        }
    ),
    UserRole.REPORTER: frozenset({PermissionCode.REPORTS_VIEW, PermissionCode.REPORTS_EXPORT}),
}

ROLE_NAMES = {
    UserRole.ADMIN: "Administrator",
    UserRole.MANAGER: "Manager",
    UserRole.USER: "Warehouse User",
    UserRole.REPORTER: "Reporter",
}

PERMISSION_DEPENDENCIES: dict[PermissionCode, frozenset[PermissionCode]] = {
    PermissionCode.STOCK_OUT: frozenset({PermissionCode.PRODUCTS_VIEW, PermissionCode.STOCK_VIEW})
}


def validate_permission_set(codes: set[PermissionCode]) -> None:
    forbidden = codes & _SECURITY_CODES
    if forbidden:
        values = ", ".join(sorted(code.value for code in forbidden))
        raise ValueError(f"Admin-only permissions cannot be assigned: {values}")
    for code, dependencies in PERMISSION_DEPENDENCIES.items():
        if code in codes and not dependencies.issubset(codes):
            missing = ", ".join(sorted(item.value for item in dependencies - codes))
            raise ValueError(f"{code.value} requires: {missing}")
