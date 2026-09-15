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
- **An index of albums, and the album behind it** — `/`, `/gallery` and
  `/artist/<slug>` list the work as one tile per album (its first photograph,
  served on the album itself so an index never costs a query per tile), and
  `/album/<slug>` is the only page that shows photographs. The split is what
  keeps a page readable: inlining every frame of every album made `/gallery`
  29 screens at 1440×900. The index is deliberately _not_ a fitted sheet — a
  uniform, width-driven grid gives the same density on every visit, which is
  what makes it scannable, and the fit belongs to the album the tile leads to.
  Its covers are 5:4 with a 36px white title centred on the photograph, which is
  the reference's own cover, measured
- **Fitted album sheets** — on an album's own page the grid sits inside the page
  gutter (43px, like every other element) and the window picks the column count
  whose rows come nearest the height it has left, then stretches the rows to fill
  it. An artist may set a ceiling on how dense their own sheets get (both seeded
  artists sit at two across, so the site reads as one publication); the count
  count never exceeds it, and the artist's number wins over the fit. A stretch
  that would take a frame past 1.1:1 or 1.9:1 isn't offered, so an album that
  can't fill the window at a legible crop keeps the crop and runs on instead —
  which is every album at a two-across ceiling. That is the design reference's
  own resolution, and why the ceiling is set where it is: a fill past 1.9 is a
  letterbox, and the reference never stretches a photograph to fill a frame. The
  ceiling is per artist, so Auto is available to anyone who would rather have
  every album fill and accept a column count that varies per album. Measured in
  the browser; the CSS grid is the fallback for a visitor without JS
- **The masthead** — one flat `#111` band inside the page gutter, 540px on a
  1440 window, carrying the statement centred in white. No photograph and no
  scrim: the photographs come below, and a white page with one black band is the
  whole idea. The colour is literal rather than a token, so it stays dark in the
  dark theme too
- **The gutter** — 43px of page gutter (fixed-ish: `3vw`, clamped 20–43) and
  13px of white between tiles, in both axes, on both the index and the sheets.
  Nothing is full bleed any more: the reference's content box sits inside its
  gutter, and the 13px gap on a white page is what separates one photograph from
  the next
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
- **Theming** — the site's own look is the design reference's white, and it
  stays light rather than following the system preference, so the page is the
  page the reference renders. A dark theme still exists behind the header switch
  (remembered per browser), and an artist may put their own page in dark, light
  or paper from `/studio` — though both are seeded on the site default, so the
  site reads as one white page on first boot. A visitor's explicit choice
  outranks the artist's. All of them hold the same documented contrast ratios
- **Type is sentence case, and that is a rule, not a habit** — the reference
  carries no uppercase and no letter-spacing anywhere on it, so this has none
  either: the technical layer (labels, frame numbers, credits) is 13px plain
  text, the site name and nav are 18px, sheet and cover titles are 36px at
  weight 500, the statement is 37px over a 42px line, and the footer is 15px and
  centred
- **An artist's own theme** — dark, light, or paper (the light theme warmed
  towards a cream stock), chosen in `/studio` beside the sheet density. Two
  deliberate limits. It applies to that artist's own page only: the front page
  and `/gallery` show every artist's work at once, so they have no single answer
  to give and keep the site's theme. And a visitor's own choice outranks it —
  light picked by hand stays light on an artist's dark page. All three themes
  hold the same documented contrast ratios, so none is the legible one. Seeded
  in two different themes (Ethan dark, Ted paper) so the contrast is visible on
  first boot
