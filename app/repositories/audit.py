from datetime import datetime

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit import AuditEvent


class AuditRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get(self, event_id: int) -> AuditEvent | None:
        return await self.session.get(AuditEvent, event_id)

    async def list(
        self,
        *,
        page: int,
        page_size: int,
        occurred_from: datetime | None,
        occurred_to: datetime | None,
        actor_user_id: int | None,
        actor_role: str | None,
        category: str | None,
        action: str | None,
        outcome: str | None,
        resource_type: str | None,
        resource_id: str | None,
        request_id: str | None,
        search: str | None,
        security_allowed: bool,
    ) -> tuple[list[AuditEvent], int]:
        filters = []
        if not security_allowed:
            filters.append(AuditEvent.category != "SECURITY")
        if occurred_from:
            filters.append(AuditEvent.occurred_at >= occurred_from)
        if occurred_to:
            filters.append(AuditEvent.occurred_at <= occurred_to)
        for column, value in (
            (AuditEvent.actor_user_id, actor_user_id),
            (AuditEvent.actor_role, actor_role),
            (AuditEvent.category, category),
            (AuditEvent.action, action),
            (AuditEvent.outcome, outcome),
            (AuditEvent.resource_type, resource_type),
            (AuditEvent.resource_id, resource_id),
            (AuditEvent.request_id, request_id),
        ):
            if value is not None:
                filters.append(column == value)
        if search:
            pattern = f"%{search.strip()}%"
            filters.append(
                or_(
                    AuditEvent.actor_username.ilike(pattern),
                    AuditEvent.actor_full_name.ilike(pattern),
                    AuditEvent.resource_label.ilike(pattern),
                    AuditEvent.action.ilike(pattern),
                    AuditEvent.request_id.ilike(pattern),
                )
            )
        total = int(
            await self.session.scalar(select(func.count()).select_from(AuditEvent).where(*filters))
            or 0
        )
        result = await self.session.scalars(
            select(AuditEvent)
            .where(*filters)
            .order_by(AuditEvent.occurred_at.desc(), AuditEvent.id.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        return list(result), total
