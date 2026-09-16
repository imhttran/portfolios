# Demo plan — portfolios walkthrough (produced)

Final: `demo.mp4` — **224.4s (3.7 min), 22 MB**, 1920x1080, H.264/AAC, no music, cuts
only, 14 scenes. Inside the skill's 3–5 minute target window.

## Story

One idea carries it: **access is per-person**. The studio sets the rules, artists own
their pages, clients see only what their tier allows. The centrepiece is scenes 12–13
— the same premium album, viewed by a paid client (every frame `Locked`) and then by
a premium client (`Download all 24`, lightbox, per-frame download).

Two beats exist to prove the screens are real rather than mocked: the admin **creates
an account** and then **promotes it to artist** (scenes 5–6), and the artist **starts a
new album** and tiers it (scene 9). Both write actual rows.

| #   | Scene              | Starts | Purpose                                                               |
| --- | ------------------ | ------ | --------------------------------------------------------------------- |
| 1   | `hook`             | 0:01   | What this is, the stack, and that access is per-person                |
| 2   | `public_browse`    | 0:18   | Looking is free; the gate is on taking a copy                         |
| 3   | `admin_signin`     | 0:32   | Studio-wide control starts here; 2FA on a new device                  |
| 4   | `admin_users`      | 0:46   | Every account and role; the role is a DB column every endpoint checks |
| 5   | `admin_adduser`    | 1:07   | **Writes a row** — account created, starts as a client                |
| 6   | `admin_grant_role` | 1:22   | **Writes a row** — promoted to artist; role ≠ presence on the site    |
| 7   | `studio_words`     | 1:34   | The artist's own copy — statement, bio, About                         |
| 8   | `studio_albums`    | 1:49   | Where an album gets its tier                                          |
| 9   | `studio_newalbum`  | 2:05   | **Writes a row** — new album, paid bucket, starts hidden              |
| 10  | `admin_all_albums` | 2:19   | Staff oversight: the same endpoint, a wider query                     |
| 11  | `artist_page`      | 2:37   | Each artist gets their own front door                                 |
| 12  | `client_locked`    | 2:49   | Paid tier hits a premium album: 24 frames `Locked`                    |
| 13  | `client_premium`   | 3:10   | Premium tier: unlocked, lightbox, real download                       |
| 14  | `theme_close`      | 3:27   | Theming, then the one-line summary                                    |

Spoken text: `narration.txt`. Per-scene structure and actions: `workflow.json`.

## What "technical" means here

The app has no architecture page to film, so the technical detail is carried two ways:
in the narration (the stack, the role column, per-artist subscriptions, the same
endpoint answering per caller, roles vs profiles) and in the three scenes that write
to the database, where you see the mechanics rather than a description of them.

## Pace

Tightened once, on request, by two levers — neither of which touches the approved
voice's character:

- **Holds cut from 2.0s to 1.5s** (`PAD` in `record.cjs`). This is the bulk of it: a
  full breath after every one of 14 lines is what made the take feel leisurely.
- **Narration time-stretched 5%** (`ffmpeg -filter:a atempo=1.05`, pitch-preserving).
  `public_browse` is the exception, held at its original rate: it was already the
  fastest line at 170 wpm, and a further 5% would have crossed the skill's 175 wpm
  guardrail. Doing it this way _narrows_ the spread (125–170 → 131–170 wpm) instead of
  pushing the top of the range past the limit.

Asking the model for a brisker pace in the voice instructions was tried first and
abandoned: across all 14 clips it moved the mean by ~1%, made four clips _slower_, and
pushed one to 174 wpm. That is run-to-run noise, not a lever.

## Reproduce

```bash
node ~/.claude/skills/demo-video/scripts/driver.mjs all
python3 demo/make-workflow.py     # regenerate workflow.json from the new marks
```

The pace step is **not** part of that chain — `driver.mjs narrate` regenerates clips at
narrate.sh's stock rate. To reproduce the shipped audio, apply the 5% stretch after
generating (see `NOTES.md` → "Pace"), then paste the new durations into `AUD` and
re-record. The shipped file is then compressed from the mix output, which `mix.py` does
not do itself — see `NOTES.md` → "Output compression". `demo/demo-master.mp4` is the
uncompressed master; re-encode from that rather than from `demo.mp4`.

The pipeline lives in the single global `demo-video` skill. This project contributes
`demo.config.json`, `record.cjs`, `scenes.json`, `NOTES.md` and `make-workflow.py`
(tracked); the media in `demo/` is generated and gitignored.

## Honest notes

- **Both data-entry scenes write for real, and the take cleans up after itself.**
  The admin creates `jordan@mail.com` (a client, then promoted to artist) and the
  artist creates a `Nightfall` album in the paid bucket. Both are deleted through the
  app's own API, off camera, before the take and again after it, so every run starts
  and ends on the seeded database. Nothing is deleted on screen and nothing drifts.
- **The new album is deliberately left unpublished.** A hidden album is filtered out
  of every public listing, so scene 9 can add a row without the front page, the
  gallery or the album counts changing underneath scenes 2 and 14.
- **Every persona swap and every write is asserted.** A silent auth no-op in this app
  still renders a plausible page — the previous take's "paid client is locked out"
  scene showed download buttons while the narration contradicted it. The recorder now
  asks `/api/me` who it actually is after each swap, and fails the take rather than
  recording something wrong.
- **Personas carry auth keys only.** This app persists the theme in `localStorage`, so
  copying a captured session wholesale also copied its saved dark preference: the
  picture could flip mid-take and the closing theme toggle could become a no-op. Only
  `auth_token` and `device_id` cross now; the take owns the theme.
- **Roles are a DB column, presence is a profile.** Promoting `jordan@mail.com` to
  `artist` gives the account the powers but does not put them on the site, because the
  roster is built from `ArtistProfile` rows and a profile only appears once someone
  saves one in `/studio`. That is why a promoted account can't leak into scene 14.
- **The shipped `demo.mp4` is a post-processed encode, not `mix.py`'s output.** It is
  compressed 45.3 → 22.0 MB (crf 26, audio downsampled from 96 kHz to 44.1 kHz mono at
  112 kbit/s), SSIM 0.9975 against the master. Small mono text stays crisp at 2× zoom,
  which is the check that matters for a UI demo — SSIM alone is generous with flat
  screen content. `demo/demo-master.mp4` keeps the uncompressed version.
- **Only the admin login is performed on camera** (so the 2FA step is visible). The
  artist and both clients are pre-authenticated off camera to avoid spending ~40s of a
  3.7-minute demo on repeated login ceremonies.
- **Scene 4 waits for the table before it starts.** `/api/users` has to return before
  the users table has rows, and that scene's narration opens by describing what is on
  screen. Marking the scene first put the opening line over an empty shell for a beat
  on a cold dev server, so the recorder now waits for the first row and marks after.
- **One narration line was reworded for pacing, not for content.** `admin_signin`
  opened "I'll start as the admin. It's a new device…"; the full-stop pause landed
  right where `driver.mjs verify` probes for audio (a fixed 0.8s window 1.5s in), and
  the 5% stretch tipped that window under the −45 dB threshold. Joining the two clauses
  with an em dash removed the pause, so the check passes on its merits instead of being
  waved through.
- **The lightbox Download control has no `aria-label`.** Its accessible name comes from
  its text, so `button[aria-label="Download"]` matched nothing and the closing hover
  silently skipped — the one moment the premium scene exists to show. It targets the
  text now.
- Scenes 7–9 use the artist's Studio deliberately: the admin has no artist profile, so
  those identity fields render blank and the narration would be describing empty boxes.
- The lightbox `Download` beat **hovers, it does not click** — no real file is
  downloaded, so no bandwidth or disk cost on a re-run.
- Six of the twelve original clips were regenerated because their narration changed;
  the six untouched scenes kept their approved audio byte-identical.
