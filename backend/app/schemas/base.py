"""Shared Pydantic configuration for request/response schemas."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict
from pydantic.alias_generators import to_camel


class CamelModel(BaseModel):
    """Accepts camelCase or snake_case on the wire, exposes snake_case in Python.

    ``extra="ignore"`` and ``coerce_numbers_to_str`` reproduce the Rust
    backend's deliberately permissive decode: unknown fields are dropped and a
    wrong-but-coercible type does not blow up before validation runs.
    """

    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
        extra="ignore",
        coerce_numbers_to_str=True,
    )
