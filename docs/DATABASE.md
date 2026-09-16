# Database (PostgreSQL)

Everything this project does with PostgreSQL, in one page.

## Connection

One variable: `DATABASE_URL` (a personal root `.env` overrides the dev default
in `backend/app/config.py`).

```
postgres://postgres:postgres@localhost:5432/db_portfolios?sslmode=disable
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
createdb db_portfolios
createdb db_portfolios_test            # only needed to run the integration tests
```

**Option 2 — throwaway instance (no service installed): lost on reboot**

```bash
initdb -D /tmp/portfolios-pg -A trust
pg_ctl -D /tmp/portfolios-pg -l /tmp/portfolios-pg.log start
psql -d postgres -c "CREATE USER postgres WITH PASSWORD 'postgres' SUPERUSER;"
createdb db_portfolios -U postgres
```

Check state anytime: `pg_isready -h localhost` (this is what `manage.sh` runs
before launching the backend).

## Schema: how it's managed

Tables are defined as SQLAlchemy models under `backend/app/models/` and created
on boot by `Base.metadata.create_all`, so a fresh database needs no migration
step and a second boot is a no-op.

**There is no migration tool.** `create_all` only _creates_ missing tables: it
will not add a column to an existing table, and it will not drop one the models
no longer declare (a renamed table keeps its foreign keys and blocks the drop).
So a model change needs a reset — `./manage.sh` → 9 — after which the dev seeds
rebuild the data. Add Alembic if you outgrow this.

Tables:

| Table             | Purpose                                                                                                                          |
| ----------------- | -------------------------------------------------------------------------------------------------------------------------------- |
| `users`           | accounts: email, scrypt password, role, verify/reset tokens                                                                      |
| `user_profiles`   | a user's name, optional (`ON DELETE CASCADE`)                                                                                    |
| `artist_profiles` | the public copy each artist edits in `/studio`, their URL slug, the theme their own page wears, and their sheet's column ceiling |
| `albums`          | a portfolio, its owning artist, and its tier on the free/paid/premium ladder                                                     |
| `photos`          | ordered photos: original + preview + thumbnail, and their dimensions                                                             |
| `subscriptions`   | one customer's access to one artist, at a level (`paid`/`premium`)                                                               |
| `email_queue`     | outbound mail (processed by the worker in `services/email_queue.py`)                                                             |
| `user_devices`    | browsers that skip 2FA, until their trust lapses                                                                                 |
| `login_codes`     | pending 2FA codes                                                                                                                |

Dev seeds (in `backend/app/services/seeds.py`, only when `NODE_ENV=development`),
all with the password `Password1234!`:

| Login              | Role   | Subscribed                               |
| ------------------ | ------ | ---------------------------------------- |
| `admin@mail.com`   | admin  | —                                        |
| `artist@mail.com`  | artist | owns the three seeded placeholder albums |
| `ted@mail.com`     | artist | owns nothing yet — see below             |
| `client@mail.com`  | client | `paid` on both artists                   |
| `premium@mail.com` | client | `premium` on both                        |

Each gets a first and last name. Two
artist profiles are seeded, three placeholder albums for the first artist (one
per tier), and four subscriptions — one customer at each level, subscribed to
both artists.

**Ted's albums are not seeded.** They came from importing a folder of his
photographs, which is not reproducible from an empty database:

```bash
.venv/bin/python -m app.cli import-album --artist ted@mail.com \
  --dir ~/Downloads/album-d489480890-downloads \
  --slug wetlands --title "Wetlands" --access paid
```

So after a reset, `ted@mail.com` has a page with no work until a folder is
imported for them. That is the honest state of a fresh database, not a bug.

**A reset does not delete the files, though.** If his albums vanish but
`MEDIA_ROOT` still holds them, `restore-media` rebuilds the rows from the tree —
no re-import, and the three photos added through the browser come back too:

```bash
.venv/bin/python -m app.cli restore-media --tier wetlands=paid \
  --tier field-notes=free --tier studio-selects=premium --yes
```

## Day-to-day operations

| Task               | Command                                                                       |
| ------------------ | ----------------------------------------------------------------------------- |
| Status             | `pg_isready -h localhost` or `./manage.sh` → 5                                |
| Reset **all** data | `./manage.sh` → 9 (drops and recreates the `public` schema)                   |
| Manual reset       | `psql "$DATABASE_URL" -c 'DROP SCHEMA public CASCADE; CREATE SCHEMA public;'` |
| Recover media rows | `./manage.sh` → 12 (rebuild rows for photos on disk with no row)              |
| Move media layout  | `./manage.sh` → 13 (move files/rows into `artists/{id}-{slug}/`; one-off)     |
| Look around        | `psql db_portfolios -U postgres` → `\dt`, `\d users`                          |
| Promote a user     | `./manage.sh` → 8 (runs `python -m app.cli set-role`)                         |

Option 12 is additive, so it confirms rather than warning: it runs
`restore-media --dev-tiers` first and shows what it would rebuild. Reach for it
when the site is missing photos you know are on disk — an album deleted by
mistake, or a database restored from a backup that predates some uploads. The
backend also does this on boot, so a reset recovers without the menu.

The CLI creates the schema when it is missing, the same way the backend does on
boot, so a freshly reset database no longer fails with `relation "users" does
not exist`. It still needs the **artists** to exist first: `restore-media`
matches each `artists/{id}-{slug}/` folder in `MEDIA_ROOT` to a user id and
skips a folder whose user is gone. So after a reset, let the backend boot - it
seeds the users - before restoring media, or every album is reported as
`(no user 3)`.

`manage.sh` option 9 asks for lowercase `yes` since `DROP SCHEMA public
CASCADE` destroys all data. It reads the same `DATABASE_URL` chain described
above.

## Tests

`backend/tests/` integration tests need a reachable Postgres and are skipped
otherwise:

```bash
cd backend
TEST_DATABASE_URL="postgres://postgres:postgres@localhost:5432/db_portfolios_test?sslmode=disable" .venv/bin/pytest
```

The tests drop and recreate the schema themselves, so they always match the
models — a model change needs no manual reset there. They also create
unique-email users per run and clean up after themselves, so reruns against a
dirty database still pass. `./manage.sh` → 6 runs them when `TEST_DATABASE_URL`
is set in your environment.

## Production

Any managed PostgreSQL (RDS, Cloud SQL, Neon, a Docker container) works: set
`DATABASE_URL` in the environment (`NODE_ENV=production` loads no `.env.dev`,
and only the backend's server environment matters — the frontend never touches
Postgres). Tables are created on first boot against an empty database.
