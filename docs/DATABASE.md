# Database (PostgreSQL)

Everything this project does with PostgreSQL, in one page.

## Connection

One variable: `DATABASE_URL` (a personal root `.env` overrides the dev default
in `backend/app/config.py`).

```
postgres://postgres:postgres@localhost:5432/db_template?sslmode=disable
```

- `manage.sh` (reset-database, backend startup check) reads `.env` first, then
  `.env.dev` — same precedence as the backend's environment loader.
- Changing host/port/db means changing only this URL — no code changes.

## Setting up a local instance (macOS)

**Option 1 — Homebrew service (recommended): survives reboots**

```bash
brew install postgresql@16
brew services start postgresql@16      # stop with: brew services stop postgresql@16
createuser -s postgres; psql -d postgres -c "ALTER USER postgres PASSWORD 'postgres';"
createdb db_template
```

**Option 2 — throwaway instance (no service installed): lost on reboot**

```bash
initdb -D /tmp/python-template-pg -A trust
pg_ctl -D /tmp/python-template-pg -l /tmp/python-template-pg.log start
psql -d postgres -c "CREATE USER postgres WITH PASSWORD 'postgres' SUPERUSER;"
createdb db_template -U postgres
```

Check state anytime: `pg_isready -h localhost` (this is what `manage.sh` runs
before launching the backend).

## Schema: how it's managed

Tables are defined as SQLAlchemy models under `backend/app/models/` and
created on boot by `Base.metadata.create_all`, so a fresh database needs no
migration step and a second boot is a no-op.

Schema changes: edit or add a model and restart the backend. `create_all` only
creates missing tables, so a column change on an existing table needs a manual
`ALTER` or a reset. Add Alembic if you outgrow this.

Tables:

| Table           | Purpose                                                              |
| --------------- | -------------------------------------------------------------------- |
| `users`         | accounts: email, scrypt password, role, verify/reset tokens          |
| `user_profiles` | one-time registration details (`ON DELETE CASCADE`)                  |
| `email_queue`   | outbound mail (processed by the worker in `services/email_queue.py`) |
| `user_devices`  | trusted devices that skip 2FA                                        |
| `login_codes`   | pending 2FA codes                                                    |

Dev seed (in `backend/app/services/seeds.py`, only when
`NODE_ENV=development`): upserts `admin@mail.com` / `Password1234!` plus their
profile, so the dev admin isn't blocked by onboarding gates.

## Day-to-day operations

| Task               | Command                                                                       |
| ------------------ | ----------------------------------------------------------------------------- |
| Status             | `pg_isready -h localhost` or `./manage.sh` → 5                                |
| Reset **all** data | `./manage.sh` → 9 (drops and recreates the `public` schema)                   |
| Manual reset       | `psql "$DATABASE_URL" -c 'DROP SCHEMA public CASCADE; CREATE SCHEMA public;'` |
| Look around        | `psql db_template -U postgres` → `\dt`, `\d users`                            |
| Promote a user     | `./manage.sh` → 8 (runs `python -m app.cli set-role`)                         |

`manage.sh` option 9 asks for lowercase `yes` since `DROP SCHEMA public
CASCADE` destroys all data. It reads the same `DATABASE_URL` chain described
above.

## Tests

`backend/tests/` integration tests need a reachable Postgres and are skipped
otherwise:

```bash
cd backend
TEST_DATABASE_URL="postgres://postgres:postgres@localhost:5432/db_template_test?sslmode=disable" .venv/bin/pytest
```

The tests create unique-email users per run and clean up after themselves, so
reruns against a dirty database still pass. `./manage.sh` → 6 runs them when
`TEST_DATABASE_URL` is set in your environment.

## Production

Any managed PostgreSQL (RDS, Cloud SQL, Neon, a Docker container) works: set
`DATABASE_URL` in the environment (`NODE_ENV=production` loads no `.env.dev`,
and only the backend's server environment matters — the frontend never touches
Postgres). Tables are created on first boot against an empty database.
