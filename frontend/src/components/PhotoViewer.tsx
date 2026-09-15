"use client";

import { useEffect, useRef, useState } from "react";
import { API_BASE } from "@/lib/api";

export type ViewerItem = {
  id: number;
  title: string | null;
  // The preview file, not the original: the viewer shows the same file the grid
  // loaded, so opening a frame costs no extra download.
  previewUrl: string;
  // Where a download of this frame's original lives, when one is on offer.
  downloadUrl?: string;
  // The photograph's true dimensions, straight from the row. Preferred over
  // measuring the loaded preview, which is downscaled and would understate it.
  width?: number | null;
  height?: number | null;
  // Whose work it is, carried per frame so a sheet mixing credited albums still
  // names the right artist on each one.
  credit?: string | null;
};

// Full-screen look at one frame.
//
// This is where the grid's uniform crop gives way: the sheet presents even
// frames so the sequence reads, and the viewer shows the photograph whole, at
// its own ratio, with its real dimensions read off the file itself.
export function PhotoViewer({
  items,
  index,
  onClose,
  onIndexChange,
  onDownload,
  busy,
}: {
  items: ViewerItem[];
  index: number;
  onClose: () => void;
  onIndexChange: (next: number) => void;
  // Omitted on the public page, where there is nothing to download.
  onDownload?: (item: ViewerItem) => void;
  busy?: boolean;
}) {
  const rootRef = useRef<HTMLDivElement>(null);
  const closeRef = useRef<HTMLButtonElement>(null);
  // Measured from the loaded preview, used only when the row has no dimensions
  // of its own (hand-seeded placeholders, for instance).
  const [measured, setMeasured] = useState<{ w: number; h: number } | null>(
    null,
  );

  const item = items[index];
  const size =
    item?.width && item?.height ? { w: item.width, h: item.height } : measured;
  // Guards the mount effect below: without it, an out-of-range index would
  // still lock the page and move focus, leaving no dialog on screen to close.
  const hasItem = Boolean(item);

  const step = (delta: number) => {
    setMeasured(null);
    onIndexChange((index + delta + items.length) % items.length);
  };

  // Handlers reach the keydown listener through refs, so the listener can be
  // registered once at mount: re-registering on every navigation would re-run
  // the focus and scroll-lock setup and yank focus to Close on each arrow key.
  const stepRef = useRef(step);
  const closeFnRef = useRef(onClose);
  useEffect(() => {
    stepRef.current = step;
    closeFnRef.current = onClose;
  });

  useEffect(() => {
    if (!hasItem) return;
    const restoreTo = document.activeElement as HTMLElement | null;
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    closeRef.current?.focus();

    const focusables = () =>
      Array.from(
        rootRef.current?.querySelectorAll<HTMLElement>("button, a[href]") ?? [],
      );

    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        closeFnRef.current();
      } else if (event.key === "ArrowRight") {
        stepRef.current(1);
      } else if (event.key === "ArrowLeft") {
        stepRef.current(-1);
      } else if (event.key === "Tab") {
        // Minimal focus trap: aria-modal promises the rest of the page is out
        // of reach, so Tab has to cycle within the dialog.
        const targets = focusables();
        if (targets.length === 0) return;
        const first = targets[0];
        const last = targets[targets.length - 1];
        const active = document.activeElement;
        if (
          event.shiftKey &&
          (active === first || !rootRef.current?.contains(active))
        ) {
          event.preventDefault();
          last.focus();
        } else if (!event.shiftKey && active === last) {
          event.preventDefault();
          first.focus();
        }
      }
    };

    window.addEventListener("keydown", onKey);
    return () => {
      window.removeEventListener("keydown", onKey);
      document.body.style.overflow = previousOverflow;
      restoreTo?.focus?.();
    };
  }, [hasItem]);

  if (!item) return null;

  return (
    <div
      ref={rootRef}
      className="viewer"
      role="dialog"
      aria-modal="true"
      aria-label={item.title ?? "Photograph"}
      onClick={(event) => {
        // Close on a click anywhere that isn't the photograph or a control.
        // Testing the target rather than the container matters because the bar
        // and metadata rows span the full width, which would otherwise leave
        // almost no backdrop to click.
        const target = event.target as HTMLElement;
        if (target.closest("img, button, a")) return;
        onClose();
      }}
    >
      <div className="viewer-bar">
        <span className="mono">
          {String(index + 1).padStart(2, "0")} /{" "}
          {String(items.length).padStart(2, "0")}
        </span>
        <button
          ref={closeRef}
          type="button"
          className="viewer-button"
          onClick={onClose}
        >
          Close
        </button>
      </div>

      <div className="viewer-stage">
        {/* Plain <img>: the frame is served from this same origin, and its
            natural ratio is the point - no next/image sizing, no crop. */}
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img
          key={item.id}
          src={`${API_BASE}${item.previewUrl}`}
          alt={item.title ?? "Photograph"}
          onLoad={(event) =>
            setMeasured({
              w: event.currentTarget.naturalWidth,
              h: event.currentTarget.naturalHeight,
            })
          }
        />
      </div>

      <div className="viewer-meta">
        <span className="viewer-title">{item.title ?? "Untitled"}</span>
        {size ? (
          <span className="mono">
            {size.w} × {size.h}
          </span>
        ) : null}
        {item.credit ? <span className="mono">{item.credit}</span> : null}
        {onDownload ? (
          <button
            type="button"
            className="viewer-button"
            disabled={busy}
            onClick={() => onDownload(item)}
          >
            {busy ? "Preparing..." : "Download"}
          </button>
        ) : null}
      </div>

      {items.length > 1 ? (
        <>
          <button
            type="button"
            className="viewer-nav viewer-nav--prev"
            aria-label="Previous frame"
            onClick={() => step(-1)}
          >
            ←
          </button>
          <button
            type="button"
            className="viewer-nav viewer-nav--next"
            aria-label="Next frame"
            onClick={() => step(1)}
          >
            →
          </button>
        </>
      ) : null}
    </div>
  );
}
