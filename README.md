# portfolios

A photo portfolio that doubles as a client delivery tool: **Next.js → FastAPI →
PostgreSQL**. Artists own their pages and albums; what a visitor can download depends
on their subscription tier. The browser only ever talks to Next.js; the FastAPI backend
is proxied server-side and never exposed directly.

```
Browser
   ↓
Next.js        frontend/    → :3000   React UI, routing, SSR/static gen, server components
   ↓
FastAPI        backend/     → :8080   SQLAlchemy + JWT + scrypt + email worker
   ↓
PostgreSQL     tables created on boot
```

## Demo

A 3:44 walkthrough of the whole site: public browsing, admin sign-in with 2FA on a new
device, creating an account and promoting it to artist, an artist starting and tiering
an album, and the centrepiece — the same premium album showing every frame `Locked` for
a paid client, then unlocked with a real download for a premium one.

https://github.com/user-attachments/assets/63a2f2b1-6ee7-4b5a-a87b-8052746b7a83

Full-quality 1080p cut: [demo-v1 release](https://github.com/imhttran/portfolios/releases/tag/demo-v1).
How it is recorded, and this app's gotchas: [demo/NOTES.md](demo/NOTES.md). Scene list
and honest caveats: [demo/demo-plan.md](demo/demo-plan.md).

## Quick Start

```bash
./manage.sh       # → [7] First-Time Setup, then → [1] Start All
```

Needs Python 3.11+ (manage.sh finds one, or set `PYTHON`), Node 20+, and a
running PostgreSQL (option 1 refuses to start if it's down). Dev admin:
**admin@mail.com** / **Password1234!** — first login from a new browser asks for
a 2FA code; in development it's always `1234`, and the browser is trusted
afterwards.

Useful menu options beyond setup/start: [5] status, [6] tests, [9] reset DB,
[10] tail logs, [11] re-seed (drop DB + restart backend), [12] restore media rows
(rebuild database rows for photos that are on disk but have no row — what a reset
erases for work that arrived by importing or uploading rather than by seeding),
[13] relayout media (move files into the current layout; a one-off).

## Docs

- **[backend/README.md](backend/README.md)** — the backend, its layout, config, and endpoints
- **[docs/FEATURE.md](docs/FEATURE.md)** — what this build does
- **[docs/DATABASE.md](docs/DATABASE.md)** — install Postgres, schema, reset, tests

## Tests

`./manage.sh` → 6 runs backend pytest + frontend build. Backend integration
tests need `TEST_DATABASE_URL` (see docs/DATABASE.md); without it they skip and
the unit tests still run.

## Roles

`client` < `artist` < `staff` < `admin`. `artist` carries content
powers (editing the site's public copy in `/studio`, and publishing work into a
free or paid bucket); `staff` adds user management. Grant via CLI only (no
self-service promotion):

```bash
cd backend && .venv/bin/python -m app.cli set-role you@email.com artist
# or: ./manage.sh → [8]
```

Dev logins, all with the password `Password1234!`:

| Login              | Role   | Subscribed                                    |
| ------------------ | ------ | --------------------------------------------- |
| `admin@mail.com`   | admin  | — (staff/admin can download anything)         |
| `artist@mail.com`  | artist | owns the four seeded albums                   |
| `ted@mail.com`     | artist | owns Wetlands, Field Notes and Studio Selects |
| `client@mail.com`  | client | `paid` on both artists — premium stays locked |
| `premium@mail.com` | client | `premium` on both — opens every tier          |

Two customers at different levels on purpose, so the ladder is visible on first
boot (the paid one sees premium locked) _and_ there is a login that can open
everything. Both subscribe to both artists, which is also the demo of levels
being per artist rather than global.

See who can download what at a glance: `GET /api/media/albums` answers per
caller, so the same page shows different locks depending on who is signed in.

## Artists

An artist is a user with the `artist` role, a profile they edit in `/studio`,
and their own albums. Each gets a page at `/artist/<slug>` (derived from their
display name when the profile is first saved, then left alone so links survive a
rename).

- `/` is the **front page**: the primary artist's statement and the roster of
  artists, above an index of every published album. The primary artist's copy
  (statement, About, footer) gives the site its voice.
- `/artist/<slug>` is one artist's own page — their words, and an index of their
  albums.
- `/gallery` is the **client area**: the whole catalogue as an index, with each
  album's tier shown.
- `/album/<slug>` is **the only page that shows photographs**, and where an album
  is downloaded. The index pages send you here rather than inlining every frame,
  which is what keeps them readable.
- Subscriptions are **per artist**, so a customer subscribing to one artist does
  not open another artist's paid work.

## Adding photos

Two ways in, and they write to exactly the same place (both call
`services/uploads.py`):

**In the browser** — `/studio` lists your albums. Make one with a title and a
bucket, then _Add photos_ picks up to 20 files at a time (30 MB each). The reply
is per file: a batch with one bad file adds the rest and names what it skipped.
You can also edit an album's title, credit and description (_Edit copy_), move it
between buckets, hide or publish it, and delete it (which deletes its files too).

The **credit** is for work shot by someone else. Your own albums already name you,
so a credit that just repeats your name isn't shown — which is why a blank credit
is the normal state for your own work.

**From a folder on disk** — for a whole shoot, which is what the importer is for:

```bash
cd backend
.venv/bin/python -m app.cli import-album \
  --artist ted@mail.com \
  --dir ~/Downloads/album-d489480890-downloads \
  --slug wetlands --title "Wetlands" --access paid
```

The folder is read **in place** - nothing is moved or modified - and files land
under `MEDIA_ROOT` in the layout described in `services/storage.py`:

```
originals/artists/{artist}/{album}/{name}.jpg          what a download hands over
public/artists/{artist}/{album}/{name}-preview.webp     what a page loads
public/artists/{artist}/{album}/{name}-thumb.webp
```

`{artist}` is the user id plus their slug when they have a profile
(`4-ted-nguy`), so browsing the tree says whose work it is - and the bare id when
they don't, so an album owned by someone without an artist profile still works.
**One scheme for every photo**, placeholders included: `media/` otherwise reads
as two different things jumbled together, only one of which names the artist.

Older databases used `artists/{id}/`, and the placeholders sat loose at the media
root. `./manage.sh` → 13 (`relayout-media`) moves both into the layout above; it's
a no-op once done.

Why not point `MEDIA_ROOT` at the folder and leave it there: `MEDIA_ROOT` holds
_every_ artist's originals and all derived files, so it can't be one album; the
gallery needs a row per photo to know the dimensions and which files belong
together; and without previews a public page would serve multi-megabyte
originals.

Re-running the importer only imports what's new, and non-images are **reported,
not guessed at**. Video is deliberately out of scope for now: it needs decode for
a poster frame, range requests for playback, and a place to live that isn't the
`photos` table. RAW needs a decoder we don't have. Both are reported by name so
nothing vanishes silently.

### When a reset loses work

A database reset drops the rows but **not** the files. Anything that didn't come
from the seeds - an imported folder, a browser upload - disappears from the site
while every file sits untouched under `MEDIA_ROOT`.

**This repairs itself on boot.** The seeds finish by rebuilding rows for photos
that are on disk but not in the database, using the demo's declared tiers, so a
reset no longer empties an artist's page. Files are the durable asset; the rows
can always be derived from them.

To do it by hand, or for work whose tiers aren't in the seed map, the media tree
describes itself well enough to rebuild from:

```bash
.venv/bin/python -m app.cli restore-media \
  --tier wetlands=paid --tier field-notes=free --tier studio-selects=premium
                                   # report: what would come back
.venv/bin/python -m app.cli restore-media ... --yes
```

The tier has to be passed in, because filenames deliberately don't record it -
the database is the only place a bucket lives. Everything else comes off the
files: the album slug and owner from the path, the title from the file name, the
dimensions from the image header. Additive and idempotent, so it's safe on a
database that only lost part of its data.

`prune-media` is the same idea in reverse — it reports files with no rows. If it
reports orphans after a reset, that's the signal to run this instead of deleting
them.

### Cleaning up leftovers

Files are written before their database row is committed, so a run that dies in
between leaves files with nothing pointing at them. Report them, then delete:

```bash
.venv/bin/python -m app.cli prune-media          # what would go
.venv/bin/python -m app.cli prune-media --yes    # delete them
```

### Database upkeep

Two tables grow on their own, because nothing in the app removes from them:
`login_codes` (one row per login) and `email_queue` (one row per email, which
delivery only _marks_ sent). Dead rows — codes that are used or expired, devices
whose 2FA trust has lapsed, and emails delivered or given up more than a week ago
— are dropped by:

```bash
.venv/bin/python -m app.cli prune-db                     # report only
.venv/bin/python -m app.cli prune-db --yes
.venv/bin/python -m app.cli prune-db --yes --keep-days 0  # clear the mail log now
```

Recent delivered email is deliberately kept (so "did that email go out?" stays
answerable) and `pending` mail is never touched, however old. The command also
reports referential orphans and any album with no photos. A production
deployment would run it on a schedule.

## Free, paid and premium

An album sits on one ladder:

| Tier      | Who can see it | Who can download it                                                               |
| --------- | -------------- | --------------------------------------------------------------------------------- |
| `free`    | anyone         | **any registered user**                                                           |
| `paid`    | anyone         | a subscriber at level `paid` **or** `premium`, the album's artist, or staff/admin |
| `premium` | anyone         | a subscriber at level `premium`, the album's artist, or staff/admin               |

A subscription's **level** names the highest tier it opens, so the ladder only
reaches _down_: premium opens paid albums too, never the reverse. Looking is
never gated — only taking a copy is.

Subscriptions are granted from the CLI, the same way roles are; there is no
payment provider wired up yet. The dev database seeds one customer at each
level, so the ladder can be seen without changing anything — sign in as
`client@mail.com` to see premium locked, or `premium@mail.com` to see it open.

```bash
# Give a customer access to one artist's paid work.
.venv/bin/python -m app.cli set-subscription client@mail.com ted@mail.com
.venv/bin/python -m app.cli set-subscription client@mail.com ted@mail.com --level premium
.venv/bin/python -m app.cli revoke-subscription client@mail.com ted@mail.com
```

Both commands need `DATABASE_URL` in the environment (`manage.sh` sets it, and
there is a menu entry for granting one).

## API

35 endpoints under `/api/*` — see `backend/app/api/`:

- **Public auth** (8): signup, verify, resend-verification, forgot-password,
  reset-password, login, login/verify (2FA code), login/resend (2FA code)
- **Public, no session** (6): media album list/detail, photo previews, the
  primary artist's profile, the artist roster, one artist by slug
- **Self-service, any signed-in user** (4): me, profile (get/save),
  change-password
- **Artist** (2): read/save your own public profile
- **Artist management** (6): list/create/edit/delete your albums, upload photos
  into one, delete a photo
- **Signed-in clients** (2): download one photo, download an album as a zip
- **Staff/admin** (7): list users, create user, delete, verify/unverify,
  change role, resend verification, reset password
