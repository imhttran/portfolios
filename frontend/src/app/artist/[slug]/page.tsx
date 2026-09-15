"use client";

import { use, useEffect, useMemo, useState } from "react";
import { API_BASE, LOGIN_PATH } from "@/lib/api";
import { SITE } from "@/lib/site";
import { fitGrid, useFittedGrids } from "@/lib/useFittedGrids";
import { BackToTop } from "@/components/BackToTop";
import { PageTitle } from "@/components/PageTitle";
import { PhotoViewer } from "@/components/PhotoViewer";
import { SignOut } from "@/components/SignOut";
import { ThemeToggle } from "@/components/ThemeToggle";

type Artist = {
  slug: string;
  displayName: string;
  tagline: string;
  statement: string;
  bio: string;
  location: string;
  contactEmail: string;
  phone: string | null;
  instagram: string | null;
};

type Album = {
  id: number;
  slug: string;
  title: string;
  credit: string | null;
  description: string | null;
  access: string;
};

type Photo = {
  id: number;
  title: string | null;
  previewUrl: string;
  width: number | null;
  height: number | null;
};

type Loaded = { album: Album; photos: Photo[] };

export default function ArtistPage({
  params,
}: {
  params: Promise<{ slug: string }>;
}) {
  // Next hands route params to a client page as a promise.
  const { slug } = use(params);

  const [artist, setArtist] = useState<Artist | null>(null);
  const [albums, setAlbums] = useState<Loaded[] | null>(null);
  const [missing, setMissing] = useState(false);
  const [viewing, setViewing] = useState<number | null>(null);

  useEffect(() => {
    let cancelled = false;

    (async () => {
      try {
        const response = await fetch(`${API_BASE}/api/artists/${slug}`);
        if (response.status === 404) {
          if (!cancelled) setMissing(true);
          return;
        }
        const data = await response.json();
        if (!response.ok) throw new Error(data.message);
        if (cancelled) return;
        setArtist(data.artist as Artist);

        // Same shape as the other pages: one detail request per album, so the
        // listing endpoint doesn't inline every photo in the library.
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
        if (!cancelled) setMissing(true);
      }
    })();

    return () => {
      cancelled = true;
    };
  }, [slug]);

  // Frames numbered straight through this artist's albums, so the viewer's
  // sequence runs continuously the way it does on the other pages.
  const sections = useMemo(() => {
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

  const frames = useMemo(() => sections.flatMap((s) => s.frames), [sections]);

  return (
    <div className="site">
      <PageTitle
        title={
          artist
            ? `${artist.displayName} — ${artist.tagline} | ${SITE.name}`
            : SITE.name
        }
      />
      <header className="site-bar">
        <a className="site-identity" href="/">
          <span className="site-name">{artist?.displayName ?? "Artist"}</span>
          <span className="site-role">{artist?.tagline ?? ""}</span>
        </a>
        <nav className="site-nav">
          <a href="/#artists">All artists</a>
          <a href="/gallery">Client access</a>
          <ThemeToggle />
          <SignOut />
        </nav>
      </header>

      {missing ? (
        <main className="sheet">
          <p className="sheet-note">
            No artist at that address. <a href="/#artists">See everyone</a>.
          </p>
        </main>
      ) : !artist ? (
        <main className="sheet">
          <p className="sheet-note">Loading...</p>
        </main>
      ) : (
        <>
          <section className="hero hero--plain">
            <h1 className="hero-statement">{artist.statement}</h1>
            <dl className="hero-meta">
              <div>
                <dt>Based in</dt>
                <dd>{artist.location}</dd>
              </div>
              <div>
                <dt>Frames</dt>
                <dd>{frames.length || "—"}</dd>
              </div>
              <div>
                <dt>Contact</dt>
                <dd>
                  <a href={`mailto:${artist.contactEmail}`}>
                    {artist.contactEmail}
                  </a>
                </dd>
              </div>
            </dl>
          </section>

          <main>
            {sections.length === 0 ? (
              <section className="sheet">
                <p className="sheet-note">No albums are published yet.</p>
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
                  <p className="sheet-credit">
                    {album.credit ?? album.description}
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

            <section className="about">
              <h2 className="mono">About</h2>
              <div className="about-body">
                <p className="about-bio">{artist.bio}</p>
                <p className="about-line">
                  Available for assignments —{" "}
                  <a href={`mailto:${artist.contactEmail}`}>
                    {artist.contactEmail}
                  </a>
                  {artist.phone ? <> · {artist.phone}</> : null}
                </p>
              </div>
            </section>
          </main>
        </>
      )}

      <footer className="site-footer">
        <span>
          {artist?.displayName ?? SITE.name} — {artist?.tagline ?? SITE.role}
        </span>
        <span>
          <a href={`mailto:${artist?.contactEmail ?? SITE.email}`}>
            {artist?.contactEmail ?? SITE.email}
          </a>
          {artist?.instagram ? <> · {artist.instagram}</> : null}
          {" · "}
          <a href={LOGIN_PATH}>Sign in</a>
        </span>
        <span>
          {/* The other two spans are this artist's, so the sign-off names them
              too: naming the site here read as two people's footer, and had the
              site claiming copyright over work it doesn't own. */}
          © {new Date().getFullYear()} {artist?.displayName ?? SITE.name}. All
          rights reserved.
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
