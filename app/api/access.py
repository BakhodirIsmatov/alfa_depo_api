from typing import Annotated

from fastapi import APIRouter, Depends, Request

from app.api.dependencies import SessionDep, require_permissions
from app.core.permissions import PermissionCode, UserRole
from app.models.user import User
from app.schemas.access import PermissionResponse, RolePermissionUpdate, RoleResponse
from app.schemas.common import SuccessResponse
from app.services.access import AccessService

router = APIRouter(tags=["Admin: Roles"])
RolesView = Annotated[User, Depends(require_permissions(PermissionCode.ROLES_VIEW))]
RolesUpdate = Annotated[User, Depends(require_permissions(PermissionCode.ROLES_UPDATE_PERMISSIONS))]


@router.get("/roles", response_model=SuccessResponse[list[RoleResponse]])
async def list_roles(_: RolesView, session: SessionDep) -> SuccessResponse[list[RoleResponse]]:
    return SuccessResponse(data=await AccessService(session).list_roles())


@router.get("/permissions", response_model=SuccessResponse[list[PermissionResponse]])
async def list_permissions(
    _: RolesView, session: SessionDep
) -> SuccessResponse[list[PermissionResponse]]:
    return SuccessResponse(data=await AccessService(session).list_permissions())


@router.get("/roles/{code}/permissions", response_model=SuccessResponse[RoleResponse])
async def get_role_permissions(
    code: UserRole, _: RolesView, session: SessionDep
) -> SuccessResponse[RoleResponse]:
    return SuccessResponse(data=await AccessService(session).get_role(code))


@router.put("/roles/{code}/permissions", response_model=SuccessResponse[RoleResponse])
async def update_role_permissions(
    code: UserRole,
    payload: RolePermissionUpdate,
    request: Request,
    actor: RolesUpdate,
    session: SessionDep,
) -> SuccessResponse[RoleResponse]:
    return SuccessResponse(
        data=await AccessService(session).update_permissions(code, payload, actor, request)
    )
