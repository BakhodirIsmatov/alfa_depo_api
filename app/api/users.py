from datetime import datetime
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Query, Request, status

from app.api.dependencies import SessionDep, require_permissions
from app.core.permissions import PermissionCode, UserRole
from app.models.user import User
from app.schemas.access import AuthEventResponse, SessionResponse, SessionRevokeRequest
from app.schemas.common import MessageData, PaginatedData, SuccessResponse
from app.schemas.user import PasswordResetRequest, UserCreate, UserResponse, UserUpdate
from app.services.user import UserService

router = APIRouter(prefix="/users", tags=["Admin: Users"])
UsersView = Annotated[User, Depends(require_permissions(PermissionCode.USERS_VIEW))]
UsersCreate = Annotated[User, Depends(require_permissions(PermissionCode.USERS_CREATE))]
UsersUpdate = Annotated[User, Depends(require_permissions(PermissionCode.USERS_UPDATE))]
UsersDeactivate = Annotated[User, Depends(require_permissions(PermissionCode.USERS_DEACTIVATE))]
UsersResetPassword = Annotated[
    User, Depends(require_permissions(PermissionCode.USERS_RESET_PASSWORD))
]
SessionsView = Annotated[User, Depends(require_permissions(PermissionCode.SESSIONS_VIEW))]
SessionsRevoke = Annotated[User, Depends(require_permissions(PermissionCode.SESSIONS_REVOKE))]


@router.get(
    "",
    response_model=SuccessResponse[PaginatedData[UserResponse]],
    summary="List users",
    description="List application users. Administrator access is required.",
)
async def list_users(
    _: UsersView,
    session: SessionDep,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    search: str | None = Query(default=None, max_length=255),
    role: UserRole | None = None,
    is_active: bool | None = None,
    sort_by: Literal[
        "id", "username", "full_name", "last_login_at", "last_activity_at", "created_at"
    ] = "id",
    sort_order: Literal["asc", "desc"] = "asc",
    last_login_from: datetime | None = None,
    last_login_to: datetime | None = None,
    activity_from: datetime | None = None,
    activity_to: datetime | None = None,
) -> SuccessResponse[PaginatedData[UserResponse]]:
    return SuccessResponse(
        data=await UserService(session).list(
            page,
            page_size,
            search=search,
            role=role,
            is_active=is_active,
            sort_by=sort_by,
            sort_order=sort_order,
            last_login_from=last_login_from,
            last_login_to=last_login_to,
            activity_from=activity_from,
            activity_to=activity_to,
        )
    )


@router.post(
    "",
    response_model=SuccessResponse[UserResponse],
    status_code=status.HTTP_201_CREATED,
    summary="Create user",
    description="Create an admin or standard user. Administrator access is required.",
)
async def create_user(
    payload: UserCreate, request: Request, actor: UsersCreate, session: SessionDep
) -> SuccessResponse[UserResponse]:
    service = UserService(session)
    user = await service.create(payload, actor, request)
    return SuccessResponse(data=await service.response(user))


@router.get(
    "/{user_id}",
    response_model=SuccessResponse[UserResponse],
    summary="Get user",
    description="Get one user. Administrator access is required.",
)
async def get_user(
    user_id: int, _: UsersView, session: SessionDep
) -> SuccessResponse[UserResponse]:
    service = UserService(session)
    user = await service.get(user_id)
    return SuccessResponse(data=await service.response(user))


@router.put(
    "/{user_id}",
    response_model=SuccessResponse[UserResponse],
    summary="Update user",
    description="Update user profile, password, or admin status. Administrator access is required.",
)
async def update_user(
    user_id: int,
    payload: UserUpdate,
    request: Request,
    actor: UsersUpdate,
    session: SessionDep,
) -> SuccessResponse[UserResponse]:
    service = UserService(session)
    user = await service.update(user_id, payload, actor, request)
    return SuccessResponse(data=await service.response(user))


@router.delete(
    "/{user_id}",
    response_model=SuccessResponse[MessageData],
    summary="Delete user",
    description="Delete an unused user. Administrator access is required.",
)
async def delete_user(
    user_id: int, request: Request, actor: UsersDeactivate, session: SessionDep
) -> SuccessResponse[MessageData]:
    await UserService(session).delete(user_id, actor, request)
    return SuccessResponse(data=MessageData(message="User deactivated successfully"))


@router.post(
    "/{user_id}/reset-password",
    response_model=SuccessResponse[MessageData],
    summary="Reset user password",
)
async def reset_password(
    user_id: int,
    payload: PasswordResetRequest,
    request: Request,
    actor: UsersResetPassword,
    session: SessionDep,
) -> SuccessResponse[MessageData]:
    await UserService(session).update(
        user_id, UserUpdate(password=payload.password), actor, request
    )
    return SuccessResponse(data=MessageData(message="Password reset successfully"))


@router.get("/{user_id}/sessions", response_model=SuccessResponse[list[SessionResponse]])
async def list_user_sessions(
    user_id: int, _: SessionsView, session: SessionDep
) -> SuccessResponse[list[SessionResponse]]:
    return SuccessResponse(data=await UserService(session).sessions(user_id))


@router.post("/{user_id}/sessions/revoke", response_model=SuccessResponse[MessageData])
async def revoke_user_sessions(
    user_id: int,
    payload: SessionRevokeRequest,
    request: Request,
    actor: SessionsRevoke,
    session: SessionDep,
) -> SuccessResponse[MessageData]:
    count = await UserService(session).revoke_sessions(
        user_id, actor, request, payload.session_ids, payload.reason
    )
    return SuccessResponse(data=MessageData(message=f"Revoked {count} session(s)"))


@router.get("/{user_id}/auth-events", response_model=SuccessResponse[list[AuthEventResponse]])
async def list_user_auth_events(
    user_id: int, _: SessionsView, session: SessionDep
) -> SuccessResponse[list[AuthEventResponse]]:
    return SuccessResponse(data=await UserService(session).auth_events(user_id))
