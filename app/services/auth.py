from datetime import UTC, datetime, timedelta

from fastapi import Request
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.exceptions import AppError, AuthenticationError
from app.core.security import create_access_token, verify_password
from app.models.access import AuthEvent, UserSession
from app.models.user import User
from app.repositories.access import AccessRepository
from app.repositories.user import UserRepository
from app.services.audit import client_context, request_id


class AuthService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.users = UserRepository(session)

    async def authenticate(
        self, identity: str, password: str, request: Request
    ) -> tuple[str, int, User, frozenset]:
        normalized = identity.strip().lower()
        ip, user_agent = client_context(request)
        settings = get_settings()
        cutoff = datetime.now(UTC) - timedelta(minutes=settings.login_rate_limit_minutes)
        clauses = [
            AuthEvent.event_type == "LOGIN_FAILED",
            AuthEvent.occurred_at >= cutoff,
        ]
        identity_or_ip = [AuthEvent.normalized_identity == normalized]
        if ip:
            identity_or_ip.append(AuthEvent.ip_address == ip)
        attempts = int(
            await self.session.scalar(
                select(func.count()).select_from(AuthEvent).where(*clauses, or_(*identity_or_ip))
            )
            or 0
        )
        if attempts >= settings.login_rate_limit_attempts:
            self._auth_event("LOGIN_FAILED", None, normalized, request, False, "RATE_LIMITED")
            await self.session.commit()
            raise AppError(
                "AUTH_RATE_LIMITED", "Unable to authenticate with the supplied credentials", 429
            )

        user = await self.users.get_by_identity(normalized)
        if user is None or not verify_password(password, user.password_hash):
            self._auth_event(
                "LOGIN_FAILED", user, normalized, request, False, "INVALID_CREDENTIALS"
            )
            await self.session.commit()
            raise AuthenticationError("Invalid username/email or password")
        if not user.is_active:
            self._auth_event("LOGIN_FAILED", user, normalized, request, False, "ACCOUNT_DISABLED")
            await self.session.commit()
            raise AuthenticationError("Invalid username/email or password")
        now = datetime.now(UTC)
        token, expires_in, jti, expires = create_access_token(
            str(user.id), auth_version=user.auth_version
        )
        self.session.add(
            UserSession(
                id=jti,
                user_id=user.id,
                auth_version=user.auth_version,
                issued_at=now,
                expires_at=expires,
                last_seen_at=now,
                login_ip=ip,
                user_agent=user_agent,
                device_label=user_agent[:120] if user_agent else None,
            )
        )
        user.last_login_at = now
        user.last_activity_at = now
        self._auth_event("LOGIN_SUCCESS", user, normalized, request, True, None)
        await self.session.commit()
        await self.session.refresh(user)
        permissions = await AccessRepository(self.session).effective_permissions(user.role)
        return token, expires_in, user, permissions

    async def logout(self, request: Request, user: User, user_session: UserSession) -> None:
        now = datetime.now(UTC)
        user_session.revoked_at = now
        user_session.revoked_by = user.id
        user_session.revoke_reason = "LOGOUT"
        self._auth_event("LOGOUT", user, user.username, request, True, None)
        await self.session.commit()

    def _auth_event(
        self,
        event_type: str,
        user: User | None,
        normalized_identity: str | None,
        request: Request,
        success: bool,
        reason_code: str | None,
    ) -> None:
        ip, user_agent = client_context(request)
        self.session.add(
            AuthEvent(
                event_type=event_type,
                user_id=user.id if user else None,
                normalized_identity=normalized_identity[:255] if normalized_identity else None,
                ip_address=ip,
                user_agent=user_agent,
                request_id=request_id(request),
                success=success,
                reason_code=reason_code,
            )
        )
