# backend

FastAPI auth backend. The browser talks to Next.js, Next.js proxies `/api/*`
to this API server-side, and the API talks to PostgreSQL through SQLAlchemy.
The browser never reaches the API directly, so there's no CORS layer.

```
Browser
   │
   ▼
Next.js                              frontend/   :3000
   │
   ▼
FastAPI  ── api/ ──► services/       app/        :8080
                        │
                        ▼
                     SQLAlchemy  ── models/
                        │
                        ▼
                     PostgreSQL
```

## Layout

```
backend/
├── app/
│   ├── main.py            ASGI app, lifespan, session-renewal middleware
│   ├── config.py          env loading and the Settings dataclass
│   ├── cli.py             set-role, set-subscription, media housekeeping
│   ├── api/               routers and shared dependencies
│   │   ├── deps.py        get_current_user and role gating
│   │   ├── responses.py   response shapes and the ApiError type
│   │   ├── auth.py        public auth, /api/me, change-password
│   │   ├── users.py       staff/admin user management
│   │   └── profile.py     a user's own name (optional)
│   ├── models/            SQLAlchemy models (users, profiles, queue, 2FA)
│   ├── schemas/           Pydantic request/response schemas
│   ├── services/          security, roles, validation, mail, queue, seeds
│   └── db/                engine, session factory, table creation
├── tests/
├── pyproject.toml
└── README.md
```

Requests flow `api/` to `services/` to `models/`. Routers hold HTTP concerns
only, services hold the logic, models hold the mapping.

## Requirements

Python 3.11 or newer and a running PostgreSQL. On macOS with Homebrew,
`brew install postgresql@16` then `brew services start postgresql@16`.

## Setup

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

## Run

```bash
python -m app.main               # same as: uvicorn app.main:app --port 8080
```

The schema is migrated to head on boot (Alembic), so a fresh database needs no
manual setup step. In development a known admin is seeded, `admin@mail.com`
with password `Password1234!`. First login from a new browser asks for a 2FA
code, which is always `1234` in development.

## Configuration

Every variable is read from the environment. A root `.env` wins, and `.env.dev`
fills in the rest when `NODE_ENV` is unset or `development`. Existing shell
variables are never overwritten.

| Variable                      | Default                                                                     | Notes                                                                      |
| ----------------------------- | --------------------------------------------------------------------------- | -------------------------------------------------------------------------- |
| `NODE_ENV`                    | `development`                                                               | qa and production skip the dev seed                                        |
| `DATABASE_URL`                | `postgres://postgres:postgres@localhost:5432/db_portfolios?sslmode=disable` |                                                                            |
| `JWT_SECRET`                  | dev fallback                                                                | required in production, the server refuses to boot without it              |
| `PORT`                        | `8080`                                                                      | the Next.js proxy expects this port                                        |
| `FRONTEND_URL`                | `http://localhost:3000`                                                     | base for verify and reset links                                            |
| `DEVICE_TRUST_DAYS`           | `30`                                                                        | how long a browser skips 2FA after passing it; slides on each verification |
| `SMTP_HOST`                   | empty                                                                       | when empty, mail is logged instead of sent                                 |
| `SMTP_PORT`                   | `587`                                                                       | 465 uses implicit TLS, otherwise STARTTLS                                  |
| `SMTP_USER` / `SMTP_PASS`     | empty                                                                       | login only when a user is set                                              |
| `MAIL_FROM`                   | `no-reply@example.com`                                                      |                                                                            |
| `MAX_ATTEMPTS`                | `3`                                                                         | email queue retry cap                                                      |
| `EMAIL_VERIFICATION_REQUIRED` | on                                                                          | set to `false` to skip the verification gate                               |
| `MEDIA_ROOT`                  | `backend/media`                                                             | where photo files live; see `services/storage.py` for the layout           |

## API

35 endpoints under `/api`, all in `app/api/`:

Public auth. `POST /api/signup`, `GET /api/verify`, `POST
/api/resend-verification`, `POST /api/forgot-password`, `POST
/api/reset-password`, `POST /api/login`, `POST /api/login/verify`, `POST
/api/login/resend`.

Public, no session. `GET /api/media/albums`, `GET /api/media/albums/{slug}`,
`GET /api/media/photos/{id}/file`, `GET /api/artist/profile`, `GET
/api/artists`, `GET /api/artists/{slug}`.

Signed in, any role. `GET /api/me`, `GET /api/profile`, `POST /api/profile`,
`POST /api/change-password`.

Artist. `GET /api/artist/profile/mine`, `PUT /api/artist/profile`, and the six
management routes under `/api/manage/*` (list/create/edit/delete an album,
upload photos into one, delete a photo).

Signed in clients. `GET /api/media/photos/{id}/download`, `GET
/api/media/albums/{slug}/download`. Free albums need any registered user; paid
and premium need a subscription at that level.

Staff and admin. `GET /api/users`, `POST /api/users`, `DELETE
/api/users/{id}`, `PATCH /api/users/{id}/verification`, `PATCH
/api/users/{id}/role`, `POST /api/users/{id}/resend-verification`, `POST
/api/users/{id}/reset-password`. Subscriptions are granted from the CLI, not
over HTTP - see below.

A `GET /health` endpoint exists for readiness checks.

## CLI

Out-of-band tooling lives in `app/cli.py`: `set-role`, `set-subscription` and
`revoke-subscription` (who may download whose paid work), `import-album` (a
folder of photos, read in place), `prune-media` (files nothing points at),
`prune-db` (rows that are dead by definition), `restore-media` and
`relayout-media`. See the root README for the media ones.

```bash
set-role you@email.com artist
set-subscription client@example.com you@email.com --level premium
```

Roles and subscriptions are CLI-only so there is no self-service escalation and
no HTTP surface for a payment provider to be bolted onto later - when one
arrives, it writes the same `subscriptions` row.

## Roles

`client` < `artist` < `staff` < `admin`. `artist` is the content tier: it can
read and save its own public profile (`/api/artist/profile`) and publish work.
`staff` is the user-management tier. Promotion is CLI only, so there's no
self-service escalation.

```bash
set-role you@email.com artist
```

## Schema changes

Schema changes go through Alembic:

```bash
alembic revision --autogenerate -m "add foo column"
alembic upgrade head       # or just restart the server; it upgrades on boot
```

Review the generated migration before committing it - autogenerate compares
models against the live database and doesn't catch everything (renames show
up as a drop + add, for example). Tests still rebuild their schema straight
from the models (`create_all`) rather than replaying migrations, since a
from-scratch test database has no history to preserve.

`migrations/versions/9416456c0fd7_initial_schema.py` was generated once,
against an empty scratch database, so the file only contains real `CREATE
TABLE` statements instead of a no-op diff against the already-populated dev
database. If you ever need to redo that (e.g. squashing history, or setting
up on a new Postgres instance from scratch):

```bash
createdb -h localhost -U postgres db_portfolios_scratch
DATABASE_URL="postgres://postgres:postgres@localhost:5432/db_portfolios_scratch?sslmode=disable" \
  alembic revision --autogenerate -m "initial schema"
dropdb -h localhost -U postgres db_portfolios_scratch

# Then, against the real dev DB (already has matching tables from create_all,
# so this just records the revision instead of re-running the DDL):
alembic stamp head
```

## Tests

```bash
pytest                                   # unit tests, no database needed
```

The database tests skip unless `TEST_DATABASE_URL` is set.

```bash
TEST_DATABASE_URL="postgres://postgres:postgres@localhost:5432/db_portfolios_test?sslmode=disable" \
    pytest
```

They create uniquely-addressed users per run and clean up after themselves, so
reruns against a dirty database still pass.

## Notes

The scrypt password format is `salt_hex:key_hex` with the hex salt fed to
scrypt as a string, the same shape Node, Go, and Rust produced. Hashes written
by the earlier backends verify unchanged.

Sessions last ten minutes. Any successful response authorized with a token past
its half-life carries a fresh one in `X-Renewed-Token`, and the frontend
persists it. Idle sessions hard-expire and get bounced to login.
