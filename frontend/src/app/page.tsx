"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { API_BASE, LOGIN_PATH } from "@/lib/api";
import { creditFor } from "@/lib/credits";
import { useSiteCopy } from "@/lib/useSiteCopy";
import { fitGrid, useFittedGrids } from "@/lib/useFittedGrids";
import { BackToTop } from "@/components/BackToTop";
import { PhotoViewer } from "@/components/PhotoViewer";
import { PageTitle } from "@/components/PageTitle";
import { SignOut } from "@/components/SignOut";
import { ThemeToggle } from "@/components/ThemeToggle";

type Album = {
  id: number;
  slug: string;
  title: string;
  credit: string | null;
  description: string | null;
  access: string;
  artistName: string | null;
  artistSlug: string | null;
};

type RosterArtist = {
  slug: string;
  displayName: string;
  tagline: string;
  location: string;
};

type Photo = {
  id: number;
  title: string | null;
  previewUrl: string;
  width: number | null;
  height: number | null;
};

type Loaded = { album: Album; photos: Photo[] };

export default function PortfolioPage() {
  const [albums, setAlbums] = useState<Loaded[] | null>(null);
  const [failed, setFailed] = useState(false);
  // Bumped by the retry button to re-run the load.
  const [attempt, setAttempt] = useState(0);
  const [heroLoaded, setHeroLoaded] = useState(false);
  const [viewing, setViewing] = useState<number | null>(null);
  const [roster, setRoster] = useState<RosterArtist[]>([]);
  const copy = useSiteCopy();

  useEffect(() => {
    let cancelled = false;
    setFailed(false);

    (async () => {
      try {
        const response = await fetch(`${API_BASE}/api/media/albums`);
        const data = await response.json();
        if (!response.ok) throw new Error(data.message);

        const loaded = await Promise.all(
          (data.albums as Album[]).map(async (album) => {
            const detail = await fetch(
              `${API_BASE}/api/media/albums/${album.slug}`,
            );
            const body = await detail.json();
            if (!detail.ok) throw new Error(body.message);
            return {
              album: body.album as Album,
              photos: body.photos as Photo[],
            };
          }),
        );
        if (!cancelled) setAlbums(loaded);
      } catch {
        if (!cancelled) setFailed(true);
      }
    })();

    return () => {
      cancelled = true;
    };
  }, [attempt]);

  // One flat list for the viewer, and each frame keeps its position in it, so
  // the sequence continues across albums instead of restarting per section.
  const sections = useMemo(() => {
    // Every artist's published work, not just the primary artist's. Hiding the
    // rest behind a link made a second artist invisible on the site's own front
    // page - naming them on each sheet is both more honest and more useful.
    let offset = 0;
    return (albums ?? []).map(({ album, photos }) => {
      const start = offset;
      offset += photos.length;
      return {
        album,
        frames: photos.map((photo, i) => ({
          ...photo,
          credit: album.credit,
          index: start + i,
        })),
      };
    });
  }, [albums]);

  // Size every album to the frame it is shown in.
  useFittedGrids(albums);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const response = await fetch(`${API_BASE}/api/artists`);
        if (!response.ok) return;
        const data = await response.json();
        if (!cancelled) setRoster(data.artists as RosterArtist[]);
      } catch {
        // The roster is a convenience; the page works without it.
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  const frames = useMemo(() => sections.flatMap((s) => s.frames), [sections]);
  const heroUrl = frames[0] ? `${API_BASE}${frames[0].previewUrl}` : null;

  // Fade the hero image in only once it's decoded, so the page never shows a
  // half-painted frame over the statement. A cached image fires no onload.
  useEffect(() => {
    if (!heroUrl) return;
    const image = new Image();
    image.src = heroUrl;
    if (image.complete) {
      setHeroLoaded(true);
      return;
    }
    image.onload = () => setHeroLoaded(true);
  }, [heroUrl]);

  const closeViewer = useCallback(() => setViewing(null), []);
  const changeViewer = useCallback((next: number) => setViewing(next), []);

  return (
    <div className="site">
      <PageTitle title={`${copy.name} — ${copy.role}`} />
      <header className="site-bar site-bar--over">
        <a className="site-identity" href="/">
          <span className="site-name">{copy.name}</span>
          <span className="site-role">{copy.role}</span>
        </a>
        <nav className="site-nav">
          <a href="#work">Work</a>
          <a href="#about">About</a>
          {roster.length > 1 ? <a href="#artists">Artists</a> : null}
          <a href="/gallery">Client access</a>
          <ThemeToggle />
          <SignOut />
        </nav>
      </header>

      <section className="hero">
        {heroUrl ? (
          <>
            <div
              className={`hero-media${heroLoaded ? " is-loaded" : ""}`}
              style={{ backgroundImage: `url(${heroUrl})` }}
              aria-hidden="true"
            />
            <div className="hero-scrim" aria-hidden="true" />
          </>
        ) : null}

        <h1 className="hero-statement">{copy.statement}</h1>

        <dl className="hero-meta">
          <div>
            <dt>Based in</dt>
            <dd>{copy.location}</dd>
          </div>
          <div>
            <dt>Frames</dt>
            <dd>{frames.length || "—"}</dd>
          </div>
          <div>
            <dt>Contact</dt>
            <dd>
              <a href={`mailto:${copy.email}`}>{copy.email}</a>
            </dd>
          </div>
        </dl>
      </section>

      {/* Above the work, not below it: it's how a visitor finds the second
          artist, and at the bottom of a long page it may as well not exist. */}
      {roster.length > 1 ? (
        <section className="about about--roster" id="artists">
          <h2 className="mono">Artists</h2>
          <div className="about-body">
            <ul className="roster">
              {roster.map((entry) => (
                <li key={entry.slug}>
                  <a className="roster-name" href={`/artist/${entry.slug}`}>
                    {entry.displayName}
                  </a>
                  <span className="roster-line">
                    {entry.tagline}
                    {entry.location ? <> — {entry.location}</> : null}
                  </span>
                </li>
              ))}
            </ul>
          </div>
        </section>
      ) : null}

      <main id="work">
        {failed ? (
          <section className="sheet">
            <p className="sheet-note">
              The gallery couldn&apos;t be loaded.{" "}
              <button
                type="button"
                className="frame-action"
                onClick={() => setAttempt((n) => n + 1)}
              >
                Try again
              </button>
            </p>
          </section>
        ) : albums === null ? (
          <section className="sheet">
            <p className="sheet-note">Loading the gallery...</p>
          </section>
        ) : albums.length === 0 ? (
          <section className="sheet">
            <p className="sheet-note">
              No albums are published yet. Published albums appear here.
            </p>
          </section>
        ) : (
          sections.map(({ album, frames: albumFrames }) => (
            <section className="sheet" key={album.id}>
              <div className="sheet-head">
                <h2>{album.title}</h2>
                <span className="mono">
                  {albumFrames.length}{" "}
                  {albumFrames.length === 1 ? "frame" : "frames"}
                </span>
              </div>
              {/* Whose work this is, then anything else worth saying about it. */}
              <p className="sheet-credit">
                {album.artistSlug ? (
                  <a href={`/artist/${album.artistSlug}`}>
                    {album.artistName ?? album.artistSlug}
                  </a>
                ) : null}
                {creditFor(album) ? <> · {creditFor(album)}</> : null}
              </p>

              <div className="sheet-grid" ref={fitGrid}>
                {albumFrames.map((frame) => (
                  <figure className="frame" key={frame.id}>
                    <button
                      type="button"
                      className="frame-open"
                      onClick={() => setViewing(frame.index)}
                      aria-label={`View ${frame.title ?? "this frame"} larger`}
                    >
                      {/* Plain <img>: same-origin /api paths proxied by this
                          server, and next/image would re-fetch and re-encode
                          them for no benefit. */}
                      {/* eslint-disable-next-line @next/next/no-img-element */}
                      <img
                        src={`${API_BASE}${frame.previewUrl}`}
                        alt=""
                        loading="lazy"
                      />
                    </button>
                    <figcaption>
                      <span className="frame-no">
                        {String(frame.index + 1).padStart(2, "0")}
                      </span>
                      <span className="frame-title">
                        {frame.title ?? "Untitled"}
                      </span>
                    </figcaption>
                  </figure>
                ))}
              </div>
            </section>
          ))
        )}
      </main>

      <section className="about" id="about">
        <h2 className="mono">About</h2>
        <div className="about-body">
          <p className="about-bio">{copy.bio}</p>
          <p className="about-line">
            Available for assignments —{" "}
            <a href={`mailto:${copy.email}`}>{copy.email}</a>
            {copy.phone ? <> · {copy.phone}</> : null}
          </p>
        </div>
      </section>

      <footer className="site-footer">
        <span>
          {copy.name} — {copy.role}
        </span>
        <span>
          <a href={`mailto:${copy.email}`}>{copy.email}</a>
          {copy.instagram ? <> · {copy.instagram}</> : null}
          {" · "}
          <a href={LOGIN_PATH}>Sign in</a>
        </span>
        <span>
          © {new Date().getFullYear()} {copy.name}. All rights reserved.
        </span>
      </footer>

      {viewing !== null ? (
        <PhotoViewer
          items={frames}
          index={viewing}
          onClose={closeViewer}
          onIndexChange={changeViewer}
        />
      ) : null}

      <BackToTop />
    </div>
  );
}
