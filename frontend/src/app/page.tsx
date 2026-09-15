"use client";

import { CLIENT_ACCESS_LABEL, splitParagraphs } from "@/lib/site";
import { useSiteCopy } from "@/lib/useSiteCopy";
import { useAlbumIndex } from "@/lib/usePortfolio";
import { useRoster } from "@/lib/useRoster";
import { AlbumIndex } from "@/components/AlbumIndex";
import { SheetNote } from "@/components/AlbumSheet";
import { EmailLink } from "@/components/EmailLink";
import { InstagramLink } from "@/components/InstagramLink";
import { PageTitle } from "@/components/PageTitle";
import { SiteBar } from "@/components/SiteBar";
import { SiteFooter } from "@/components/SiteFooter";

/**
 * The front page: the statement, who is on the site, and an index of the work.
 *
 * An index rather than the work itself - the design reference does the same, and
 * it is what keeps a portfolio's front page readable rather than a twenty-minute
 * scroll. The photographs are one click away, on the album's own page.
 */
export default function PortfolioPage() {
  const { albums, failed, loading, retry } = useAlbumIndex();
  const roster = useRoster();
  const copy = useSiteCopy();

  return (
    <div className="site">
      <PageTitle title={`${copy.name} — ${copy.role}`} />
      <SiteBar
        over
        icon="/icon.png"
        name={copy.name}
        role={copy.role}
        links={[
          { href: "#work", label: "Work" },
          { href: "#about", label: "About" },
          ...(roster.length > 1
            ? [{ href: "#artists", label: "Artists" }]
            : []),
          { href: "/gallery", label: CLIENT_ACCESS_LABEL },
        ]}
      />

      {/* The reference's masthead: one flat dark band carrying the statement.
          No photograph behind it - the photographs come below, and a white page
          with one black band is the whole idea. */}
      <section className="hero">
        <h1 className="hero-statement">{copy.statement}</h1>
        <p className="hero-sub">{copy.bio}</p>

        <div className="hero-contact">
          <EmailLink address={copy.email} name={copy.name} />
          {copy.instagram ? (
            <InstagramLink handle={copy.instagram} name={copy.name} />
          ) : null}
        </div>
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

      {failed ? (
        <SheetNote>
          The gallery couldn’t be loaded.{" "}
          <button type="button" className="frame-action" onClick={retry}>
            Try again
          </button>
        </SheetNote>
      ) : loading || !albums ? (
        <SheetNote>Loading the gallery…</SheetNote>
      ) : albums.length === 0 ? (
        <SheetNote>
          No albums are published yet. Published albums appear here.
        </SheetNote>
      ) : (
        <AlbumIndex albums={albums} />
      )}

      <section className="about" id="about">
        <h2 className="mono">About</h2>
        <div className="about-body">
          {splitParagraphs(copy.about).map((paragraph, index) => (
            <p className="about-more" key={index}>
              {paragraph}
            </p>
          ))}
        </div>
      </section>

      <SiteFooter
        name={copy.name}
        role={copy.role}
        email={copy.email}
        instagram={copy.instagram}
      />
    </div>
  );
}
