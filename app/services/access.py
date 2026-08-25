from fastapi import Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AppError, ConflictError, NotFoundError
from app.core.permissions import UserRole, validate_permission_set
from app.models.user import User
from app.repositories.access import AccessRepository
from app.schemas.access import PermissionResponse, RolePermissionUpdate, RoleResponse
from app.services.audit import AuditService


class AccessService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repository = AccessRepository(session)

    async def list_roles(self) -> list[RoleResponse]:
        roles = await self.repository.list_roles()
        return [await self._response(role) for role in roles]

    async def get_role(self, code: UserRole) -> RoleResponse:
        role = await self.repository.get_role(code.value)
        if role is None:
            raise NotFoundError("ROLE_NOT_FOUND", "Role not found")
        return await self._response(role)

    async def list_permissions(self) -> list[PermissionResponse]:
        return [
            PermissionResponse.model_validate(item)
            for item in await self.repository.list_permissions()
        ]

    async def update_permissions(
        self,
        code: UserRole,
        payload: RolePermissionUpdate,
        actor: User,
        request: Request,
    ) -> RoleResponse:
        if code == UserRole.ADMIN:
            raise AppError("ADMIN_ROLE_IMMUTABLE", "Administrator permissions cannot be changed")
        role = await self.repository.get_role(code.value, for_update=True)
        if role is None:
            raise NotFoundError("ROLE_NOT_FOUND", "Role not found")
        if role.version != payload.expected_version:
            raise ConflictError(
                "ROLE_PERMISSION_CONFLICT",
                "Role permissions changed since they were loaded; refresh and try again",
            )
        try:
            validate_permission_set(payload.permissions)
        except ValueError as exc:
            raise AppError("INVALID_PERMISSION_SET", str(exc), 422) from exc
        before = await self.repository.effective_permissions(role)
        await self.repository.replace_permissions(role, payload.permissions, actor.id)
        AuditService(self.session).add(
            request,
            actor,
            category="SECURITY",
            action="ROLE_PERMISSIONS_UPDATED",
            resource_type="role",
            resource_id=role.code,
            resource_label=role.name,
            before={
                "permissions": sorted(item.value for item in before),
                "version": role.version - 1,
            },
            after={
                "permissions": sorted(item.value for item in payload.permissions),
                "version": role.version,
            },
        )
        await self.session.commit()
        return await self.get_role(code)

    async def _response(self, role) -> RoleResponse:
        permissions = await self.repository.effective_permissions(role)
        return RoleResponse(
            code=UserRole(role.code),
            name=role.name,
            is_system=role.is_system,
            version=role.version,
            permissions=sorted(permissions, key=lambda item: item.value),
        )
