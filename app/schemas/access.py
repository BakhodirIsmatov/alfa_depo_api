from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.core.permissions import PermissionCode, UserRole


class PermissionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    code: PermissionCode
    module: str
    description: str
    is_assignable: bool


class RoleResponse(BaseModel):
    code: UserRole
    name: str
    is_system: bool
    version: int
    permissions: list[PermissionCode]


class RolePermissionUpdate(BaseModel):
    permissions: set[PermissionCode]
    expected_version: int = Field(ge=1)


class SessionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    issued_at: datetime
    expires_at: datetime
    last_seen_at: datetime
    revoked_at: datetime | None
    revoke_reason: str | None
    login_ip: str | None
    user_agent: str | None
    device_label: str | None


class SessionRevokeRequest(BaseModel):
    session_ids: list[str] | None = None
    reason: str = Field(default="ADMIN_REVOKED", min_length=1, max_length=80)


class AuthEventResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    event_type: str
    normalized_identity: str | None
    occurred_at: datetime
    ip_address: str | None
    user_agent: str | None
    request_id: str
    success: bool
    reason_code: str | None
