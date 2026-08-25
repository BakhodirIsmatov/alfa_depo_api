from datetime import UTC, datetime

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.permissions import (
    DEFAULT_ROLE_PERMISSIONS,
    PERMISSION_CATALOG,
    ROLE_NAMES,
    PermissionCode,
    UserRole,
)
from app.models.access import Permission, Role, RolePermission, UserSession


class AccessRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_role(self, code: str, *, for_update: bool = False) -> Role | None:
        statement = (
            select(Role)
            .where(Role.code == code)
            .options(selectinload(Role.permission_links).selectinload(RolePermission.permission))
        )
        if for_update:
            statement = statement.with_for_update()
        return (await self.session.execute(statement)).scalar_one_or_none()

    async def list_roles(self) -> list[Role]:
        result = await self.session.execute(
            select(Role)
            .options(selectinload(Role.permission_links).selectinload(RolePermission.permission))
            .order_by(Role.id)
        )
        return list(result.scalars())

    async def list_permissions(self) -> list[Permission]:
        result = await self.session.execute(
            select(Permission).order_by(Permission.module, Permission.code)
        )
        return list(result.scalars())

    async def effective_permissions(self, role: Role) -> frozenset[PermissionCode]:
        if role.code == UserRole.ADMIN:
            return frozenset(PermissionCode)
        result = await self.session.scalars(
            select(Permission.code)
            .join(RolePermission, RolePermission.permission_id == Permission.id)
            .where(RolePermission.role_id == role.id)
        )
        known = {code.value for code in PermissionCode}
        return frozenset(PermissionCode(code) for code in result if code in known)

    async def replace_permissions(
        self, role: Role, codes: set[PermissionCode], actor_id: int
    ) -> None:
        permissions = list(
            (
                await self.session.scalars(
                    select(Permission).where(Permission.code.in_([code.value for code in codes]))
                )
            ).all()
        )
        if len(permissions) != len(codes):
            raise ValueError("One or more permissions are not present in the catalog")
        await self.session.execute(delete(RolePermission).where(RolePermission.role_id == role.id))
        for permission in permissions:
            self.session.add(
                RolePermission(
                    role_id=role.id,
                    permission_id=permission.id,
                    granted_by=actor_id,
                )
            )
        role.version += 1

    async def revoke_user_sessions(
        self, user_id: int, *, actor_id: int, reason: str, exclude_id: str | None = None
    ) -> int:
        statement = select(UserSession).where(
            UserSession.user_id == user_id,
            UserSession.revoked_at.is_(None),
            UserSession.expires_at > datetime.now(UTC),
        )
        if exclude_id:
            statement = statement.where(UserSession.id != exclude_id)
        sessions = list((await self.session.scalars(statement)).all())
        now = datetime.now(UTC)
        for item in sessions:
            item.revoked_at = now
            item.revoked_by = actor_id
            item.revoke_reason = reason
        return len(sessions)


async def sync_access_catalog(session: AsyncSession) -> dict[UserRole, Role]:
    roles = {role.code: role for role in (await session.scalars(select(Role))).all()}
    for code in UserRole:
        role = roles.get(code.value)
        if role is None:
            role = Role(code=code.value, name=ROLE_NAMES[code], is_system=True)
            session.add(role)
            roles[code.value] = role
        else:
            role.name = ROLE_NAMES[code]
            role.is_system = True
    await session.flush()

    permissions = {
        permission.code: permission
        for permission in (await session.scalars(select(Permission))).all()
    }
    for item in PERMISSION_CATALOG:
        permission = permissions.get(item.code.value)
        if permission is None:
            permission = Permission(
                code=item.code.value,
                module=item.module,
                description=item.description,
                is_assignable=item.is_assignable,
            )
            session.add(permission)
            permissions[item.code.value] = permission
        else:
            permission.module = item.module
            permission.description = item.description
            permission.is_assignable = item.is_assignable
    await session.flush()

    for code in UserRole:
        role = roles[code.value]
        existing_count = int(
            await session.scalar(
                select(func.count())
                .select_from(RolePermission)
                .where(RolePermission.role_id == role.id)
            )
            or 0
        )
        desired = DEFAULT_ROLE_PERMISSIONS[code]
        if code == UserRole.ADMIN:
            existing_codes = set(
                await session.scalars(
                    select(Permission.code)
                    .join(RolePermission)
                    .where(RolePermission.role_id == role.id)
                )
            )
            for permission_code in desired:
                if permission_code.value not in existing_codes:
                    session.add(
                        RolePermission(
                            role_id=role.id,
                            permission_id=permissions[permission_code.value].id,
                        )
                    )
        elif existing_count == 0:
            for permission_code in desired:
                session.add(
                    RolePermission(
                        role_id=role.id,
                        permission_id=permissions[permission_code.value].id,
                    )
                )
    await session.flush()
    return {code: roles[code.value] for code in UserRole}
