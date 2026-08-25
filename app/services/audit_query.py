from datetime import datetime
from math import ceil

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.exceptions import AppError, NotFoundError
from app.repositories.audit import AuditRepository
from app.schemas.audit import AuditEventResponse
from app.schemas.common import PaginatedData, PaginationMeta


class AuditQueryService:
    def __init__(self, session: AsyncSession) -> None:
        self.repository = AuditRepository(session)

    async def get(self, event_id: int, *, security_allowed: bool) -> AuditEventResponse:
        event = await self.repository.get(event_id)
        if event is None or (event.category == "SECURITY" and not security_allowed):
            raise NotFoundError("AUDIT_EVENT_NOT_FOUND", "Audit event not found")
        return AuditEventResponse.model_validate(event)

    async def list(
        self,
        *,
        page: int,
        page_size: int,
        occurred_from: datetime | None,
        occurred_to: datetime | None,
        security_allowed: bool,
        **filters,
    ) -> PaginatedData[AuditEventResponse]:
        settings = get_settings()
        if occurred_from and occurred_to:
            if occurred_from > occurred_to:
                raise AppError("INVALID_AUDIT_RANGE", "Start must not be after end", 422)
            if (occurred_to - occurred_from).days > settings.audit_max_range_days:
                raise AppError("AUDIT_RANGE_TOO_LARGE", "Audit date range is too large", 422)
        events, total = await self.repository.list(
            page=page,
            page_size=page_size,
            occurred_from=occurred_from,
            occurred_to=occurred_to,
            security_allowed=security_allowed,
            **filters,
        )
        return PaginatedData(
            items=[AuditEventResponse.model_validate(event) for event in events],
            pagination=PaginationMeta(
                page=page,
                page_size=page_size,
                total=total,
                pages=ceil(total / page_size),
            ),
        )
