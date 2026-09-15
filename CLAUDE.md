# python-template

Full-stack auth template: Next.js (`frontend/`, :3000) → FastAPI (`backend/`, :8080) → PostgreSQL. Browser only ever talks to Next.js; FastAPI is proxied server-side, never exposed directly. Full architecture, roles, tiers, and API list: `README.md`.

## Commands

```bash
./manage.sh       # single entry point: [7] first-time setup, [1] start all, [5] status,
                   # [6] tests, [9] reset DB, [10] tail logs, [11] re-seed, [8] grant role
```

Needs Python 3.11+, Node 20+, and a running PostgreSQL (`[1]` refuses to start if it's down).

- Tests: `./manage.sh` → `[6]` (backend pytest + frontend build). Integration tests need `TEST_DATABASE_URL` (see `docs/DATABASE.md`); without it they skip and unit tests still run.
- Lint: `ruff` in `backend/` (config in `backend/pyproject.toml`); `prettier` at root.
- Role/subscription grants are CLI-only — no self-service promotion (`backend/app/cli.py`, or `./manage.sh` → `[8]`).

Dev admin: `admin@mail.com` / `Password1234!` (2FA code in dev is always `1234`). More logins in `README.md`.

## Docs

- `backend/README.md` — backend layout, config, endpoints
- `docs/FEATURE.md` — what this build does
- `docs/DATABASE.md` — Postgres install, schema, reset, tests

## Gotchas

- **Alembic migrations**: generate against a scratch empty DB, not the populated dev DB — otherwise `autogenerate` produces a no-op diff instead of real `CREATE TABLE`/`ALTER TABLE` statements. Then `alembic stamp head` reconciles the real DB without replaying the DDL.
- Postgres empty-string column defaults need `server_default=text("''")` (quoted literal) — `text("")` produces invalid SQL.
- `command.upgrade()` is sync but its async `env.py` calls `asyncio.run()`; run it via `asyncio.to_thread` when called from FastAPI's already-running lifespan loop (see `app/db/session.py`).
- A database reset drops rows but not files under `MEDIA_ROOT`; the seed step rebuilds rows for orphaned files on boot. Manual repair: `app/cli.py restore-media` / `prune-media`.
