# portfolios — demo recording notes

Project-specific facts for the `demo-video` skill. The skill itself is global
(`~/.claude/skills/demo-video/`); this file holds only what is true of _this_ app.

Run everything through the shared driver:

```bash
node ~/.claude/skills/demo-video/scripts/driver.mjs doctor
node ~/.claude/skills/demo-video/scripts/driver.mjs all
python3 demo/make-workflow.py   # after a re-record: workflow.json from the new marks
```

`driver.mjs narrate` regenerates clips at narrate.sh's stock rate and `mix.py` writes
its own encode, so a full `all` run does **not** reproduce the shipped file — see
**Pace** and **Output compression** for the two extra steps.

Config lives in `demo/demo.config.json` (URLs, services, target length, voice).

## Output compression

`mix.py` writes its own encode, so the shipped `demo.mp4` is smaller than what a bare
`driver.mjs mix` produces. `demo/demo-master.mp4` is the uncompressed master — re-encode
from that, never from `demo.mp4`, or the artifacts compound.

```bash
ffmpeg -v error -y -i demo/demo-master.mp4 -c:v libx264 -crf 26 -preset slow \
  -pix_fmt yuv420p -movflags +faststart \
  -c:a aac -b:a 112k -ar 44100 -ac 1 demo/demo.mp4
```

45.3 MB → 22.0 MB (−51%), SSIM 0.9975 against the master over a text- and
photo-heavy minute. Measured, not assumed — and this is a UI demo, so the thing to
check is that small mono text stays crisp, not the SSIM alone. `crf 29` also held up
(15.6 MB, SSIM 0.9963) if a smaller file is ever wanted.

- **`-ar 44100 -ac 1` matters more than the bitrate.** `mix.py` passes the TTS wav's
  own rate through, so the source was 96 kHz mono AAC at ~170 kbit/s — wasteful, and
  96 kHz is a _worse_ encode target for speech than 44.1 kHz. This alone is a real
  saving at no cost.
- **112 kbit/s is deliberately above what the test suggests.** 64–80k looked fine on
  paper, but audio is the one stream that can't be checked by machine, so the setting
  errs toward the safe side for a ~0.9 MB cost.

## Pace

Two levers, both set in this repo:

- `PAD` in `record.cjs` (currently `1.5`) — silence held after each line. This is the
  main one. It only ever adds trailing quiet, so lowering it cannot clip narration.
- A pitch-preserving 5% stretch of the narration clips. `driver.mjs narrate` does not
  do this, so a regenerated clip comes back at stock rate and must be stretched before
  mixing:

```bash
python3 -c "
import glob, os, shutil, subprocess
for p in sorted(glob.glob('demo/audio/*.wav')):
    if os.path.basename(p) == 'public_browse.wav':
        continue            # held at stock rate, deliberately
    subprocess.run(['ffmpeg','-v','error','-y','-i',p,'-filter:a','atempo=1.05',p+'.t'],check=True)
    shutil.move(p+'.t', p)
"
```

Then paste the new `ffprobe` durations into `AUD` in `record.cjs` and re-record — `AUD`
is what each scene holds for.

`public_browse` is excluded on purpose: it is already the fastest line at 170 wpm, and
5% more would cross the skill's 175 wpm guardrail. Excluding it keeps the spread at
131–170 instead of pushing the top past the limit.

**Do not try to get pace out of the TTS instructions.** Asking for a "slightly brisker"
delivery across all 14 clips moved the mean by ~1%, made four clips slower, and pushed
one to 174 wpm — run-to-run noise. The rate lever is `atempo`; the timing lever is `PAD`.

## Logins

All use `Password1234!`; the dev 2FA code is always `1234`.

| Login              | Role   | Notes                                        |
| ------------------ | ------ | -------------------------------------------- |
| `admin@mail.com`   | admin  | can download anything — masks tier bugs      |
| `artist@mail.com`  | artist | owns Ethan's 4 albums                        |
| `ted@mail.com`     | artist | owns Wetlands / Field Notes / Studio Selects |
| `client@mail.com`  | client | **paid** tier — premium albums stay Locked   |
| `premium@mail.com` | client | **premium** tier — everything unlocked       |

Ethan's albums are grey placeholder gradients; Ted's hold real photographs, which
is why the client/premium scenes use Ted's _Studio Selects_.

`jordan@mail.com` is not seeded. Scene 5 creates it and scene 6 promotes it to
`artist`; `clearLeftovers()` deletes it again off camera. Likewise the `Nightfall`
album scene 9 creates. If a run dies mid-take, the next run's pre-flight cleanup
removes both — you should never see them in the database between takes.

## Writing to the database on camera

Scenes 5, 6 and 9 write real rows, so the forms aren't mimed. The rules that keep
that safe:

- **Clean up on both sides, off camera, through the app's own API.** `clearLeftovers()`
  logs in as admin in a throwaway context and deletes by email / slug prefix via
  `fetch('/api/users')` and `fetch('/api/manage/albums')`. Called before the take and
  after the video context closes, so a crashed run self-heals on the next one.
- **Leave the album unpublished.** `is_published = false` keeps it out of every public
  listing (`media.py` filters on it), so adding a row can't disturb the front page,
  the gallery, or the album counts scenes 2 and 14 show.
- **Delete by slug _prefix_.** `unique_album_slug` appends `-2`, `-3` … if the slug is
  taken, so a leftover from a crashed run may not be at the bare slug.
- **A promoted user does not join the roster.** `/api/artists` reads `ArtistProfile`
  rows, and a profile only appears when someone saves one in `/studio`. A fresh
  `artist` with no profile is invisible to the public site — which is why promoting one
  on camera is safe.

## Gotchas

Everything here was hit for real in this repo.

- **Auth may live in `localStorage`, not cookies.** This app stores `auth_token` and
  `device_id` in localStorage and sets **zero** cookies, so switching personas with
  `clearCookies()` / `addCookies()` is a _silent_ no-op — no error, the page just
  stays signed in as whoever logged in last. Capture
  `storageState().origins[0].localStorage` and replay it with `page.evaluate()` while
  already on the app's origin, then navigate. Check `storageState()` before assuming
  cookies carry the session.
- **A persona swap must carry the auth keys _only_.** `localStorage` also holds `theme`,
  which is presentation state. Replaying a captured session wholesale replays its saved
  dark preference too, so the picture can flip mid-take and the closing theme toggle
  becomes a no-op (you toggle dark → light and the video ends dark). `asPersona()`
  filters to `auth_token` + `device_id`; the take owns the theme.
- **Assert every persona swap and every write.** A silent auth no-op renders a
  _plausible_ page, so a wrong take looks fine in a contact sheet. `expectPersona()`
  asks `/api/me` who the session actually is, and the write scenes assert the new row
  exists (and starts as `client` before the promotion). A failed assertion aborts the
  take instead of shipping something wrong.
- **The lightbox's Download control has no `aria-label`.** Its accessible name comes
  from its text, so `[role=dialog] button[aria-label="Download"]` matches nothing —
  `moveTo()` logs `[skip moveTo]` and the hover silently never happens, at exactly the
  moment the premium scene exists to show. Use `:has-text("Download")`. The lightbox's
  arrow buttons _do_ have labels (`Previous frame` / `Next frame`).
- **A silent auth no-op can look like success.** Because an admin here can download
  anything, a broken persona swap still rendered a plausible page — the "paid client
  is locked out" scene showed download buttons and the narration contradicted the
  screen. Assert the persona took effect (an element only that persona sees) rather
  than trusting the navigation.
- **Form fields may have `name` but no `id`.** The Add User inputs are
  `input[name="email"]` / `input[name="password"]` with no id at all, so `#email`
  matched nothing. With default timeouts that cost ~31s of dead air mid-take. Probe
  real attributes, and keep `type()`/`moveTo()` timeouts short so a bad selector
  fails in seconds instead of silently padding the video.
- **The recorder must be `.cjs`, not `.js`.** Root `package.json` has
  `"type": "module"`, so a CommonJS `record.js` dies with
  `ReferenceError: require is not defined in ES module scope`. It works in `/tmp`
  (no parent package.json) and breaks the moment it moves into the repo.
- **Clicking "Sign in" before React hydrates submits the form natively as a GET** and
  bounces to `/login?email=…&password=…` with the password in the URL. Wait for
  `networkidle` plus ~900ms before filling. The pre-auth retries 3× for this reason.
- **`./manage.sh 1` does not work.** It's an interactive menu — it prints
  `Unknown option` and re-renders forever. The driver starts services directly:
  `env PORT=8080 .venv/bin/python -m app.main` and `npm run dev`.
- **`/api/health` returns 404** on this build despite what the docs claim. Use
  `/api/artists` (200) as the health signal.
- **Playwright's cached browser is the wrong revision.** `playwright@1.63.0` wants
  `chromium_headless_shell-1243`; the cache has `chromium-1234`, so `launch()` fails
  with `Executable doesn't exist`. Fixed by `channel: 'chrome'` — no ~150MB download.
- **`npx playwright` won't self-install non-interactively**
  (`npx canceled due to missing packages and no YES option`). `deps` runs an explicit
  `npm install` into `~/.cache/portfolios-demo` instead of touching the repo.
- **2FA is four separate inputs** `#code-0`…`#code-3`. `fill('1234')` on the first box
  only fills that box. The dev code is always `1234`.
- **Album tier `<select>`s have no `aria-label`** — the accessible name comes from a
  `<label>`, so `select[aria-label^="Bucket for"]` matches nothing. The recorder uses
  `select` `.nth(2)` (0 = gridColumns, 1 = theme, 2 = first album bucket).
- **`/album/wetlands` is below the fold** in the gallery grid; it needs
  `scrollIntoViewIfNeeded()` before the click. Use Wetlands specifically — Ethan's
  four albums are grey placeholder gradients, Ted's have real photographs.
- **The Next.js dev overlay is in frame** unless hidden; the recorder injects
  `nextjs-portal{display:none!important}`.
- **Do not screen-record this app.** `ffmpeg -f avfoundation` hangs with zero output
  when macOS Screen Recording permission is missing, and when granted it captures the
  whole physical display — other windows and personal tabs included. Playwright's
  `recordVideo` captures only the page and needs no permission.
- **Never use AppleScript to find the automation window.**
  `tell application "Google Chrome"` routes to the user's _real_ Chrome; `set bounds`
  moved and raised a personal window with no way to restore its geometry. Headless
  recording means you never need to touch OS windows.
- **`timeout` is not installed** on macOS. Use the Bash tool's own timeout parameter.
- The recorder uses a **fresh browser context every run**, so admin always gets the
  2FA prompt (it waits for `#code-0`). Reusing a persisted profile would skip the
  prompt and hang that wait.
- **Do not blanket-run `brew install node python3 ffmpeg jq postgresql@16`.** On an
  already-provisioned machine it _upgrades_ rather than no-ops. Doing exactly that
  here took node 26.7.0 -> 26.8.2 and simdutf 9.1.0 -> 9.2.0; simdutf 9.2.0 ships
  `libsimdutf.36` while `merve` (which node loads) still linked `.35`, so every
  `node` invocation died with
  `dyld: Library not loaded: …libsimdutf.35.dylib … Referenced from: …libmerve…`.
  Fix: `brew reinstall merve`. Install individual missing tools instead.
- **`driver.mjs verify` probes a fixed window, so a natural pause can read as silence.**
  It samples 0.8s starting 1.5s into each scene and wants mean volume above −45 dB. A
  line whose delivery pauses right there fails even though the clip is healthy — check
  the clip with `ffmpeg -i <clip> -af volumedetect -f null -` before believing the FAIL
  (and note `-v error` hides volumedetect's output; it logs at INFO). The real fix is to
  remove the pause, not to wave the gate through: joining two clauses with an em dash in
  `scenes.json` moved that line from −47 dB to −29 dB. This bit `admin_signin` when the
  5% pace stretch was applied.
- **A `[skip moveTo]` line means a selector matched nothing, not that a hover was
  flaky.** Helpers log and continue rather than aborting a 4-minute take, so the
  failure is invisible unless you read the log. Two were found this way: `Add photos`
  is a `<label>` wrapping the hidden file input (use `label.album-upload`), and the
  lightbox's Download button has no `aria-label` (use `:has-text("Download")`). A
  clean take should now print **no** skips — treat any as a bug, not as noise.

## Troubleshooting

| Symptom                                                                         | Fix                                                                                                              |
| ------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------- |
| `ReferenceError: require is not defined in ES module scope`                     | The recorder got renamed to `.js`. It must stay `record.cjs`.                                                    |
| `premium pre-auth failed, landed on …/login?email=…`                            | Pre-hydration submit. Frontend was still compiling — re-run; `up` waits for a 200 but the first compile is lazy. |
| `browserType.launch: Executable doesn't exist at …chromium_headless_shell-1243` | Missing `channel: 'chrome'`, or Chrome isn't installed.                                                          |
| `playwright not found`                                                          | `driver.mjs deps`. The driver sets `NODE_PATH` to the cache dir for the recorder.                                |
| `app is not up -> driver.mjs up`                                                | Frontend/backend not listening. Check `/tmp/portfolios-backend.log` and `-frontend.log`.                         |
| `postgres is down`                                                              | `brew services start postgresql@16`.                                                                             |
| `RUNS PAST END OF VIDEO` from mix                                               | A scene's narration is longer than its screen time. Update `AUD` in `record.cjs` and re-record.                  |
| Backend starts then exits                                                       | Almost always Postgres. `pg_isready` should say `accepting connections`.                                         |
