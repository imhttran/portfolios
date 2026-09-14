"""HTTP response helpers shared by the routers.

Shapes mirror the Rust backend exactly: ``msg`` is ``{message}`` and ``fail``
adds ``success: false`` for the endpoints that return it.
"""

from __future__ import annotations

import sys
from typing import Any

from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse


def respond(status_code: int, body: Any) -> JSONResponse:
    return JSONResponse(status_code=status_code, content=jsonable_encoder(body))


def msg(message: str) -> dict[str, Any]:
    return {"message": message}


def fail(message: str) -> dict[str, Any]:
    return {"success": False, "message": message}


def internal_error(context: str, err: object, with_success: bool) -> JSONResponse:
    """Log the server-side reason, then answer with the generic 500 body."""
    print(f"{context}: {err}", file=sys.stderr)
    body = (
        fail("Internal server error") if with_success else msg("Internal server error")
    )
    return respond(500, body)


class ApiError(Exception):
    """Carries a status code and exact JSON body; handled in main.py."""

    def __init__(self, status_code: int, body: dict[str, Any]):
        super().__init__(body.get("message", ""))
        self.status_code = status_code
        self.body = body
