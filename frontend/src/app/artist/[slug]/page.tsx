"use client";

import { use, useState } from "react";
import { LOGIN_PATH } from "@/lib/api";
import { SITE } from "@/lib/site";
import { usePortfolio } from "@/lib/usePortfolio";
import { AlbumSheet, SheetNote } from "@/components/AlbumSheet";
import { BackToTop } from "@/components/BackToTop";
import { PageTitle } from "@/components/PageTitle";
import { PhotoViewer } from "@/components/PhotoViewer";
import { SiteBar } from "@/components/SiteBar";

export default function ArtistPage({
  params,
}: {
  params: Promise<{ slug: string }>;
}) {
  // Next hands route params to a client page as a promise.
  const { slug } = use(params);

  const { artist, sections, frames, failed, missing, loading, retry } =
    usePortfolio(slug);
  const [viewing, setViewing] = useState<number | null>(null);

  return (
    <div className="site">
      <PageTitle
        title={
          artist
            ? `${artist.displayName} — ${artist.tagline} | ${SITE.name}`
            : SITE.name
        }
      />
      <SiteBar
        name={artist?.displayName ?? "Artist"}
        role={artist?.tagline ?? ""}
        links={[
          { href: "/#artists", label: "All artists" },
          { href: "/gallery", label: "Client access" },
        ]}
      />

      {missing ? (
        <SheetNote>
          No artist at that address. <a href="/#artists">See everyone</a>.
        </SheetNote>
      ) : failed ? (
        <SheetNote>
          The gallery couldn’t be loaded.{" "}
          <button type="button" className="frame-action" onClick={retry}>
            Try again
          </button>
        </SheetNote>
      ) : loading || !artist ? (
        <SheetNote>Loading…</SheetNote>
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
              <SheetNote>No albums are published yet.</SheetNote>
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
