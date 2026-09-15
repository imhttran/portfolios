"use client";

import { useEffect, useState } from "react";
import { API_BASE, LOGIN_PATH } from "@/lib/api";
import { useSiteCopy } from "@/lib/useSiteCopy";
import { usePortfolio } from "@/lib/usePortfolio";
import { AlbumSheet, SheetNote } from "@/components/AlbumSheet";
import { BackToTop } from "@/components/BackToTop";
import { PageTitle } from "@/components/PageTitle";
import { PhotoViewer } from "@/components/PhotoViewer";
import { SiteBar } from "@/components/SiteBar";

type RosterArtist = {
  slug: string;
  displayName: string;
  tagline: string;
  location: string;
};

export default function PortfolioPage() {
  const { sections, frames, failed, loading, retry } = usePortfolio();
  const [viewing, setViewing] = useState<number | null>(null);
  const [heroLoaded, setHeroLoaded] = useState(false);
  const [roster, setRoster] = useState<RosterArtist[]>([]);
  const copy = useSiteCopy();

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

  return (
    <div className="site">
      <PageTitle title={`${copy.name} — ${copy.role}`} />
      <SiteBar
        over
        name={copy.name}
        role={copy.role}
        links={[
          { href: "#work", label: "Work" },
          { href: "#about", label: "About" },
          ...(roster.length > 1
            ? [{ href: "#artists", label: "Artists" }]
            : []),
          { href: "/gallery", label: "Client access" },
        ]}
      />

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
          <SheetNote>
            The gallery couldn’t be loaded.{" "}
            <button type="button" className="frame-action" onClick={retry}>
              Try again
            </button>
          </SheetNote>
        ) : loading ? (
          <SheetNote>Loading the gallery…</SheetNote>
        ) : sections.length === 0 ? (
          <SheetNote>
            No albums are published yet. Published albums appear here.
          </SheetNote>
        ) : (
          sections.map(({ album, frames: albumFrames }) => (
            <AlbumSheet
              key={album.id}
              album={album}
              frames={albumFrames}
              onOpen={setViewing}
            />
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
          onClose={() => setViewing(null)}
          onIndexChange={setViewing}
        />
      ) : null}

      <BackToTop />
    </div>
  );
}
