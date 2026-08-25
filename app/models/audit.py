from datetime import datetime

from sqlalchemy import JSON, DateTime, ForeignKey, Index, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base

JSON_DATA = JSON().with_variant(JSONB(), "postgresql")


class AuditEvent(Base):
    __tablename__ = "audit_events"
    __table_args__ = (
        Index("ix_audit_events_actor_time", "actor_user_id", "occurred_at"),
        Index("ix_audit_events_category_action", "category", "action"),
        Index("ix_audit_events_resource", "resource_type", "resource_id"),
        Index("ix_audit_events_outcome_time", "outcome", "occurred_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    request_id: Mapped[str] = mapped_column(String(64), index=True)
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False, index=True
    )
    actor_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), index=True
    )
    actor_username: Mapped[str | None] = mapped_column(String(50))
    actor_full_name: Mapped[str | None] = mapped_column(String(120))
    actor_role: Mapped[str | None] = mapped_column(String(32), index=True)
    category: Mapped[str] = mapped_column(String(32), index=True)
    action: Mapped[str] = mapped_column(String(80), index=True)
    outcome: Mapped[str] = mapped_column(String(16), index=True)
    http_method: Mapped[str] = mapped_column(String(10))
    path: Mapped[str] = mapped_column(String(500))
    status_code: Mapped[int] = mapped_column()
    resource_type: Mapped[str | None] = mapped_column(String(50), index=True)
    resource_id: Mapped[str | None] = mapped_column(String(80), index=True)
    resource_label: Mapped[str | None] = mapped_column(String(255))
    before: Mapped[dict | list | None] = mapped_column(JSON_DATA)
    after: Mapped[dict | list | None] = mapped_column(JSON_DATA)
    changes: Mapped[dict | list | None] = mapped_column(JSON_DATA)
    event_metadata: Mapped[dict | list | None] = mapped_column("metadata", JSON_DATA)
    ip_address: Mapped[str | None] = mapped_column(String(45))
    user_agent: Mapped[str | None] = mapped_column(Text)
