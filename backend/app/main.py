"""ASGI application entrypoint.

Wires the routers, exception handling, the sliding-session middleware, and the
startup work (create tables, seed the dev admin, start the email worker).
"""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from starlette.middleware.base import BaseHTTPMiddleware

from app.api import (
    artist,
    artists,
    auth,
    manage,
    media,
    profile,
    users,
)
from app.api.responses import ApiError, respond
from app.config import get_settings, load_env_files
from app.db.session import create_all, dispose_engine, get_sessionmaker
from app.services.email_queue import email_worker
from app.services.security import renew_token_if_due
from app.services.seeds import seed_dev_all

# Load .env/.env.dev before anything reads Settings.
load_env_files()


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    await create_all()
    # Order-sensitive; see seed_dev_all.
    await seed_dev_all(settings, get_sessionmaker())

    worker = asyncio.create_task(email_worker(settings, get_sessionmaker()))
    try:
        yield
    finally:
        worker.cancel()
        try:
            await worker
        except asyncio.CancelledError:
            pass
        await dispose_engine()


app = FastAPI(title="backend", version="0.1.0", lifespan=lifespan)


class SessionRenewalMiddleware(BaseHTTPMiddleware):
    """Slide active JWT sessions forward.

    Whenever a successful response was authorized with a token past half its
    10-minute life, a fresh one rides back on X-Renewed-Token for the client to
    persist. Idle sessions hit the hard expiry and are bounced to login.
    """

    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        if 200 <= response.status_code < 300:
            parts = request.headers.get("authorization", "").split(" ")
            token = parts[1] if len(parts) > 1 else ""
            if token:
                renewed = renew_token_if_due(token, get_settings().jwt_secret)
                if renewed:
                    response.headers["X-Renewed-Token"] = renewed
        return response


app.add_middleware(SessionRenewalMiddleware)


@app.exception_handler(ApiError)
async def _api_error_handler(request: Request, exc: ApiError):
    return respond(exc.status_code, exc.body)


app.include_router(auth.router)
app.include_router(media.router)
app.include_router(manage.router)
app.include_router(artist.router)
app.include_router(artists.router)
app.include_router(users.router)
app.include_router(profile.router)


@app.get("/health", tags=["meta"])
async def health() -> dict:
    return {"status": "ok"}


def run() -> None:
    """Console entrypoint: ``uvicorn``-equivalent in-process server."""
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=get_settings().port,
        reload=False,
    )


if __name__ == "__main__":
    run()
