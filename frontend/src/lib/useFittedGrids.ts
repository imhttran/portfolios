"use client";

import { useEffect, type RefCallback } from "react";

// An album fills the frame it is shown in: the grid spans the browser edge to
// edge (the CSS pulls it out of the page gutter), and its rows take up whatever
// height the window has left.
//
// Two things choose the column count: the artist's ceiling (data-max-cols), and
// the window. The width fixes a frame's width and the crop fixes its shape, so
// the count is the one free variable - and the only thing that decides how tall
// an album runs. Within the ceiling, the count whose rows come nearest the
// window is chosen, and those rows then stretch the rest of the way, so a sheet
// comes out the size of the frame rather than whatever its crop happens to make
// it.
//
// The numbers come from the browser (viewport height, element widths), which
// the server render cannot know, so the server sends the CSS fallback and this
// replaces it as soon as the grid is in the document.

// The frame crop: 3 across, 2 down. Every cell keeps it, so an album reads as a
// contact sheet rather than as differently shaped pictures.
const CROP = 2 / 3;

// That crop as a ratio of width to height, and how far a stretched frame may sit
// from it before it stops looking like a photograph. The reference's own covers
// are 5:4 (1.25) and its archive never stretches a photograph to fill a frame -
// it is a uniform grid that scrolls. 1.9 is the widest a stretched frame may go
// and still read as the photograph it is; past that it is a letterbox strip, and
// the sheet keeps the crop and runs on instead.
const TARGET_RATIO = 1 / CROP;
const MIN_RATIO = 1.1;
const MAX_RATIO = 1.9;

// A frame never gets narrower than this, so a column count that would take it
// below this is not offered at all - which is what stops a narrow window from
// turning a sheet into confetti ...
const MIN_CELL = 110;

// ... nor shorter than this once its rows have been stretched, which is the same
// floor read the other way.
const MIN_IMAGE_HEIGHT = 60;

// The 1px hairlines between cells are the grid's gap, so they count.
const GAP = 1;

type Layout = {
  cols: number;
  // True when the rows stretch to fill the window, false when the sheet keeps
  // the crop and runs past it instead.
  fill: boolean;
};

type Candidate = { cols: number; rows: number; natural: number };

/** What this count makes with no stretching: the crop's own height. */
function naturalHeight(
  cols: number,
  rows: number,
  width: number,
  chrome: number,
  inset: number,
): number {
  const cell = (width - (cols - 1) * GAP) / cols;
  return rows * (chrome + (cell - inset) * CROP) + (rows - 1) * GAP;
}

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
  // A single column fills a narrow frame exactly, by standing one narrow strip
  // of photographs in the middle of it. That is not a contact sheet, so more
  // than one photograph always gets at least two columns.
  const min = count > 1 ? 2 : 1;

  let filled: Candidate | null = null;
  let filledScore = Infinity;
  let nearest: Candidate | null = null;
  let nearestDelta = Infinity;

  for (let cols = min; cols <= max; cols++) {
    // The cell that makes this many columns span the sheet exactly. Solving from
    // the width is what puts the album edge to edge; the count then decides how
    // many rows that makes, and so how tall the album runs.
    const cell = (width - (cols - 1) * GAP) / cols;
    if (cell < MIN_CELL) continue;

    // A last row less than half full reads as a mistake rather than a sheet, so
    // a count that leaves one is not offered at all.
    const lastRow = count % cols;
    if (lastRow !== 0 && lastRow * 2 < cols) continue;

    const rows = Math.ceil(count / cols);
    const natural = naturalHeight(cols, rows, width, chrome, inset);

    // What this count makes with no stretching at all, for a sheet that cannot
    // fill the window: whichever comes nearest it. Nearest rather than tallest,
    // because nothing is being filled here - a count that only fits by making
    // the frames smaller has given up legibility for a fit that never happened.
    const delta = Math.abs(natural - available);
    if (delta < nearestDelta) {
      nearestDelta = delta;
      nearest = { cols, rows, natural };
    }

    // The same rows filling the window: a cell is not all photograph, since the
    // frame's own padding and caption take their share of it first.
    const imageHeight = (available - (rows - 1) * GAP) / rows - chrome;
    if (imageHeight < MIN_IMAGE_HEIGHT) continue;

    const ratio = (cell - inset) / imageHeight;
    if (ratio < MIN_RATIO || ratio > MAX_RATIO) continue;

    // The fill that lands nearest the crop wins. Iterating upwards gives a tie
    // to the sparser sheet, and with it the larger frames.
    const score = Math.abs(Math.log(ratio / TARGET_RATIO));
    if (score < filledScore) {
      filledScore = score;
      filled = { cols, rows, natural };
    }
  }

  if (filled) return { cols: filled.cols, fill: true };
  if (nearest) return { cols: nearest.cols, fill: false };
  return null;
}

function fitOne(grid: HTMLElement): void {
  const count = grid.childElementCount;
  const sheet = grid.closest<HTMLElement>(".sheet");
  if (!count || !sheet) return;

  // Everything in a cell that isn't the photograph (the frame's padding and its
  // caption), and how much narrower the photograph is than the cell it sits in.
  // Measured rather than assumed, so both follow the padding and the type as
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
  // How much height the sheet has left for its frames: from just under its own
  // heading down to the bottom edge of the window, which is the frame a
  // full-height sheet fills.
  const available =
    window.innerHeight -
    parseFloat(style.paddingTop) -
    (head?.getBoundingClientRect().height ?? 0) -
    (credit?.getBoundingClientRect().height ?? 0);

  // The width the album spans, which is the whole browser: the grid's own
  // negative margins cancel the sheet's gutter, so its content box is the
  // edge-to-edge width. Read from the grid rather than the sheet, and stable
  // between fits, because a block's width comes from its container and not from
  // the column count - there is nothing here for an earlier fit to report back.
  const width = grid.clientWidth;
  if (width <= 0 || available <= 0) return;

  // The artist's ceiling, read off the element so a grid carries its own limit
  // wherever it is rendered. Absent, or unparseable, means no ceiling.
  const cap = Number(grid.dataset.maxCols) || null;

  const layout = bestLayout(count, width, available, chrome, inset, cap);
  if (!layout) {
    // Nothing legible fits this frame - the frames would come out narrower than
    // a thumbnail - so hand the album back to the plain width-driven grid.
    grid.style.removeProperty("--cols");
    grid.style.removeProperty("--fit-height");
    delete grid.dataset.fit;
    delete grid.dataset.fill;
    return;
  }

  grid.style.setProperty("--cols", String(layout.cols));
  grid.dataset.fit = "on";
  if (layout.fill) {
    grid.style.setProperty("--fit-height", `${available}px`);
    grid.dataset.fill = "on";
  } else {
    grid.style.removeProperty("--fit-height");
    delete grid.dataset.fill;
  }
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
