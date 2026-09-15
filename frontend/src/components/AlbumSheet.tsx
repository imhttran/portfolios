"use client";

import type { ReactNode } from "react";
import { API_BASE } from "@/lib/api";
import { creditFor } from "@/lib/credits";
import { fitGrid } from "@/lib/useFittedGrids";
import type { Album, Frame } from "@/lib/usePortfolio";

/** A one-line note where an album would be: loading, empty, or broken. */
export function SheetNote({ children }: { children: ReactNode }) {
  return (
    <section className="sheet">
      <p className="sheet-note">{children}</p>
    </section>
  );
}

/**
 * One album as a contact sheet: its title, whose work it is, and every frame in
 * order.
 *
 * ``actions`` replaces the frame count beside the title - the client area puts
 * the tier and the download control there instead. ``frameAction`` renders per
 * frame, inside its caption, for the same reason.
 */
export function AlbumSheet({
  album,
  frames,
  onOpen,
  heading: Heading = "h2",
  actions,
  frameAction,
}: {
  album: Album;
  frames: Frame[];
  onOpen: (index: number) => void;
  heading?: "h1" | "h2";
  actions?: ReactNode;
  frameAction?: (frame: Frame) => ReactNode;
}) {
  const credit = creditFor(album);

  return (
    <section className="sheet">
      <div className="sheet-head">
        <Heading>{album.title}</Heading>
        {actions ?? (
          <span className="mono">
            {frames.length} {frames.length === 1 ? "frame" : "frames"}
          </span>
        )}
      </div>
      {/* Whose work this is, then anything else worth saying about it. */}
      <p className="sheet-credit">
        {album.artistSlug ? (
          <a href={`/artist/${album.artistSlug}`}>
            {album.artistName ?? album.artistSlug}
          </a>
        ) : null}
        {credit ? <> · {credit}</> : null}
      </p>

      <div
        className="sheet-grid"
        data-max-cols={album.artistColumns ?? undefined}
        ref={fitGrid}
      >
        {frames.map((frame) => (
          <figure className="frame" key={frame.id}>
            <button
              type="button"
              className="frame-open"
              onClick={() => onOpen(frame.index)}
              aria-label={`View ${frame.title ?? "this frame"} larger`}
            >
              {/* Plain <img>: same-origin /api paths proxied by this server, and
                  next/image would re-fetch and re-encode them for no benefit. */}
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
              <span className="frame-title" title={frame.title ?? undefined}>
                {frame.title ?? "Untitled"}
              </span>
              {frameAction?.(frame)}
            </figcaption>
          </figure>
        ))}
      </div>
    </section>
  );
}
