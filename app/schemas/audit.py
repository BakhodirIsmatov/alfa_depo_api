from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class AuditEventResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id: int
    request_id: str
    occurred_at: datetime
    actor_user_id: int | None
    actor_username: str | None
    actor_full_name: str | None
    actor_role: str | None
    category: str
    action: str
    outcome: str
    http_method: str
    path: str
    status_code: int
    resource_type: str | None
    resource_id: str | None
    resource_label: str | None
    before: Any = None
    after: Any = None
    changes: Any = None
    metadata: Any = Field(default=None, validation_alias="event_metadata")
    ip_address: str | None
    user_agent: str | None
