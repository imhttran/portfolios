// Drives the portfolios app and records a silent 1920x1080 .webm + marks.json.
// Scene ids MUST match scenes.json ids, in order. See SKILL.md.
function resolvePlaywright() {
  const cache = require("path").join(
    require("os").homedir(),
    ".cache/portfolios-demo/node_modules/playwright",
  );
  for (const c of ["playwright", process.env.DEMO_PW_PATH, cache].filter(
    Boolean,
  )) {
    try {
      return require(c);
    } catch {
      /* next */
    }
  }
  throw new Error("playwright not found — driver.mjs deps");
}
const { chromium } = resolvePlaywright();
const fs = require("fs");
const path = require("path");
const BASE = process.env.DEMO_BASE_URL || "http://localhost:3000";
const OUT = process.env.DEMO_ASSETS_DIR || __dirname;
fs.mkdirSync(OUT, { recursive: true });

// Clip lengths from `ffprobe` on demo/audio/<id>.wav — each scene holds at least this long.
const AUD = {
  hook: 15.33,
  public_browse: 12.35,
  admin_signin: 12.55,
  admin_users: 19.48,
  admin_adduser: 13.33,
  admin_grant_role: 10.26,
  studio_words: 13.79,
  studio_albums: 14.43,
  studio_newalbum: 13.0,
  admin_all_albums: 15.76,
  artist_page: 10.53,
  client_locked: 19.9,
  client_premium: 15.55,
  theme_close: 13.94,
};
// Breath after each line. 1.5s still reads as a deliberate pause and lets the eye
// finish the screen, where 2.0s made the whole take feel leisurely.
const PAD = 1.5,
  LEAD = 1.2;
const VP = { width: 1920, height: 1080 }; // full-screen rule: never changes mid-take

// Everything the take writes, it also cleans up (see clearLeftovers).
const PW = "Password1234!"; // every seeded login
const DEMO_USER = "jordan@mail.com"; // created on camera, then promoted to artist
const DEMO_PASS = "TempPass123!";
const DEMO_ALBUM = "Nightfall"; // created on camera, deliberately left hidden
const DEMO_SLUG = "nightfall";

const CURSOR = `
(() => {
  const mk = () => {
    if (document.getElementById('__democur')) return;
    const d = document.createElement('div');
    d.id = '__democur';
    d.style.cssText = 'position:fixed;z-index:2147483647;width:18px;height:18px;margin:-9px 0 0 -9px;border-radius:50%;background:rgba(0,0,0,.28);box-shadow:0 0 0 2px rgba(255,255,255,.9),0 1px 4px rgba(0,0,0,.35);pointer-events:none;transition:transform .08s ease-out;left:-100px;top:-100px';
    document.documentElement.appendChild(d);
    document.addEventListener('mousemove', e => { d.style.left=e.clientX+'px'; d.style.top=e.clientY+'px'; }, true);
    document.addEventListener('mousedown', () => d.style.transform='scale(.6)', true);
    document.addEventListener('mouseup',   () => d.style.transform='scale(1)',  true);
    const s = document.createElement('style');
    s.textContent = 'nextjs-portal{display:none!important}';
    document.documentElement.appendChild(s);
  };
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', mk); else mk();
  new MutationObserver(mk).observe(document.documentElement, { childList: true });
})();`;

(async () => {
  const b = await chromium.launch({ channel: "chrome" });

  // Pre-authenticate the non-admin personas off camera. Showing four full login
  // ceremonies would burn ~40s of a 4-minute demo on the least interesting part;
  // the admin sign-in (scene 3) is performed live so the 2FA step is on screen.
  //
  // This app keeps auth in localStorage (auth_token, device_id) and sets NO cookies,
  // so a clearCookies()/addCookies() swap is a silent no-op — the page stays signed
  // in as whoever logged in last. We capture and replay localStorage instead.
  async function authStorage(email) {
    const a = await b.newContext({ viewport: VP });
    const p = await a.newPage();
    await signIn(p, email);
    const state = await a.storageState();
    await a.close();
    const ls = (state.origins[0] || {}).localStorage || [];
    if (!ls.length) throw new Error(`no localStorage captured for ${email}`);
    console.log(
      `  pre-auth ok: ${email} (${ls.map((x) => x.name).join(", ")})`,
    );
    return ls;
  }

  // One login ceremony. Used off camera (pre-auth, cleanup) and on camera (scene 3).
  async function signIn(p, email) {
    for (let attempt = 1; attempt <= 3; attempt++) {
      // Clicking before React hydrates submits the form natively as a GET and
      // bounces back to /login?email=...&password=...
      await p.goto(BASE + "/login", { waitUntil: "networkidle" });
      await p.waitForTimeout(900);
      await p.fill("#email", email);
      await p.fill("#password", PW);
      await p.click('button:has-text("Sign in")');
      await p.waitForTimeout(2000);
      if (await p.locator("#code-0").count()) {
        for (let i = 0; i < 4; i++) await p.fill("#code-" + i, String(i + 1));
        await p.waitForTimeout(2500);
      }
      if (/dashboard|gallery/.test(p.url())) return;
      if (attempt === 3)
        throw new Error(`sign-in failed for ${email}, landed on ${p.url()}`);
      console.log(`  sign-in ${email} attempt ${attempt} bounced, retrying`);
    }
  }

  // Scenes 5, 6 and 9 write two real rows, so the flows are genuine rather than
  // mimed. Both are removed through the app's own API here, off camera, on the way
  // in AND on the way out — every run starts and ends on the seeded database, and
  // the album counts the narration describes stay true.
  async function clearLeftovers() {
    const a = await b.newContext({ viewport: VP });
    const p = await a.newPage();
    p.setDefaultTimeout(6000);
    await signIn(p, "admin@mail.com");
    const removed = await p.evaluate(
      async ([email, slug]) => {
        const headers = {
          Authorization: `Bearer ${localStorage.getItem("auth_token")}`,
        };
        const gone = [];
        const users = await (await fetch("/api/users", { headers })).json();
        for (const u of users.users || []) {
          if (u.email !== email) continue;
          const r = await fetch(`/api/users/${u.id}`, {
            method: "DELETE",
            headers,
          });
          if (r.ok) gone.push(`user ${u.email}`);
        }
        const albums = await (
          await fetch("/api/manage/albums", { headers })
        ).json();
        for (const al of albums.albums || []) {
          if (al.slug !== slug && !al.slug.startsWith(slug + "-")) continue;
          const r = await fetch(`/api/manage/albums/${al.slug}`, {
            method: "DELETE",
            headers,
          });
          if (r.ok) gone.push(`album /${al.slug}`);
        }
        return gone;
      },
      [DEMO_USER, DEMO_SLUG],
    );
    await a.close();
    console.log(
      removed.length
        ? `  cleanup: removed ${removed.join(", ")}`
        : "  cleanup: nothing to remove",
    );
  }

  await clearLeftovers(); // a run that died mid-take leaves rows behind
  const ARTIST = await authStorage("artist@mail.com");
  const CLIENT = await authStorage("client@mail.com");
  const PREMIUM = await authStorage("premium@mail.com");

  const ctx = await b.newContext({
    viewport: VP,
    recordVideo: { dir: path.join(OUT, "video-out"), size: VP },
  });
  await ctx.addInitScript(CURSOR);
  const p = await ctx.newPage();
  p.setDefaultTimeout(6000);
  p.on("dialog", (d) => d.accept());

  const T0 = Date.now();
  const marks = {};
  const el = () => (Date.now() - T0) / 1000;
  const sleep = (ms) => p.waitForTimeout(ms);
  const mark = (id) => {
    marks[id] = el();
    console.log(`[${el().toFixed(1)}s] ${id}`);
  };
  const hold = async (id) => {
    const wait =
      ((marks[id] ?? el()) + (AUD[id] ?? 0) + PAD) * 1000 - (Date.now() - T0);
    if (wait > 0) await sleep(wait);
  };
  // Swap the session. Must be called while already on the app's origin; the next
  // goto picks it up.
  //
  // Only the auth keys are carried across. localStorage also holds `theme`, and
  // that is presentation state: copying it from a captured persona would let a
  // saved dark preference flip the picture mid-take and make the closing theme
  // toggle a no-op depending on whose session ran last. The take owns the theme.
  const AUTH_KEYS = ["auth_token", "device_id"];
  const asPersona = async (ls) => {
    await p.evaluate(
      ([items, keys]) => {
        localStorage.clear();
        for (const { name, value } of items)
          if (keys.includes(name)) localStorage.setItem(name, value);
      },
      [ls, AUTH_KEYS],
    );
  };

  // NOTES.md's hard-won lesson: a silent auth no-op still renders a plausible
  // page, so never trust the navigation alone — assert. A failed take is cheap;
  // a take that quietly shows the wrong persona is not.
  const expect = (cond, msg) => {
    if (!cond) throw new Error(`ASSERT FAILED: ${msg}`);
    console.log(`  ok: ${msg}`);
  };
  const whoami = () =>
    p
      .evaluate(async () => {
        const t = localStorage.getItem("auth_token");
        const r = await fetch("/api/me", {
          headers: { Authorization: `Bearer ${t}` },
        });
        const j = await r.json();
        return j.user ? `${j.user.email} (${j.user.role})` : "anonymous";
      })
      .catch(() => "unknown");
  const expectPersona = async (email, label) => {
    const who = await whoami();
    expect(who.startsWith(email), `${label}: session is ${who}`);
  };

  async function move(x, y, steps = 22) {
    await p.mouse.move(x, y, { steps });
  }
  async function moveTo(sel, dx = 0, dy = 0) {
    try {
      const l = typeof sel === "string" ? p.locator(sel).first() : sel;
      await l.waitFor({ state: "visible", timeout: 4000 });
      await l.scrollIntoViewIfNeeded().catch(() => {});
      const bx = await l.boundingBox({ timeout: 3000 });
      if (!bx) {
        console.log("  [skip moveTo]");
        return null;
      }
      const x = bx.x + bx.width / 2 + dx,
        y = bx.y + bx.height / 2 + dy;
      await move(x, y);
      return { x, y };
    } catch {
      console.log("  [skip moveTo]");
      return null;
    }
  }
  async function click(sel, dx = 0, dy = 0) {
    const at = await moveTo(sel, dx, dy);
    await sleep(260);
    try {
      if (at) await p.mouse.click(at.x, at.y);
      else
        await (typeof sel === "string" ? p.locator(sel).first() : sel).click({
          timeout: 5000,
        });
    } catch {
      console.log("  [skip click]");
    }
  }
  async function type(sel, text, delay = 55) {
    await click(sel);
    try {
      await (typeof sel === "string" ? p.locator(sel).first() : sel).type(
        text,
        { delay, timeout: 4000 },
      );
    } catch {
      console.log("  [skip type] " + sel);
    }
  }
  async function choose(sel, value) {
    await moveTo(sel);
    await sleep(220);
    try {
      await (
        typeof sel === "string" ? p.locator(sel).first() : sel
      ).selectOption(value, { timeout: 4000 });
    } catch {
      console.log("  [skip select] " + value);
    }
  }
  async function glide(toY, ms = 2400) {
    await p.evaluate(
      ([toY, ms]) =>
        new Promise((res) => {
          const s = window.scrollY,
            d = toY - s,
            t0 = performance.now();
          const ease = (t) =>
            t < 0.5 ? 2 * t * t : 1 - Math.pow(-2 * t + 2, 2) / 2;
          (function step(now) {
            const k = Math.min(1, (now - t0) / ms);
            window.scrollTo(0, s + d * ease(k));
            k < 1 ? requestAnimationFrame(step) : res();
          })(t0);
        }),
      [toY, ms],
    );
  }

  // ---------------- 1. hook — homepage ----------------
  await p.goto(BASE + "/", { waitUntil: "networkidle" });
  await sleep(600);
  await sleep(Math.max(0, LEAD * 1000 - (Date.now() - T0)));
  mark("hook");
  await move(1150, 430);
  await sleep(900);
  await glide(520, 2600);
  await sleep(1400);
  await glide(980, 2600);
  await hold("hook");

  // ---------------- 2. public_browse — the work grid ----------------
  mark("public_browse");
  await glide(1700, 3000);
  await sleep(1200);
  await glide(2500, 3000);
  await sleep(900);
  await glide(3200, 2600);
  await hold("public_browse");

  // ---------------- 3. admin_signin — live login + 2FA ----------------
  mark("admin_signin");
  await p.goto(BASE + "/login", { waitUntil: "networkidle" });
  await sleep(700);
  await type("#email", "admin@mail.com");
  await sleep(180);
  await type("#password", "Password1234!");
  await sleep(320);
  await click('button:has-text("Sign in")');
  await p.waitForSelector("#code-0", { timeout: 15000 });
  await sleep(900);
  for (let i = 0; i < 4; i++) {
    await p.locator("#code-" + i).fill(String(i + 1));
    await sleep(200);
  }
  await p.waitForURL("**/dashboard", { timeout: 20000 });
  await expectPersona("admin@mail.com", "scene 3 landed as the admin");
  // Keep the live admin session so scene 10 can switch back to it.
  const ADMIN = await p.evaluate(() =>
    Object.keys(localStorage).map((name) => ({
      name,
      value: localStorage.getItem(name),
    })),
  );
  await hold("admin_signin");

  // ---------------- 4. admin_users — roles in the table ----------------
  // /api/users has to come back before the table has any rows, and the narration
  // opens by describing what is on screen — so the scene doesn't start until it is.
  // Marking first put this line over an empty shell for a beat on a cold dev server.
  await p.waitForSelector("table tbody tr", { timeout: 15000 }).catch(() => {});
  await sleep(350);
  mark("admin_users");
  await sleep(500);
  // The take starts on the seeded five; a leftover from an earlier run would
  // show up here rather than silently breaking the album counts later on.
  expect(
    (await p.locator("table tbody tr").count()) === 5,
    "scene 4 starts on the seeded five accounts",
  );
  await moveTo("table tbody tr:nth-child(2) select");
  await sleep(1100);
  await moveTo("table tbody tr:nth-child(3) select");
  await sleep(1100);
  await moveTo("table tbody tr:nth-child(5) select");
  await sleep(1100);
  await moveTo("table tbody tr:nth-child(1)");
  await sleep(700);
  await hold("admin_users");

  // ---------------- 5. admin_adduser — create the account ----------------
  mark("admin_adduser");
  // "Add User" is a <summary> inside <details>, not a modal.
  await click('summary:has-text("Add User")');
  await sleep(700);
  await type('details input[name="email"]', DEMO_USER);
  await sleep(200);
  await type('details input[name="password"]', DEMO_PASS);
  await sleep(500);
  // Submitted for real: the details collapses and the new row lands at the
  // bottom of the table. clearLeftovers() takes it back out off camera.
  await click('details button:has-text("Add User")');
  await sleep(1800);
  const newRow = p.locator(`table tbody tr:has-text("${DEMO_USER}")`);
  expect((await newRow.count()) === 1, `scene 5 created ${DEMO_USER}`);
  expect(
    (await newRow.locator("select").inputValue()) === "client",
    "a new account starts as a client",
  );
  await moveTo(newRow);
  await hold("admin_adduser");

  // ---------------- 6. admin_grant_role — hand over the artist role ----------------
  mark("admin_grant_role");
  await moveTo(`table tbody tr:has-text("${DEMO_USER}") select`);
  await sleep(800);
  await choose(`table tbody tr:has-text("${DEMO_USER}") select`, "artist");
  await sleep(1600);
  expect(
    (await p
      .locator(`table tbody tr:has-text("${DEMO_USER}") select`)
      .inputValue()) === "artist",
    "scene 6 promoted the account to artist",
  );
  await hold("admin_grant_role");

  // ---------------- 7. studio_words — the copy behind the site ----------------
  mark("studio_words");
  await asPersona(ARTIST); // admin has no artist profile -> these fields would be blank
  await p.goto(BASE + "/studio", { waitUntil: "networkidle" });
  await sleep(800);
  await expectPersona(
    "artist@mail.com",
    "scene 7 is the artist, not the admin",
  );
  await moveTo("#displayName");
  await sleep(700);
  await moveTo("#tagline");
  await sleep(600);
  await glide(520, 2200);
  await sleep(700);
  await moveTo("#statement");
  await sleep(700);
  await moveTo("#about");
  await sleep(900);
  await hold("studio_words");

  // ---------------- 8. studio_albums — tier buckets ----------------
  mark("studio_albums");
  await glide(1450, 2600);
  await sleep(700);
  await moveTo('select:below(:text("Albums"))');
  await sleep(900);
  await moveTo(p.locator("select").nth(3));
  await sleep(900);
  // "Add photos" is a <label> wrapping the hidden file input, not a <button>, so
  // `button:has-text("Add photos")` matches nothing and the hover silently skips.
  await moveTo("label.album-upload");
  await sleep(800);
  await glide(2300, 2400);
  await sleep(700);
  await hold("studio_albums");

  // ---------------- 9. studio_newalbum — start an album, hidden ----------------
  mark("studio_newalbum");
  // Continues in the artist session from scene 8, further down the same page.
  await glide(4000, 2600);
  await sleep(800);
  await type("#new-album-title", DEMO_ALBUM);
  await sleep(300);
  await choose("#new-album-access", "paid");
  await sleep(500);
  // Left unpublished on purpose: a hidden album stays off every public page, so
  // the seeded site still looks exactly as it did on the way in.
  await click('button:has-text("Create album")');
  await sleep(1800);
  expect(
    (await p.locator(`.album-row:has-text("${DEMO_ALBUM}")`).count()) === 1,
    `scene 9 created the ${DEMO_ALBUM} album`,
  );
  await moveTo(`.album-row:has-text("${DEMO_ALBUM}")`);
  await hold("studio_newalbum");

  // ---------------- 10. admin_all_albums — same editor, every artist ----------------
  mark("admin_all_albums");
  await asPersona(ADMIN);
  await p.goto(BASE + "/studio", { waitUntil: "networkidle" });
  await sleep(900);
  await expectPersona("admin@mail.com", "scene 10 switched back to the admin");
  // An admin's list widens to every artist (4 + 3 + the album scene 9 created),
  // where the artist's own list stops at five. This is the persona, asserted.
  const allAlbums = await p.locator(".album-row").count();
  expect(allAlbums >= 8, `scene 10 shows every album (${allAlbums})`);
  await glide(1500, 2600);
  await sleep(1200);
  await glide(2100, 2400);
  await sleep(1000);
  await moveTo('button:has-text("Hide")');
  await sleep(800);
  await hold("admin_all_albums");

  // ---------------- 11. artist_page — per-artist front door ----------------
  mark("artist_page");
  await p.goto(BASE + "/artist/ted-nguy", { waitUntil: "networkidle" });
  await sleep(800);
  expect(
    new URL(p.url()).pathname === "/artist/ted-nguy",
    "scene 11 landed on Ted's own page",
  );
  await glide(700, 2600);
  await sleep(900);
  await glide(1500, 2600);
  await hold("artist_page");

  // ---------------- 12. client_locked — paid tier hits a premium album ----------------
  mark("client_locked");
  await asPersona(CLIENT);
  await p.goto(BASE + "/album/studio-selects", { waitUntil: "networkidle" });
  await sleep(1000);
  await expectPersona("client@mail.com", "scene 12 is the paid client");
  const lockedCount = await p.locator("text=Locked").count();
  expect(lockedCount > 0, `scene 12 shows ${lockedCount} locked frames`);
  expect(
    (await p.locator('button:has-text("Download all")').count()) === 0,
    "scene 12 offers no download to the paid tier",
  );
  await moveTo("text=Premium subscription");
  await sleep(1400);
  await glide(700, 2600);
  await sleep(1400);
  await glide(1400, 2600);
  await sleep(1200);
  await glide(2100, 2400);
  await hold("client_locked");

  // ---------------- 13. client_premium — same album, unlocked ----------------
  mark("client_premium");
  await asPersona(PREMIUM);
  await p.goto(BASE + "/album/studio-selects", { waitUntil: "networkidle" });
  await sleep(1000);
  // The same album must now be open. Without this the take can quietly show the
  // paid client's locked view while the narration promises a download button.
  await expectPersona("premium@mail.com", "scene 13 is the premium client");
  const unlockedLocks = await p.locator("text=Locked").count();
  expect(
    unlockedLocks === 0,
    `scene 13 unlocks every frame (${unlockedLocks} locked)`,
  );
  expect(
    (await p.locator('button:has-text("Download all")').count()) === 1,
    "scene 13 offers the whole-set download",
  );
  await moveTo('button:has-text("Download all")');
  await sleep(1200);
  await click('figure button[aria-label*="larger"]');
  await p.waitForSelector("[role=dialog]", { timeout: 10000 });
  expect(
    (await p.locator("[role=dialog]").count()) === 1,
    "scene 13 opened the lightbox",
  );
  await sleep(1500);
  await click('[role=dialog] button[aria-label="Next frame"]');
  await sleep(1500);
  // Text, not aria-label: this control's accessible name comes from its text, so
  // `button[aria-label="Download"]` matches nothing and the hover silently skips.
  await moveTo('[role=dialog] button:has-text("Download")');
  await sleep(900);
  await hold("client_premium");

  // ---------------- 14. theme_close — light/dark + closing stroll ----------------
  mark("theme_close");
  await p.keyboard.press("Escape");
  await sleep(400);
  await p.goto(BASE + "/", { waitUntil: "networkidle" });
  await sleep(500);
  expect(
    new URL(p.url()).pathname === "/",
    `scene 14 came back to the front page (${new URL(p.url()).pathname})`,
  );
  await glide(3400, 2600);
  await sleep(1300);
  await glide(0, 1600);
  await sleep(400);
  const themeBefore = await p.evaluate(
    () => document.documentElement.dataset.theme,
  );
  await click('button[aria-label="Switch between light and dark theme"]');
  await sleep(1600);
  expect(
    (await p.evaluate(() => document.documentElement.dataset.theme)) !==
      themeBefore,
    `scene 14 flipped the theme (${themeBefore} -> dark or light)`,
  );
  await glide(1500, 2800);
  await sleep(900);
  await glide(2400, 2200);
  await hold("theme_close");
  await sleep(900);

  // Full-screen rule: viewport must still be exactly 1920x1080 at 100% zoom.
  const vp = p.viewportSize();
  const zoom = await p.evaluate(
    () => Math.round(window.devicePixelRatio * 100) / 100,
  );
  if (!vp || vp.width !== VP.width || vp.height !== VP.height)
    throw new Error(
      `viewport drifted to ${vp && vp.width}x${vp && vp.height}; must stay 1920x1080`,
    );
  if (zoom !== 1) throw new Error(`browser zoom is ${zoom}, must be 1 (100%)`);
  console.log(`  viewport ok: ${vp.width}x${vp.height} @ zoom ${zoom}`);

  const total = el();
  await ctx.close();
  await clearLeftovers(); // undo the two rows scenes 5-6 and 9 wrote
  await b.close();
  const webm = fs
    .readdirSync(path.join(OUT, "video-out"))
    .filter((f) => f.endsWith(".webm"))
    .pop();
  const meta = { marks, total, video: path.join(OUT, "video-out", webm) };
  fs.writeFileSync(path.join(OUT, "marks.json"), JSON.stringify(meta, null, 2));
  console.log(JSON.stringify(meta, null, 2));
  console.log("RECORD OK");
})().catch((err) => {
  console.error("FAILED:", err.message.split("\n")[0]);
  process.exit(1);
});
