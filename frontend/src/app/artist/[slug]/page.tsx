"use client";

import { use } from "react";
import { LOGIN_PATH } from "@/lib/api";
import { ABOUT_MORE, SITE } from "@/lib/site";
import { useAlbumIndex } from "@/lib/usePortfolio";
import { useRoster } from "@/lib/useRoster";
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
  const roster = useRoster();

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
        over
        icon={artist?.slug === SITE.slug ? "/icon.png" : undefined}
        name={artist?.displayName ?? "Artist"}
        role={artist?.tagline ?? ""}
        links={[
          { href: "#work", label: "Work" },
          ...(artist?.slug === SITE.slug
            ? [{ href: "#about", label: "About" }]
            : []),
          ...(roster.length > 1
            ? [{ href: "#artists", label: "Artists" }]
            : []),
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
          <section className="hero">
            <h1 className="hero-statement">{artist.statement}</h1>
            <p className="hero-sub">{artist.bio}</p>
            <div className="hero-contact">
              <EmailLink
                address={artist.contactEmail}
                name={artist.displayName}
              />
              {artist.instagram ? (
                <InstagramLink
                  handle={artist.instagram}
                  name={artist.displayName}
                />
              ) : null}
            </div>
          </section>

          {/* Above the work, not below it: it's how a visitor finds the rest
              of the roster, and at the bottom of a long page it may as well
              not exist. */}
          {roster.length > 1 ? (
            <section className="about about--roster" id="artists">
              <h2 className="mono">Artists</h2>
              <div className="about-body">
                <ul className="roster">
                  {roster.map((entry) => (
                    <li key={entry.slug}>
                      <a
                        className="roster-name"
                        href={`/artist/${entry.slug}`}
                      >
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

          {albums && albums.length > 0 ? (
            <AlbumIndex albums={albums} />
          ) : (
            <SheetNote>No albums are published yet.</SheetNote>
          )}

          {artist.slug === SITE.slug ? (
            <section className="about" id="about">
              <h2 className="mono">About</h2>
              <div className="about-body">
                {ABOUT_MORE.map((paragraph, index) => (
                  <p className="about-more" key={index}>
                    {paragraph}
                  </p>
                ))}
              </div>
            </section>
          ) : null}
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
