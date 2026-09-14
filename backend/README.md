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
│   ├── cli.py             the set-role command
│   ├── api/               routers and shared dependencies
│   │   ├── deps.py        get_current_user and role gating
│   │   ├── responses.py   response shapes and the ApiError type
│   │   ├── auth.py        public auth, /api/me, change-password
│   │   ├── users.py       staff/admin user management
│   │   └── profile.py     registration profile
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

Tables are created on boot, so a fresh database needs no migration step. In
development a known admin is seeded, `admin@mail.com` with password
`Password1234!`. First login from a new browser asks for a 2FA code, which is
always `1234` in development.

## Configuration

Every variable is read from the environment. A root `.env` wins, and `.env.dev`
fills in the rest when `NODE_ENV` is unset or `development`. Existing shell
variables are never overwritten.

| Variable                      | Default                                                                   | Notes                                                         |
| ----------------------------- | ------------------------------------------------------------------------- | ------------------------------------------------------------- |
| `NODE_ENV`                    | `development`                                                             | qa and production skip the dev seed                           |
| `DATABASE_URL`                | `postgres://postgres:postgres@localhost:5432/db_template?sslmode=disable` |                                                               |
| `JWT_SECRET`                  | dev fallback                                                              | required in production, the server refuses to boot without it |
| `PORT`                        | `8080`                                                                    | the Next.js proxy expects this port                           |
| `FRONTEND_URL`                | `http://localhost:3000`                                                   | base for verify and reset links                               |
| `SMTP_HOST`                   | empty                                                                     | when empty, mail is logged instead of sent                    |
| `SMTP_PORT`                   | `587`                                                                     | 465 uses implicit TLS, otherwise STARTTLS                     |
| `SMTP_USER` / `SMTP_PASS`     | empty                                                                     | login only when a user is set                                 |
| `MAIL_FROM`                   | `no-reply@example.com`                                                    |                                                               |
| `MAX_ATTEMPTS`                | `3`                                                                       | email queue retry cap                                         |
| `EMAIL_VERIFICATION_REQUIRED` | on                                                                        | set to `false` to skip the verification gate                  |

## API

Nineteen endpoints under `/api`, matching the previous backend route for route.

Public auth. `POST /api/signup`, `GET /api/verify`, `POST
/api/resend-verification`, `POST /api/forgot-password`, `POST
/api/reset-password`, `POST /api/login`, `POST /api/login/verify`, `POST
/api/login/resend`.

Signed in, any role. `GET /api/me`, `GET /api/profile`, `POST /api/profile`,
`POST /api/change-password`.

Staff and admin. `GET /api/users`, `POST /api/users`, `DELETE
/api/users/{id}`, `PATCH /api/users/{id}/verification`, `PATCH
/api/users/{id}/role`, `POST /api/users/{id}/resend-verification`, `POST
/api/users/{id}/reset-password`.

A `GET /health` endpoint exists for readiness checks.

## Roles

`client` < `staff` < `admin`. Promotion is CLI only, so there's no
self-service escalation.

```bash
set-role you@email.com admin
```

## Tests

```bash
pytest                                   # unit tests, no database needed
```

The database tests skip unless `TEST_DATABASE_URL` is set.

```bash
TEST_DATABASE_URL="postgres://postgres:postgres@localhost:5432/db_template_test?sslmode=disable" \
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
