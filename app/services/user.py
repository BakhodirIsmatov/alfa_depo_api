from __future__ import annotations

from datetime import UTC, datetime
from math import ceil

from fastapi import Request
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AppError, ConflictError, NotFoundError
from app.core.permissions import UserRole
from app.core.security import hash_password
from app.models.access import AuthEvent, UserSession
from app.models.user import User
from app.repositories.access import AccessRepository
from app.repositories.user import UserRepository
from app.schemas.access import AuthEventResponse, SessionResponse
from app.schemas.common import PaginatedData, PaginationMeta
from app.schemas.user import UserCreate, UserResponse, UserUpdate
from app.services.audit import AuditService, client_context, request_id


class UserService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repository = UserRepository(session)
        self.access = AccessRepository(session)

    async def list(
        self,
        page: int,
        page_size: int,
        *,
        search: str | None = None,
        role: UserRole | None = None,
        is_active: bool | None = None,
        sort_by: str = "id",
        sort_order: str = "asc",
        last_login_from: datetime | None = None,
        last_login_to: datetime | None = None,
        activity_from: datetime | None = None,
        activity_to: datetime | None = None,
    ) -> PaginatedData[UserResponse]:
        users, total = await self.repository.list(
            page,
            page_size,
            search=search,
            role=role.value if role else None,
            is_active=is_active,
            sort_by=sort_by,
            sort_order=sort_order,
            last_login_from=last_login_from,
            last_login_to=last_login_to,
            activity_from=activity_from,
            activity_to=activity_to,
        )
        permissions_by_role = {}
        for user in users:
            if user.role_id not in permissions_by_role:
                permissions_by_role[user.role_id] = await self.access.effective_permissions(
                    user.role
                )
        return PaginatedData(
            items=[
                UserResponse.from_user(user, permissions_by_role[user.role_id]) for user in users
            ],
            pagination=PaginationMeta(
                page=page, page_size=page_size, total=total, pages=ceil(total / page_size)
            ),
        )

    async def get(self, user_id: int) -> User:
        user = await self.repository.get_by_id(user_id)
        if user is None:
            raise NotFoundError("USER_NOT_FOUND", "User not found")
        return user

    async def response(self, user: User) -> UserResponse:
        return UserResponse.from_user(user, await self.access.effective_permissions(user.role))

    async def create(self, payload: UserCreate, actor: User, request: Request) -> User:
        if await self.repository.identity_exists(username=payload.username, email=payload.email):
            raise ConflictError("USER_ALREADY_EXISTS", "Username or email already exists")
        role_code = UserRole.ADMIN if payload.is_admin is True else payload.role
        role = await self.access.get_role(role_code.value)
        if role is None:
            raise AppError("INVALID_ROLE", "Role is not available", 422)
        user = User(
            **payload.model_dump(exclude={"password", "role", "is_admin"}),
            password_hash=hash_password(payload.password),
            role_id=role.id,
            is_admin=role_code == UserRole.ADMIN,
        )
        self.repository.add(user)
        try:
            await self.session.flush()
            AuditService(self.session).add(
                request,
                actor,
                category="SECURITY",
                action="USER_CREATED",
                status_code=201,
                resource_type="user",
                resource_id=user.id,
                resource_label=user.username,
                after={
                    "username": user.username,
                    "email": user.email,
                    "full_name": user.full_name,
                    "role": role.code,
                    "is_active": user.is_active,
                },
            )
            await self.session.commit()
        except IntegrityError as exc:
            await self.session.rollback()
            raise ConflictError("USER_ALREADY_EXISTS", "Username or email already exists") from exc
        await self.session.refresh(user)
        return user

    async def update(
        self, user_id: int, payload: UserUpdate, actor: User, request: Request
    ) -> User:
        user = await self.get(user_id)
        values = payload.model_dump(exclude_unset=True)
        requested_role = values.pop("role", None)
        legacy_is_admin = values.pop("is_admin", None)
        if legacy_is_admin is not None:
            requested_role = UserRole.ADMIN if legacy_is_admin else UserRole.MANAGER
        target_role = user.role
        if requested_role is not None:
            target_role = await self.access.get_role(UserRole(requested_role).value)
            if target_role is None:
                raise AppError("INVALID_ROLE", "Role is not available", 422)
        if user.id == actor.id and values.get("is_active") is False:
            raise AppError(
                "SELF_DEACTIVATION_NOT_ALLOWED", "You cannot deactivate your own account"
            )
        if user.id == actor.id and target_role.code != UserRole.ADMIN:
            raise AppError("SELF_DEMOTION_NOT_ALLOWED", "You cannot remove your own admin access")
        losing_admin = user.role.code == UserRole.ADMIN and (
            target_role.code != UserRole.ADMIN or values.get("is_active") is False
        )
        if losing_admin:
            admin_role = await self.access.get_role(UserRole.ADMIN.value, for_update=True)
            if (
                admin_role is None
                or await self.repository.count_active_admins(admin_role.id, for_update=True) <= 1
            ):
                raise ConflictError(
                    "LAST_ADMIN_REQUIRED", "The last active administrator cannot be changed"
                )
        if await self.repository.identity_exists(
            username=values.get("username"), email=values.get("email"), exclude_id=user_id
        ):
            raise ConflictError("USER_ALREADY_EXISTS", "Username or email already exists")
        before = self._snapshot(user)
        password = values.pop("password", None)
        sensitive_change = password is not None or target_role.id != user.role_id
        if password is not None:
            user.password_hash = hash_password(password)
        for field, value in values.items():
            setattr(user, field, value)
        if target_role.id != user.role_id:
            user.role_id = target_role.id
            user.role = target_role
            user.is_admin = target_role.code == UserRole.ADMIN
        if values.get("is_active") is False:
            sensitive_change = True
        if sensitive_change:
            user.auth_version += 1
            await self.access.revoke_user_sessions(
                user.id, actor_id=actor.id, reason="ACCOUNT_SECURITY_CHANGED"
            )
        action = (
            "PASSWORD_RESET"
            if password is not None and len(values) == 0 and requested_role is None
            else "USER_UPDATED"
        )
        after = self._snapshot(user)
        AuditService(self.session).add(
            request,
            actor,
            category="SECURITY",
            action=action,
            resource_type="user",
            resource_id=user.id,
            resource_label=user.username,
            before=before,
            after=after,
            changes={
                key: {"before": before.get(key), "after": after.get(key)}
                for key in before
                if before.get(key) != after.get(key)
            },
            metadata={"sessions_revoked": sensitive_change},
        )
        try:
            await self.session.commit()
        except IntegrityError as exc:
            await self.session.rollback()
            raise ConflictError("USER_ALREADY_EXISTS", "Username or email already exists") from exc
        await self.session.refresh(user)
        return user

    async def delete(self, user_id: int, actor: User, request: Request) -> None:
        user = await self.get(user_id)
        if user.id == actor.id:
            raise AppError("SELF_DELETE_NOT_ALLOWED", "You cannot delete your own account")
        if user.role.code == UserRole.ADMIN:
            admin_role = await self.access.get_role(UserRole.ADMIN.value, for_update=True)
            if (
                admin_role is None
                or await self.repository.count_active_admins(admin_role.id, for_update=True) <= 1
            ):
                raise ConflictError(
                    "LAST_ADMIN_REQUIRED", "The last active administrator cannot be changed"
                )
        before = self._snapshot(user)
        now = datetime.now(UTC)
        user.is_active = False
        user.deleted_at = now
        user.deleted_by = actor.id
        user.auth_version += 1
        revoked = await self.access.revoke_user_sessions(
            user.id, actor_id=actor.id, reason="ACCOUNT_DEACTIVATED"
        )
        AuditService(self.session).add(
            request,
            actor,
            category="SECURITY",
            action="USER_DEACTIVATED",
            resource_type="user",
            resource_id=user.id,
            resource_label=user.username,
            before=before,
            after=self._snapshot(user),
            metadata={"sessions_revoked": revoked},
        )
        await self.session.commit()

    async def sessions(self, user_id: int) -> list[SessionResponse]:
        await self.get(user_id)
        result = await self.session.scalars(
            select(UserSession)
            .where(UserSession.user_id == user_id)
            .order_by(UserSession.issued_at.desc())
            .limit(200)
        )
        return [SessionResponse.model_validate(item) for item in result]

    async def auth_events(self, user_id: int) -> list[AuthEventResponse]:
        await self.get(user_id)
        result = await self.session.scalars(
            select(AuthEvent)
            .where(AuthEvent.user_id == user_id)
            .order_by(AuthEvent.occurred_at.desc(), AuthEvent.id.desc())
            .limit(200)
        )
        return [AuthEventResponse.model_validate(item) for item in result]

    async def revoke_sessions(
        self,
        user_id: int,
        actor: User,
        request: Request,
        session_ids: list[str] | None,
        reason: str,
    ) -> int:
        user = await self.get(user_id)
        statement = select(UserSession).where(
            UserSession.user_id == user_id, UserSession.revoked_at.is_(None)
        )
        if session_ids is not None:
            statement = statement.where(UserSession.id.in_(session_ids))
        items = list((await self.session.scalars(statement)).all())
        now = datetime.now(UTC)
        for item in items:
            item.revoked_at = now
            item.revoked_by = actor.id
            item.revoke_reason = reason
        ip, user_agent = client_context(request)
        self.session.add(
            AuthEvent(
                event_type="SESSION_REVOKED",
                user_id=user.id,
                normalized_identity=user.username,
                ip_address=ip,
                user_agent=user_agent,
                request_id=request_id(request),
                success=True,
                reason_code=reason,
            )
        )
        AuditService(self.session).add(
            request,
            actor,
            category="SECURITY",
            action="SESSIONS_REVOKED",
            resource_type="user",
            resource_id=user.id,
            resource_label=user.username,
            metadata={"count": len(items), "reason": reason},
        )
        await self.session.commit()
        return len(items)

    @staticmethod
    def _snapshot(user: User) -> dict:
        return {
            "username": user.username,
            "email": user.email,
            "full_name": user.full_name,
            "role": user.role.code,
            "is_active": user.is_active,
            "deleted_at": user.deleted_at.isoformat() if user.deleted_at else None,
        }
