from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from typing import Any

from fastapi import Request
from pydantic import BaseModel
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit import AuditEvent
from app.models.user import User

_SENSITIVE_PARTS = {
    "authorization",
    "cookie",
    "password",
    "password_hash",
    "token",
    "access_token",
    "refresh_token",
    "secret",
    "image",
    "raw_image",
}


def request_id(request: Request) -> str:
    return str(getattr(request.state, "request_id", "unknown"))[:64]


def client_context(request: Request) -> tuple[str | None, str | None]:
    ip = request.client.host if request.client else None
    user_agent = request.headers.get("user-agent")
    return (ip[:45] if ip else None, user_agent[:512] if user_agent else None)


def audit_json(value: Any, *, key: str | None = None) -> Any:
    if key and any(part in key.lower() for part in _SENSITIVE_PARTS):
        return "[REDACTED]"
    if isinstance(value, BaseModel):
        value = value.model_dump(mode="python")
    if isinstance(value, dict):
        return {
            str(item_key): audit_json(item, key=str(item_key)) for item_key, item in value.items()
        }
    if isinstance(value, (list, tuple, set)):
        return [audit_json(item) for item in value]
    if isinstance(value, bytes):
        return "[BINARY REDACTED]"
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, Enum):
        return value.value
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    return str(value)


def field_changes(before: dict[str, Any], after: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        key: {"before": audit_json(before.get(key)), "after": audit_json(after.get(key))}
        for key in before.keys() | after.keys()
        if before.get(key) != after.get(key)
    }


class AuditService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    def add(
        self,
        request: Request,
        actor: User | None,
        *,
        category: str,
        action: str,
        outcome: str = "SUCCESS",
        status_code: int = 200,
        resource_type: str | None = None,
        resource_id: str | int | None = None,
        resource_label: str | None = None,
        before: Any = None,
        after: Any = None,
        changes: Any = None,
        metadata: Any = None,
    ) -> AuditEvent:
        ip, user_agent = client_context(request)
        role_code = actor.role.code if actor and actor.role else None
        event = AuditEvent(
            request_id=request_id(request),
            actor_user_id=actor.id if actor else None,
            actor_username=actor.username if actor else None,
            actor_full_name=actor.full_name if actor else None,
            actor_role=role_code,
            category=category,
            action=action,
            outcome=outcome,
            http_method=request.method,
            path=request.url.path[:500],
            status_code=status_code,
            resource_type=resource_type,
            resource_id=str(resource_id)[:80] if resource_id is not None else None,
            resource_label=resource_label[:255] if resource_label else None,
            before=audit_json(before),
            after=audit_json(after),
            changes=audit_json(changes),
            event_metadata=audit_json(metadata),
            ip_address=ip,
            user_agent=user_agent,
        )
        self.session.add(event)
        return event

    async def record_read(self, request: Request, actor: User, **kwargs: Any) -> None:
        from app.core.exceptions import AppError

        try:
            self.add(request, actor, **kwargs)
            await self.session.commit()
        except SQLAlchemyError as exc:
            await self.session.rollback()
            raise AppError(
                "AUDIT_UNAVAILABLE",
                "The operation could not be audited and was not completed",
                503,
            ) from exc
