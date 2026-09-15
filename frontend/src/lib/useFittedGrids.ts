"use client";

import { useEffect, type RefCallback } from "react";

// An album is a sheet sized to the frame it is shown in. A fixed column count
// can't do that: four photographs leave half a window empty, twenty-seven run
// on for two windows. So the grid works out its own columns from the space it
// actually has - see bestLayout() for the arithmetic.
//
// The one fixed thing is the artist's ceiling, data-max-cols: how dense their
// sheets are allowed to get. It caps the count the grid would otherwise choose,
// so an artist who wants two across keeps two across on every window.
//
// The numbers come from the browser (viewport height, element widths), which
// the server render cannot know, so the server sends the CSS fallback and this
// replaces it as soon as the grid is in the document.

// The frame crop: 3 across, 2 down. Every cell keeps it, so an album reads as a
// contact sheet rather than as differently shaped pictures.
const CROP = 2 / 3;

// A photograph never gets narrower than this. An album that cannot be shown
// within it keeps the plain width-driven layout and scrolls, rather than
// turning into confetti. It has to stay low enough that a laptop window can
// still fit a whole roll - at 140px, twenty-seven photographs stopped fitting
// a 1280-wide window at all.
const MIN_CELL = 110;

// The 1px hairlines between cells are the grid's gap, so they count.
const GAP = 1;

// Two layouts whose heights are within this much of each other count as equal,
// which leaves the tie to be broken on photograph size instead. Without it a
// layout that is a pixel closer to the frame wins over one with visibly larger
// photographs.
const SAME = 0.02;

type Layout = { cols: number; width: number; height: number };

function layoutWithin(
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
    const rows = Math.ceil(count / cols);
    // The cell width at which this many rows fills the frame exactly. Solving
    // from the height, rather than from the width, is what lets an album fill a
    // frame: a grid that is always as wide as the sheet cannot do it, so it is
    // allowed to come in from the edges and sit centred instead.
    const exact =
      inset + (available - (rows - 1) * GAP - rows * chrome) / (rows * CROP);
    // Never wider than its row can hold, never narrower than legible.
    const cell = Math.min(exact, (width - (cols - 1) * GAP) / cols);
    if (cell < MIN_CELL) continue;

    const usedWidth = cols * cell + (cols - 1) * GAP;
    candidates.push({
      cols,
      width: usedWidth,
      // A cell is not all photograph: the frame's own side padding narrows the
      // image, which shortens the row by that much again.
      height: rows * (chrome + (cell - inset) * CROP) + (rows - 1) * GAP,
    });
  }

  if (!candidates.length) return null;

  // Fill the frame; where two layouts do that equally well, take the wider one,
  // because that is the one with the larger photographs in it.
  const tallest = Math.max(...candidates.map((c) => c.height));
  const close = candidates.filter(
    (c) => c.height >= tallest - available * SAME,
  );
  return close.reduce((a, b) => (b.width > a.width ? b : a));
}

// The artist's ceiling is a preference for how dense their sheets read, not a
// hard limit: a ceiling can be unreachable. Four across a roll of twenty-seven
// needs seven rows, and seven rows in one window leaves the frames under the
// legible size - so that album falls back to the columns the grid would have
// chosen on its own, because an album that fills the window is the point.
function bestLayout(
  count: number,
  width: number,
  available: number,
  chrome: number,
  inset: number,
  cap: number | null,
): Layout | null {
  const capped = layoutWithin(count, width, available, chrome, inset, cap);
  if (capped || cap === null) return capped;
  return layoutWithin(count, width, available, chrome, inset, null);
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
  // The frame to fill is the browser window: from just under the album's own
  // heading down to the bottom edge. The sheet's bottom padding is deliberately
  // not subtracted - the grid reaches the edge and that padding falls below the
  // fold, which is what separates one album from the next.
  const available =
    window.innerHeight -
    parseFloat(style.paddingTop) -
    (head?.getBoundingClientRect().height ?? 0) -
    (credit?.getBoundingClientRect().height ?? 0);

  const width = grid.clientWidth;
  if (width <= 0 || available <= 0) return;

  // The artist's ceiling, read off the element so a grid carries its own limit
  // wherever it is rendered. Absent, or unparseable, means no ceiling.
  const cap = Number(grid.dataset.maxCols) || null;

  const layout = bestLayout(count, width, available, chrome, inset, cap);
  if (!layout) {
    // No layout is legible in this frame even without a ceiling, so hand the
    // album back to the plain width-driven grid and let it scroll.
    grid.style.removeProperty("--cols");
    grid.style.removeProperty("max-width");
    delete grid.dataset.fit;
    return;
  }

  grid.style.setProperty("--cols", String(layout.cols));
  grid.style.setProperty("max-width", `${Math.round(layout.width)}px`);
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
