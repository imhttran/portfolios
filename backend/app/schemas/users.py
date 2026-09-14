"""Staff/admin user-management request and response shapes."""

from __future__ import annotations

from datetime import datetime

from pydantic import Field

from app.schemas.base import CamelModel


class CreateUserRequest(CamelModel):
    email: str = ""
    password: str = ""


class PatchRoleRequest(CamelModel):
    role: str = ""


class UserSummary(CamelModel):
    id: int
    email: str
    role: str
    email_verified: bool = Field(alias="emailVerified")
    created_at: datetime = Field(alias="createdAt")
