"""Profile request and response shapes."""

from __future__ import annotations

from pydantic import Field

from app.schemas.base import CamelModel


class ProfileInput(CamelModel):
    first_name: str = ""
    last_name: str = ""
    address: str = ""
    address2: str | None = None
    state: str = ""
    zip: str = ""
    country: str = ""
    phone: str = ""
    communication_preference: str = ""
    linkedin: str | None = None
    github: str | None = None
    alt_email: str | None = None


class ProfileOut(CamelModel):
    id: int
    user_id: int = Field(alias="userId")
    first_name: str = Field(alias="firstName")
    last_name: str = Field(alias="lastName")
    address: str
    address2: str | None = None
    state: str
    zip: str
    country: str
    phone: str
    communication_preference: str = Field(alias="communicationPreference")
    linkedin: str | None = None
    github: str | None = None
    alt_email: str | None = Field(None, alias="altEmail")
