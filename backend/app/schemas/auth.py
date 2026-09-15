"""Auth request bodies and the /api/me response shape."""

from __future__ import annotations

from pydantic import Field

from app.schemas.base import CamelModel


class SignupRequest(CamelModel):
    email: str = ""
    password: str = ""


class EmailRequest(CamelModel):
    email: str = ""


class ResetPasswordRequest(CamelModel):
    token: str = ""
    password: str = ""


class LoginRequest(CamelModel):
    email: str = ""
    password: str = ""
    device_id: str = Field("", alias="deviceId")


class VerifyLoginRequest(CamelModel):
    token: str = ""
    code: str = ""
    device_id: str = Field("", alias="deviceId")


class ResendCodeRequest(CamelModel):
    token: str = ""


class ChangePasswordRequest(CamelModel):
    current_password: str = Field("", alias="currentPassword")
    new_password: str = Field("", alias="newPassword")


class MeUser(CamelModel):
    id: int
    email: str
    role: str
    email_verified: bool = Field(alias="emailVerified")
    must_change_password: bool = Field(alias="mustChangePassword")
