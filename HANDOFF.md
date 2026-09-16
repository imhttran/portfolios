# Handoff — demo video + demo tooling consolidation: DONE

## Goal

Two things, both finished:

1. Produce a narrated demo video of the portfolios app.
2. Stop having two overlapping demo skills. One skill that works for **this**
   project and any future one, with nothing app-specific baked into it.

## Status: shipped

`demo/demo.mp4` — **224.4s (3.7 min), 22 MB**, 1920x1080, H.264/AAC, 14 scenes. Inside
the skill's 3–5 minute target. Narration is OpenAI TTS (`gpt-4o-mini-tts`, voice
`ash`), generated per scene. **Tom has listened to it and approved the voice** — that
is settled, don't re-litigate it or re-sample voices.

### Architecture (the important part)

There is now exactly **one** skill. Everything app-specific is project data:

```
~/.claude/skills/demo-video/          <- the only skill, global, app-agnostic
  SKILL.md                            craft: story, narration style, voice, gates, modes
  scripts/driver.mjs                  generic orchestration
  scripts/narrate.sh  mix.py  concat-videos.sh  record-template.js  scenes.example.json

<repo>/demo/                          <- per-project (tracked)
  demo.config.json                    URLs, services, target length, voice, prereqs
  record.cjs                          the app-specific recorder
  scenes.json                         narration text (contract with the recorder)
  NOTES.md                            this app's logins + gotchas
  make-workflow.py                    regenerates workflow.json from the new marks
  (generated, gitignored: demo.mp4, raw.webm, marks.json, audio/,
   narration.txt, workflow.json, demo-plan.md)
```

Run from anywhere inside the repo — the driver walks up to find `demo/demo.config.json`:

```bash
node ~/.claude/skills/demo-video/scripts/driver.mjs doctor
node ~/.claude/skills/demo-video/scripts/driver.mjs all     # ~5 min
```

Commands: `doctor deps up down record narrate mix verify all`. `narrate` skips clips
that already exist (`FORCE=1` regenerates, costs OpenAI calls). `verify` writes
`/tmp/demo-verify-frame.png` — open it; a green PASS list does not prove the picture
is right.

**A previous `run-demo-video` project skill was deleted.** Its project-specific half
lives in `demo/NOTES.md`; its generic half became `scripts/driver.mjs`. Don't
recreate it — that duplication is what we just removed.

## What worked

- **Playwright `recordVideo` (CDP screencast), headless, `channel: 'chrome'`.** No
  macOS Screen Recording permission, captures only the page (desktop windows and
  personal tabs cannot leak in), real motion rather than a slideshow. `channel:
'chrome'` also dodges a cached-browser revision mismatch without a ~150MB download.
- **Marks-based sync.** The recorder emits a wall-clock timestamp per scene into
  `marks.json`; `mix.py --marks` places each clip exactly there. Un-narrated
  transitions (logins, navigation) are then free and the voice never drifts.
- **Persona switching via `localStorage`** — see the trap below.
- **Config-driven driver.** `demo.config.json` holds base URL, health URL, service
  start commands, target length, voice. Nothing about portfolios is in the skill.
- **Generating TTS _before_ finalising the recorder**, then pasting the real clip
  durations into `AUD` at the top of `record.cjs` so each scene holds long enough.
- Injected cursor dot + hiding `nextjs-portal` so clicks read and dev chrome is out
  of frame.

## What didn't work (do not repeat)

- **Cookie-based persona switching is a silent no-op here.** This app sets **zero
  cookies**; auth is entirely `localStorage` (`auth_token`, `device_id`). The old
  `clearCookies()`/`addCookies()` swap changed nothing, so the whole take stayed
  signed in as admin — and because admin can download anything, the "paid client is
  locked out" scene showed Download buttons while the narration said "Locked". Fix:
  capture `storageState().origins[0].localStorage` and replay with
  `page.evaluate()` on the app origin. **Always assert the persona took effect** with
  an element only that persona sees.
- **AppleScript to find the automation window.** `tell application "Google Chrome"`
  routes to the _user's real Chrome_; `set bounds`/`set index` moved and raised a
  personal window with no way to restore its geometry. Headless recording removes any
  reason to touch OS windows. Never do this.
- **`ffmpeg -f avfoundation` screen capture.** Hangs with zero output when Screen
  Recording permission is missing; when granted it captures the whole physical
  display. Strictly worse than page capture.
- **Blanket `brew install node python3 ffmpeg jq postgresql@16`.** It _upgrades_ on a
  provisioned machine: node 26.7.0→26.8.2 and simdutf 9.1.0→9.2.0, after which
  `merve` still linked `libsimdutf.35` and **every `node` call died**. Fix was
  `brew reinstall merve`. Install only what's actually missing.
- **`record.js` in this repo** — root `package.json` has `"type": "module"`, so a
  CommonJS recorder dies with `ReferenceError: require is not defined`. Must be `.cjs`.
- **Assuming `#email` exists on the Add User form.** Those inputs have `name` but no
  `id`; with default timeouts the miss cost ~31s of dead air mid-video. Probe real
  attributes and keep helper timeouts short so bad selectors fail fast.
- **Admin's `/studio` for the "words on the page" scene** — admin has no artist
  profile, so the identity fields render blank while the narration describes them.
  Those scenes use the artist session deliberately.
- **Stale duration gates.** After the profile moved to 3–5 min, `driver.mjs` still
  asserted `<= 90s` and would have failed its own check. Gates now read
  `targetSeconds`/`maxSeconds` from the project config.

## Next steps

Nothing is blocking. Open items are only things to decide, not bugs:

- **The take now writes real rows.** Scenes 5–6 create and promote `jordan@mail.com`;
  scene 9 creates a hidden `Nightfall` album. `clearLeftovers()` removes both off camera
  before and after the take, and it also runs before the take so a crashed run
  self-heals. Every persona swap and every write is asserted — if you change those
  scenes, keep the assertions, because a silent auth no-op in this app still renders a
  plausible page. See `demo/NOTES.md` → "Writing to the database on camera".
- **The take's pace is set in two places, and neither is the TTS instructions.** `PAD`
  in `record.cjs` (trailing quiet after each line) plus a 5% pitch-preserving `atempo`
  stretch on the clips. `driver.mjs narrate` does not apply the stretch, so a full `all`
  run reproduces the video but not the shipped audio. See `demo/NOTES.md` → "Pace".
- **A `[skip moveTo]` in the record log is a bug, not noise.** It means a selector
  matched nothing. Two were fixed this way (the `Add photos` label, the lightbox
  Download button with no `aria-label`); a clean take prints none.

- **`CLAUDE.md` is deleted in the working tree** (`git status` shows ` D CLAUDE.md`).
  Still in git — `git checkout -- CLAUDE.md` restores it. Left alone in case the
  deletion was deliberate.
- **Nothing here is committed.** `demo/` sources, `.gitignore`, and this file are all
  uncommitted; `.gitignore` was changed to track the four demo sources while ignoring
  generated media.
- Ethan's four albums are grey placeholder gradients (Ted's are real photographs,
  which is why the client/premium scenes use Ted's _Studio Selects_). Importing real
  images via `app/cli.py import-album` and re-running `driver.mjs all` would improve
  scenes 1, 2 and 12.
- To use the skill on **another project**: follow "Per-project setup" in
  `~/.claude/skills/demo-video/SKILL.md` — copy `scripts/record-template.js` to
  `<repo>/demo/record.cjs`, write `demo.config.json` + `scenes.json`, done. No new
  skill required.

## Reference

- Project gotchas and dev logins: `demo/NOTES.md`
- Story, scene table, honest caveats: `demo/demo-plan.md`
- Craft + pipeline + per-project setup: `~/.claude/skills/demo-video/SKILL.md`
- App commands: `./manage.sh` (interactive menu; `./manage.sh 1` does **not** work)
