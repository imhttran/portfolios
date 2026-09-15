"use client";

import { LOGIN_PATH } from "@/lib/api";
import { useSiteCopy } from "@/lib/useSiteCopy";
import { useAlbumIndex } from "@/lib/usePortfolio";
import { AlbumIndex } from "@/components/AlbumIndex";
import { SheetNote } from "@/components/AlbumSheet";
import { PageTitle } from "@/components/PageTitle";
import { SiteBar } from "@/components/SiteBar";

/**
 * The client area: every album on the site, one tile each.
 *
 * An index, like the front page, so a subscriber picks what to look at instead
 * of scrolling the entire library. The tier is stated here and the download
 * controls live on the album itself.
 */
export default function GalleryPage() {
  const { albums, signedIn, failed, loading, retry } = useAlbumIndex();
  const copy = useSiteCopy();

  return (
    <div className="site">
      <PageTitle title={`Client access | ${copy.name}`} />
      <SiteBar
        name={copy.name}
        role={copy.role}
        links={[
          { href: "/#work", label: "Work" },
          { href: "/#about", label: "About" },
          signedIn
            ? { href: "/dashboard", label: "Dashboard" }
            : { href: LOGIN_PATH, label: "Sign in" },
        ]}
      />

      <main>
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
          <SheetNote>No albums are published yet.</SheetNote>
        ) : (
          <AlbumIndex albums={albums} heading="h1" />
        )}
      </main>

      {!signedIn && !loading && albums && albums.length > 0 ? (
        <p className="sheet-note">
          <a href={LOGIN_PATH}>Sign in</a> to download free work.
        </p>
      ) : null}

      <footer className="site-footer">
        <span>
          {copy.name} — {copy.role}
        </span>
        <span>
          <a href={`mailto:${copy.email}`}>{copy.email}</a>
        </span>
        <span>
          © {new Date().getFullYear()} {copy.name}
        </span>
      </footer>
    </div>
  );
}
