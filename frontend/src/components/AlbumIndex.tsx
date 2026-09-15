"use client";

import { API_BASE } from "@/lib/api";
import type { Album } from "@/lib/usePortfolio";

/**
 * The albums as an index: one tile per album, its first photograph on it.
 *
 * This is the page you read to decide what to look at, so it is deliberately not
 * a contact sheet - no fit solver, no per-artist ceiling, no stretching. A
 * uniform, width-driven grid gives the same density on every visit, which is
 * what makes an index scannable; the album behind the click is where the frames
 * are sized to the window.
 */
export function AlbumIndex({
  albums,
  heading = "h2",
}: {
  albums: Album[];
  heading?: "h1" | "h2";
}) {
  const Heading = heading;

  return (
    <section className="sheet" id="work">
      <div className="sheet-head">
        <Heading>Work</Heading>
        <span className="mono">
          {albums.length} {albums.length === 1 ? "album" : "albums"}
        </span>
      </div>

      <div className="index-grid">
        {albums.map((album) => (
          <figure className="cover" key={album.id}>
            <a
              className="cover-open"
              href={`/album/${album.slug}`}
              // The tile is the photograph, so the anchor has no text of its
              // own; this is what names it. alt="" because the title below
              // already carries the album's name, and a second copy would just
              // be announced twice.
              aria-label={`View ${album.title}`}
            >
              {/* Plain <img>: same-origin /api paths proxied by this server. */}
              {/* eslint-disable-next-line @next/next/no-img-element */}
              {album.coverUrl ? (
                <img
                  src={`${API_BASE}${album.coverUrl}`}
                  alt=""
                  loading="lazy"
                />
              ) : (
                <span className="cover-frame" />
              )}
            </a>
            <figcaption className="cover-meta">
              <a className="cover-title" href={`/album/${album.slug}`}>
                {album.title}
              </a>
              <span className="cover-line mono">
                {album.artistName ?? album.artistSlug ?? "Unattributed"}
                {" · "}
                {album.photoCount} {album.photoCount === 1 ? "frame" : "frames"}
              </span>
            </figcaption>
          </figure>
        ))}
      </div>
    </section>
  );
}
