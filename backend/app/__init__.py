"""FastAPI port of the Rust/axum auth API.

Layering: api/ (HTTP) -> services/ (domain logic) -> models/ (SQLAlchemy) ->
PostgreSQL. Config lives in config.py; the ASGI app is main.py.
"""

__version__ = "0.1.0"
