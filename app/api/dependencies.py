from datetime import UTC, datetime, timedelta
from typing import Annotated, Literal

from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.database import get_db
from app.core.exceptions import AuthenticationError, AuthorizationError, PermissionDeniedError
from app.core.permissions import PermissionCode, UserRole
from app.core.security import decode_access_token
from app.models.access import UserSession
from app.models.user import User
from app.repositories.access import AccessRepository
from app.repositories.user import UserRepository

SessionDep = Annotated[AsyncSession, Depends(get_db)]
bearer_scheme = HTTPBearer(auto_error=False)


async def get_current_user(
    request: Request,
    session: SessionDep,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
) -> User:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise AuthenticationError()
    payload = decode_access_token(credentials.credentials)
    try:
        user_id = int(payload["sub"])
    except (KeyError, TypeError, ValueError) as exc:
        raise AuthenticationError("Invalid access token") from exc
    user = await UserRepository(session).get_by_id(user_id)
    if user is None or not user.is_active or user.deleted_at is not None:
        raise AuthenticationError("User account is unavailable")
    jti = str(payload.get("jti", ""))
    user_session = await session.get(UserSession, jti)
    now = datetime.now(UTC)
    if (
        user_session is None
        or user_session.user_id != user.id
        or user_session.revoked_at is not None
        or _aware(user_session.expires_at) <= now
        or user_session.auth_version != user.auth_version
        or payload.get("ver") != user.auth_version
    ):
        raise AuthenticationError("Session is unavailable or expired")
    request.state.current_session = user_session
    request.state.current_user = user
    cutoff = now - timedelta(minutes=get_settings().activity_update_minutes)
    if _aware(user_session.last_seen_at) <= cutoff:
        user_session.last_seen_at = now
        user.last_activity_at = now
        await session.commit()
        await session.refresh(user)
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


async def get_current_admin(user: CurrentUser) -> User:
    if user.role.code != UserRole.ADMIN:
        raise AuthorizationError()
    return user


CurrentAdmin = Annotated[User, Depends(get_current_admin)]


def _aware(value: datetime) -> datetime:
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


def require_permissions(
    *required: PermissionCode,
    match: Literal["all", "any"] = "all",
):
    async def dependency(request: Request, user: CurrentUser, session: SessionDep) -> User:
        cached = getattr(request.state, "effective_permissions", None)
        if cached is None:
            cached = await AccessRepository(session).effective_permissions(user.role)
            request.state.effective_permissions = cached
        allowed = (
            all(code in cached for code in required)
            if match == "all"
            else any(code in cached for code in required)
        )
        if not allowed:
            raise PermissionDeniedError([code.value for code in required])
        return user

    return dependency


def current_session(request: Request) -> UserSession:
    value = getattr(request.state, "current_session", None)
    if value is None:
        raise AuthenticationError()
    return value
