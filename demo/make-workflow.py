import json, pathlib

demo = pathlib.Path("demo")
scenes = json.loads((demo / "scenes.json").read_text())
marks = json.loads((demo / "marks.json").read_text())

ACTIONS = {
    "hook": ["Open /", "Ease down through the hero and the statement"],
    "public_browse": ["Scroll the roster and the full work grid"],
    "admin_signin": [
        "Go to /login",
        "Type admin@mail.com / Password1234!",
        "Submit",
        "Fill 2FA 1234 into #code-0..3",
        "Land on /dashboard",
        "Assert the session really is admin@mail.com",
    ],
    "admin_users": [
        "Assert the table holds the seeded five accounts",
        "Hover the inline role dropdowns in the users table",
    ],
    "admin_adduser": [
        "Expand the Add User <details>",
        "Fill email + temporary password",
        "Submit for real",
        "Assert jordan@mail.com appears in the table, as a client",
    ],
    "admin_grant_role": [
        "Change the new account's role dropdown to artist",
        "Assert the row now reads artist",
    ],
    "studio_words": [
        "Switch to the artist session (asserted)",
        "Open /studio",
        "Scroll the identity + copy fields (statement, bio, About)",
    ],
    "studio_albums": [
        "Scroll to the album list",
        "Hover a tier bucket",
        "Show Hide / Add photos / New album",
    ],
    "studio_newalbum": [
        "Scroll to the New album form",
        "Type a title",
        "Set the bucket to paid",
        "Leave 'Publish it now' unticked",
        "Create album",
        "Assert the row appears: hidden, 0 photos, /nightfall",
    ],
    "admin_all_albums": [
        "Switch back to the live admin session (asserted)",
        "Open /studio",
        "Assert every album is listed (8, not the artist's 5)",
        "Scroll the album editor across both artists",
    ],
    "artist_page": ["Open /artist/ted-nguy (asserted)", "Scroll the per-artist page"],
    "client_locked": [
        "Switch to the paid-tier client (asserted)",
        "Open /album/studio-selects",
        "Assert 24 frames read Locked and no download control exists",
        "Scroll the locked grid",
    ],
    "client_premium": [
        "Switch to the premium client (asserted)",
        "Same album, same request",
        "Assert every frame unlocked and Download all present",
        "Open the lightbox",
        "Next frame",
        "Hover Download",
    ],
    "theme_close": [
        "Close the lightbox",
        "Return to / (asserted)",
        "Scroll to About",
        "Back to top",
        "Toggle the theme (asserted)",
        "Stroll the grid in the new theme",
    ],
}

workflow = {
    "application": "http://localhost:3000",
    "goal": (
        "Show how one photo-portfolio site serves three audiences: the studio admin who "
        "sets the rules, the artists who own their own pages, and the paying clients whose "
        "tier decides what they can download. The admin and artist scenes now write real "
        "rows rather than miming the forms."
    ),
    "duration_seconds": round(marks["total"], 2),
    "resolution": "1920x1080",
    "capture": {
        "method": "playwright headless chrome recordVideo (channel: chrome)",
        "note": (
            "Records the page via CDP, not the screen — desktop windows and personal tabs "
            "cannot appear. Viewport is asserted 1920x1080 @ 100% zoom at the end of the "
            "take. Every persona swap and every write is asserted, because a silent auth "
            "no-op still renders a plausible page (see demo/NOTES.md)."
        ),
        "fps": 25,
        "cursor": "synthetic dot injected via addInitScript",
    },
    "voice": {
        "provider": "openai",
        "model": "gpt-4o-mini-tts",
        "voice": "ash",
        "format": "wav",
        "generated_per_scene": True,
        "instructions": "see narrate.sh / SKILL.md voice-design prompt",
    },
    "personas": {
        "admin": "admin@mail.com — signed in live on camera, 2FA 1234",
        "artist": "artist@mail.com — pre-authenticated off camera",
        "paid_client": "client@mail.com — paid tier, premium albums stay locked",
        "premium_client": "premium@mail.com — premium tier, everything unlocked",
        "switching": (
            "localStorage (auth_token, device_id) is captured and replayed. Only those two "
            "auth keys are carried across; `theme` is presentation state and is left to the "
            "take, so a captured dark preference can't flip the picture or no-op the close."
        ),
        "asserted": "each swap is followed by a whoami() call against /api/me",
    },
    "database_writes": {
        "note": (
            "Two scenes write real rows. Both are removed through the app's own API off "
            "camera — before the take and again after it — so every run starts and ends on "
            "the seeded database and the album counts the narration implies stay true."
        ),
        "user": "jordan@mail.com, created as client then promoted to artist",
        "album": "Nightfall, paid bucket, deliberately left unpublished (hidden albums are "
                 "filtered out of every public page, so the public site is untouched)",
    },
    "scenes": [
        {
            "id": s["id"],
            "starts_at": marks["marks"][s["id"]],
            "narration": s["text"],
            "actions": ACTIONS[s["id"]],
        }
        for s in scenes
    ],
    "artifacts": {
        "final": "demo.mp4",
        "narration": "narration.txt",
        "scenes": "scenes.json",
        "marks": "marks.json",
        "audio_dir": "audio/",
        "raw_capture": "raw.webm",
        "recorder": "record.cjs",
        "config": "demo.config.json",
        "notes": "NOTES.md",
    },
    "reproduce": {
        "run_from": "anywhere inside the repo",
        "steps": ["node ~/.claude/skills/demo-video/scripts/driver.mjs all"],
    },
}

(demo / "workflow.json").write_text(json.dumps(workflow, indent=2, ensure_ascii=False) + "\n")
print("wrote demo/workflow.json:", len(workflow["scenes"]), "scenes,", workflow["duration_seconds"], "s")
