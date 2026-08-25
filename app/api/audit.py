from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request

from app.api.dependencies import SessionDep, require_permissions
from app.core.config import get_settings
from app.core.exceptions import PermissionDeniedError
from app.core.permissions import PermissionCode
from app.models.user import User
from app.schemas.audit import AuditEventResponse
from app.schemas.common import PaginatedData, SuccessResponse
from app.services.audit_query import AuditQueryService

router = APIRouter(prefix="/audit-events", tags=["Audit"])
AuditViewer = Annotated[
    User,
    Depends(
        require_permissions(
            PermissionCode.AUDIT_OPERATIONS_VIEW,
            PermissionCode.AUDIT_SECURITY_VIEW,
            match="any",
        )
    ),
]


def _security_allowed(request: Request) -> bool:
    return PermissionCode.AUDIT_SECURITY_VIEW in getattr(
        request.state, "effective_permissions", frozenset()
    )


@router.get("", response_model=SuccessResponse[PaginatedData[AuditEventResponse]])
async def list_audit_events(
    request: Request,
    _: AuditViewer,
    session: SessionDep,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=get_settings().audit_max_page_size),
    occurred_from: datetime | None = None,
    occurred_to: datetime | None = None,
    actor_user_id: int | None = None,
    actor_role: str | None = Query(default=None, max_length=32),
    category: str | None = Query(default=None, max_length=32),
    action: str | None = Query(default=None, max_length=80),
    outcome: str | None = Query(default=None, max_length=16),
    resource_type: str | None = Query(default=None, max_length=50),
    resource_id: str | None = Query(default=None, max_length=80),
    request_id: str | None = Query(default=None, max_length=64),
    search: str | None = Query(default=None, max_length=255),
) -> SuccessResponse[PaginatedData[AuditEventResponse]]:
    security_allowed = _security_allowed(request)
    if category == "SECURITY" and not security_allowed:
        raise PermissionDeniedError([PermissionCode.AUDIT_SECURITY_VIEW.value])
    return SuccessResponse(
        data=await AuditQueryService(session).list(
            page=page,
            page_size=page_size,
            occurred_from=occurred_from,
            occurred_to=occurred_to,
            actor_user_id=actor_user_id,
            actor_role=actor_role,
            category=category,
            action=action,
            outcome=outcome,
            resource_type=resource_type,
            resource_id=resource_id,
            request_id=request_id,
            search=search,
            security_allowed=security_allowed,
        )
    )


@router.get("/{event_id}", response_model=SuccessResponse[AuditEventResponse])
async def get_audit_event(
    event_id: int, request: Request, _: AuditViewer, session: SessionDep
) -> SuccessResponse[AuditEventResponse]:
    return SuccessResponse(
        data=await AuditQueryService(session).get(
            event_id, security_allowed=_security_allowed(request)
        )
    )
