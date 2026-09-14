"""Declarative base shared by every ORM model."""

from __future__ import annotations

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Base class for all models; ``Base.metadata`` drives table creation."""
