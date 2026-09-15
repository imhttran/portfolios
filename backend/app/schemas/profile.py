"""Profile request and response shapes."""

from __future__ import annotations

from pydantic import Field

from app.schemas.base import CamelModel


class ProfileInput(CamelModel):
    first_name: str = ""
    last_name: str = ""


class ProfileOut(CamelModel):
    id: int
    user_id: int = Field(alias="userId")
    first_name: str = Field(alias="firstName")
    last_name: str = Field(alias="lastName")
