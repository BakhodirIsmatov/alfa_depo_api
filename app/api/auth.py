from fastapi import APIRouter, Request

from app.api.dependencies import CurrentUser, SessionDep, current_session
from app.repositories.access import AccessRepository
from app.schemas.auth import LoginRequest, TokenResponse
from app.schemas.common import MessageData, SuccessResponse
from app.schemas.user import UserResponse
from app.services.auth import AuthService

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post(
    "/login",
    response_model=SuccessResponse[TokenResponse],
    summary="Log in",
    description="Authenticate with a username or email and receive a JWT access token.",
)
async def login(
    payload: LoginRequest, request: Request, session: SessionDep
) -> SuccessResponse[TokenResponse]:
    token, expires_in, user, permissions = await AuthService(session).authenticate(
        payload.username, payload.password, request
    )
    return SuccessResponse(
        data=TokenResponse(
            access_token=token,
            expires_in=expires_in,
            user=UserResponse.from_user(user, permissions),
        )
    )


@router.get(
    "/me",
    response_model=SuccessResponse[UserResponse],
    summary="Get current user",
    description="Return the active user represented by the bearer token.",
)
async def me(
    request: Request, user: CurrentUser, session: SessionDep
) -> SuccessResponse[UserResponse]:
    permissions = await AccessRepository(session).effective_permissions(user.role)
    return SuccessResponse(data=UserResponse.from_user(user, permissions))


@router.post(
    "/logout",
    response_model=SuccessResponse[MessageData],
    summary="Log out",
    description="Revoke the current server-side session and invalidate its access token.",
)
async def logout(
    request: Request, user: CurrentUser, session: SessionDep
) -> SuccessResponse[MessageData]:
    await AuthService(session).logout(request, user, current_session(request))
    return SuccessResponse(data=MessageData(message="Logged out successfully"))
