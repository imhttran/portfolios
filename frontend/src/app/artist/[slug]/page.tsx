"use client";

import { use } from "react";
import { LOGIN_PATH } from "@/lib/api";
import { SITE } from "@/lib/site";
import { useAlbumIndex } from "@/lib/usePortfolio";
import { AlbumIndex } from "@/components/AlbumIndex";
import { SheetNote } from "@/components/AlbumSheet";
import { BackToTop } from "@/components/BackToTop";
import { EmailLink } from "@/components/EmailLink";
import { InstagramLink } from "@/components/InstagramLink";
import { PageTitle } from "@/components/PageTitle";
import { SiteBar } from "@/components/SiteBar";

export default function ArtistPage({
  params,
}: {
  params: Promise<{ slug: string }>;
}) {
  // Next hands route params to a client page as a promise.
  const { slug } = use(params);

  const { artist, albums, failed, missing, loading, retry } =
    useAlbumIndex(slug);

  return (
    // The artist's own theme, when they have one and the visitor hasn't chosen.
    // It sits on this container rather than on <html> so it applies to their
    // page alone, and so leaving the page removes it without any cleanup.
    <div className="site" data-artist-theme={artist?.theme ?? undefined}>
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
                <dt>Albums</dt>
                <dd>{albums?.length ?? "—"}</dd>
              </div>
              <div>
                <dt>Contact</dt>
                <dd>
                  <EmailLink
                    address={artist.contactEmail}
                    name={artist.displayName}
                  />
                </dd>
              </div>
            </dl>
          </section>

          {albums && albums.length > 0 ? (
            <AlbumIndex albums={albums} />
          ) : (
            <SheetNote>No albums are published yet.</SheetNote>
          )}

          <section className="about">
            <h2 className="mono">About</h2>
            <div className="about-body">
              <p className="about-bio">{artist.bio}</p>
              <p className="about-line">
                Available for assignments —{" "}
                <EmailLink
                  address={artist.contactEmail}
                  name={artist.displayName}
                />
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
          <EmailLink
            address={artist?.contactEmail ?? SITE.email}
            name={artist?.displayName ?? SITE.name}
          />
          {artist?.instagram ? (
            <>
              {" · "}
              <InstagramLink
                handle={artist.instagram}
                name={artist?.displayName ?? SITE.name}
              />
            </>
          ) : null}
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

      <BackToTop />
    </div>
  );
}
