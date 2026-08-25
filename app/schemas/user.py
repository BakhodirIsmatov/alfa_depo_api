from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from app.core.permissions import PermissionCode, UserRole


class UserBase(BaseModel):
    username: str = Field(min_length=3, max_length=50, pattern=r"^[A-Za-z0-9_.-]+$")
    email: EmailStr
    full_name: str = Field(min_length=1, max_length=120)
    is_active: bool = True
    role: UserRole = UserRole.MANAGER
    is_admin: bool | None = None

    @field_validator("username", "email", mode="before")
    @classmethod
    def normalize_identity(cls, value: str) -> str:
        return value.strip().lower()


class UserCreate(UserBase):
    password: str = Field(min_length=8, max_length=128)


class UserUpdate(BaseModel):
    username: str | None = Field(
        default=None, min_length=3, max_length=50, pattern=r"^[A-Za-z0-9_.-]+$"
    )
    email: EmailStr | None = None
    full_name: str | None = Field(default=None, min_length=1, max_length=120)
    password: str | None = Field(default=None, min_length=8, max_length=128)
    is_active: bool | None = None
    role: UserRole | None = None
    is_admin: bool | None = None

    @field_validator("username", "email", mode="before")
    @classmethod
    def normalize_identity(cls, value: str | None) -> str | None:
        return value.strip().lower() if value else value


class PasswordResetRequest(BaseModel):
    password: str = Field(min_length=8, max_length=128)


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str
    email: EmailStr
    full_name: str
    is_active: bool
    is_admin: bool
    role: UserRole
    effective_permissions: list[PermissionCode]
    last_login_at: datetime | None
    last_activity_at: datetime | None
    deleted_at: datetime | None
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_user(
        cls, user, permissions: set[PermissionCode] | frozenset[PermissionCode]
    ) -> "UserResponse":
        role = UserRole(user.role.code)
        return cls(
            id=user.id,
            username=user.username,
            email=user.email,
            full_name=user.full_name,
            is_active=user.is_active,
            is_admin=role == UserRole.ADMIN,
            role=role,
            effective_permissions=sorted(permissions, key=lambda item: item.value),
            last_login_at=user.last_login_at,
            last_activity_at=user.last_activity_at,
            deleted_at=user.deleted_at,
            created_at=user.created_at,
            updated_at=user.updated_at,
        )
