# Features

- **Auth** — JWT login with 10-minute sliding sessions (renewed past half-life
  on every successful request; idle sessions hard-expire), scrypt password
  hashing, email verification, password
  reset, resend-verification, self-service change-password, email-code 2FA on
  new devices. A device that has passed 2FA stays trusted for a month, and the
  window slides with use (`DEVICE_TRUST_DAYS`), so an active browser isn't asked
  again and an abandoned one is
- **RBAC** — `client` < `artist` < `staff` < `admin` roles with role-gated
  routes; `artist` is the content tier (site copy, and publishing work) while
  `staff` is the user-management tier; promotion is CLI-only so there's no
  self-service escalation
- **Artist profile** — the site's public copy (name, tagline, statement, bio,
  location, contact) is editable in `/studio` and stored per artist; each artist
  gets a page at `/artist/<slug>`
- **Roster and artist pages** — `/` is the primary artist's portfolio and links
  to everyone else; `/api/artists` lists the roster and `/api/artists/{slug}`
  serves one artist's words and work. The client area names each album's artist,
  since a subscribe prompt has to say _who_ it is for
- **Fitted album sheets** — every album sizes itself to the frame it is shown in.
  The grid solves its column count from the window, so a four-photo album fills
  the screen instead of leaving half of it empty, and a twenty-seven-photo album
  stops running on for two. Cells keep one 3:2 crop, so an album still reads as a
  contact sheet, and the grid is allowed to come in from the edges when a tall
  frame needs that to fill. Measured in the browser; the CSS grid is the fallback
  for a visitor without JS
- **Free / paid / premium tiers** — an album sits on one ladder. `free` is
  downloadable by any registered user; `paid` and `premium` need a subscription at
  that level or above (plus the artist, and staff/admin). Looking is never gated,
  only downloading. Unpublishing an album hides it and its photos at once
- **Subscriptions** — one customer's access to one artist's work, at a level
  (`paid` or `premium`) that names the highest tier it opens, so the ladder only
  reaches down. Per artist, so subscribing to one does not open another's paid
  work. Granted from the CLI (`python -m app.cli set-subscription`), which is
  also how roles are granted: no payment provider is wired up, so a human writes
  the row deliberately. When one is, it writes the same row
- **Image pipeline** — uploads become three files via Pillow: the original (what
  a download hands over) plus a preview and thumbnail that pages actually load,
  so a public gallery never streams full-resolution work. EXIF rotation is baked
  in and the derived files carry no metadata (EXIF often holds GPS coordinates)
- **Browser uploads and album management** — in `/studio` an artist creates
  albums in a bucket, uploads up to 20 files at a time, moves an album between
  buckets, hides or publishes it, and deletes it along with its files. The
  upload reply is per file, so one bad file doesn't lose the rest, and ownership
  is enforced: an artist manages their own albums, staff/admin manage anyone's
- **Folder import** — `python -m app.cli import-album` ingests an existing folder
  of photos in place: it copies the originals into the storage layout, generates
  the previews and thumbnails, and creates the photo rows. Idempotent, and it
  reports non-images (RAW, video) rather than guessing at them
- **Forced password change** — an account created by an admin (temporary
  password) can reach `/api/me`, `/api/change-password`, and the downloads, and
  nothing else until the password is changed. There is no second gate: nothing
  asks a user for a registration form, and the name on `/profile` is optional
- **Admin user management** — create, delete, verify/unverify, change role,
  and trigger password resets from the dashboard
- **Email queue** — Postgres-backed queue with a bounded-retry worker; logs to
  stdout when no SMTP is configured, so dev needs no mail server
- **Enumeration-safe endpoints** — generic responses on signup/forgot-password
  so the API can't be used to probe registered emails
- **Server-side proxy** — the browser only talks to Next.js; `/api/*` is
  forwarded to the FastAPI backend, so it's never exposed directly
- **Theming** — a monochrome editorial palette (ink/paper, no accent colour)
  in both a dark and a light theme, switched from the header, remembered per
  browser, and defaulting to the system preference. Mono type is reserved for
  the technical layer: frame numbers, credits, the footer. The hero over a
  photograph, and the viewer, stay dark in either theme, because there the scrim
  behind the type sets the contrast rather than the page
