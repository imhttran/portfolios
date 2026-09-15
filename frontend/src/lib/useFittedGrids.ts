"use client";

import { useEffect, type RefCallback } from "react";

// An album is a sheet that spans the frame it is shown in. The sheet's width
// sets the size of a frame, and the column count then decides how many rows the
// album runs to - so an album is as tall as its own count makes it, on the full
// width of the page, rather than being squeezed until one window can hold it.
//
// Two things choose the count: the artist's ceiling (data-max-cols), and the
// window, which the grid reads to pick the count whose rows come nearest to
// filling it. See bestLayout() for the arithmetic.
//
// The numbers come from the browser (viewport height, element widths), which
// the server render cannot know, so the server sends the CSS fallback and this
// replaces it as soon as the grid is in the document.

// The frame crop: 3 across, 2 down. Every cell keeps it, so an album reads as a
// contact sheet rather than as differently shaped pictures.
const CROP = 2 / 3;

// A frame never gets narrower than this, so a column count that would take it
// below this is not offered at all - which is what stops a narrow window from
// turning a sheet into confetti. If no count clears it, the album keeps the
// plain width-driven grid instead.
const MIN_CELL = 110;

// The 1px hairlines between cells are the grid's gap, so they count.
const GAP = 1;

type Layout = { cols: number; height: number };

function bestLayout(
  count: number,
  width: number,
  available: number,
  chrome: number,
  inset: number,
  cap: number | null,
): Layout | null {
  const widest = Math.max(1, Math.floor((width + GAP) / (MIN_CELL + GAP)));
  // No ceiling means "as many as fit", which is what count already is.
  const max = Math.min(count, widest, cap ?? count);
  // A single column fills a narrow frame exactly, by standing one narrow strip of
  // photographs in the middle of it. That is not a contact sheet, so more than
  // one photograph always gets at least two columns.
  const min = count > 1 ? 2 : 1;

  const candidates: Layout[] = [];
  for (let cols = min; cols <= max; cols++) {
    // The cell that makes this many columns span the sheet exactly. Solving
    // from the width is what puts the album edge to edge; the count then decides
    // how many rows that makes, and so how tall the album runs.
    const cell = (width - (cols - 1) * GAP) / cols;
    if (cell < MIN_CELL) continue;

    const rows = Math.ceil(count / cols);
    candidates.push({
      cols,
      // A cell is not all photograph: the frame's own side padding narrows the
      // image, which shortens the row by that much again.
      height: rows * (chrome + (cell - inset) * CROP) + (rows - 1) * GAP,
    });
  }

  if (!candidates.length) return null;

  // The count whose rows land nearest the window: the tallest that still fits,
  // or - when none does, because the artist's ceiling keeps the columns few and
  // the rows therefore tall - the shortest of them, so the album runs on as
  // little as the ceiling allows.
  const fits = candidates.filter((c) => c.height <= available);
  if (fits.length) {
    return fits.reduce((a, b) => (b.height > a.height ? b : a));
  }
  return candidates.reduce((a, b) => (b.height < a.height ? b : a));
}

function fitOne(grid: HTMLElement): void {
  const count = grid.childElementCount;
  const sheet = grid.closest<HTMLElement>(".sheet");
  if (!count || !sheet) return;

  // Everything in a cell that isn't the photograph (frame padding and caption),
  // and how much narrower the photograph is than the cell it sits in. Measured
  // rather than assumed, so both follow the frame's padding and the type as
  // they scale.
  const first = grid.firstElementChild as HTMLElement | null;
  const image = first?.querySelector("img");
  const frameBox = first?.getBoundingClientRect();
  const imageBox = image?.getBoundingClientRect();
  const measured = frameBox && imageBox && imageBox.height > 0;
  const chrome = measured ? frameBox.height - imageBox.height : 51;
  const inset = measured ? frameBox.width - imageBox.width : 20;

  const style = getComputedStyle(sheet);
  const head = sheet.querySelector<HTMLElement>(".sheet-head");
  const credit = sheet.querySelector<HTMLElement>(".sheet-credit");
  // How tall the album is allowed to be before it runs past the window: from
  // just under its own heading down to the bottom edge. Nothing here decides the
  // frame size - the width does that - so this only steers which column count is
  // chosen.
  const available =
    window.innerHeight -
    parseFloat(style.paddingTop) -
    (head?.getBoundingClientRect().height ?? 0) -
    (credit?.getBoundingClientRect().height ?? 0);

  // The sheet's own content column, which is the width the grid spans. Measured
  // from the sheet rather than from the grid: a grid carrying a max-width from
  // an earlier fit would otherwise report that narrower width back and never
  // grow out to the frame again.
  const width =
    sheet.clientWidth -
    parseFloat(style.paddingLeft) -
    parseFloat(style.paddingRight);
  if (width <= 0 || available <= 0) return;

  // The artist's ceiling, read off the element so a grid carries its own limit
  // wherever it is rendered. Absent, or unparseable, means no ceiling.
  const cap = Number(grid.dataset.maxCols) || null;

  const layout = bestLayout(count, width, available, chrome, inset, cap);
  if (!layout) {
    // No layout is legible in this frame - the frames would be narrower than a
    // thumbnail - so hand the album back to the plain width-driven grid.
    grid.style.removeProperty("--cols");
    grid.style.removeProperty("max-width");
    delete grid.dataset.fit;
    return;
  }

  grid.style.setProperty("--cols", String(layout.cols));
  // No max-width: the grid is the width of the sheet, which is the whole point.
  // A stale one from an earlier fit would hold it in from the edges.
  grid.style.removeProperty("max-width");
  grid.dataset.fit = "on";
}

// Attached to each grid, so the fit lands before the first paint and the album
// never shows the fallback for a frame.
export const fitGrid: RefCallback<HTMLDivElement> = (element) => {
  if (element) fitOne(element);
};

/**
 * Re-fit every album on the page. Pass the loaded albums so a change in the
 * data (or a fresh fetch) re-measures, and the listener covers resizing.
 */
export function useFittedGrids(albums: unknown): void {
  useEffect(() => {
    const fitAll = () => {
      document.querySelectorAll<HTMLElement>(".sheet-grid").forEach(fitOne);
    };
    fitAll();
    window.addEventListener("resize", fitAll);
    return () => window.removeEventListener("resize", fitAll);
  }, [albums]);
}
