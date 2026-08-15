import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from citypulse.identity.models import RoleName


class LoginRequest(BaseModel):
    username: str = Field(min_length=3, max_length=32)
    password: str = Field(min_length=1, max_length=256)


class UserRoleView(BaseModel):
    name: RoleName


class CurrentUser(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    username: str
    display_name: str
    is_active: bool
    roles: list[RoleName]


class LoginResponse(BaseModel):
    user: CurrentUser


class UserCreateRequest(BaseModel):
    username: str = Field(min_length=3, max_length=32, pattern=r"^[a-z0-9][a-z0-9_-]*$")
    password: str = Field(min_length=1, max_length=256)
    display_name: str = Field(min_length=1, max_length=64)
    roles: list[RoleName] = Field(min_length=1)


class UserUpdateRequest(BaseModel):
    display_name: str | None = Field(default=None, min_length=1, max_length=64)
    is_active: bool | None = None
    roles: list[RoleName] | None = Field(default=None, min_length=1)


class UserAdminView(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    username: str
    display_name: str
    is_active: bool
    roles: list[RoleName]
    created_at: datetime
    last_login_at: datetime | None


class UserListResponse(BaseModel):
    items: list[UserAdminView]
    total: int
