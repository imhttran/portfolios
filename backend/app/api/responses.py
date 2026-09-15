"""HTTP response helpers shared by the routers.

One shape, everywhere: an error body is ``{message}`` and nothing else, so a
client reads ``message`` and an HTTP status without a second convention to
learn.
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


def internal_error(context: str, err: object) -> JSONResponse:
    """Log the server-side reason, then answer with the generic 500 body."""
    print(f"{context}: {err}", file=sys.stderr)
    return respond(500, msg("Internal server error"))


class ApiError(Exception):
    """Carries a status code and exact JSON body; handled in main.py."""

    def __init__(self, status_code: int, body: dict[str, Any]):
        super().__init__(body.get("message", ""))
        self.status_code = status_code
        self.body = body
