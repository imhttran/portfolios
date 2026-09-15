"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { API_BASE, renewSessionFrom } from "./api";
import { useFittedGrids } from "./useFittedGrids";

// Everything the portfolio pages need to show work.
//
// The site is an index of albums and, behind a click, the album itself - the
// shape the design reference uses, and the only one where a page stays readable:
// inlining every photograph of every album put /gallery at 29 screens. So there
// are two loaders rather than one, and the split is what keeps an index page
// from paying for photographs nothing on it shows.

export type Artist = {
  slug: string;
  displayName: string;
  tagline: string;
  statement: string;
  bio: string;
  location: string;
  contactEmail: string;
  phone: string | null;
  instagram: string | null;
  // "dark" | "light" | "paper", or null for no theme of their own - in which
  // case their page follows the site's.
  theme: string | null;
};

export type Album = {
  id: number;
  slug: string;
  title: string;
  credit: string | null;
  description: string | null;
  // "free" | "paid" | "premium" - the tier, and whether this visitor may take
  // a copy.
  access: string;
  artistName: string | null;
  artistSlug: string | null;
  // That artist's ceiling on how many photographs across the sheet may get.
  // Null means the grid decides on its own.
  artistColumns: number | null;
  // "dark" | "light" | "paper", or null for none of their own. Carried on the
  // album so its page can wear the artist's theme without a second request.
  artistTheme: string | null;
  photoCount: number;
  // What an index tile shows for this album: its first photograph. Null for an
  // album with none imported yet.
  coverUrl: string | null;
  canDownload: boolean;
  downloadUrl: string;
};

export type Photo = {
  id: number;
  title: string | null;
  previewUrl: string;
  downloadUrl: string;
  width: number | null;
  height: number | null;
};

// A photograph with its place in the album's sequence and whose work it is.
export type Frame = Photo & { credit: string | null; index: number };

/**
 * Read ``auth_token`` and hand back the headers a portfolio request needs.
 *
 * These endpoints are public but answer differently for a signed-in visitor -
 * canDownload is computed per caller - so the token has to go with the request,
 * or a subscriber sees everything as locked.
 */
function authHeaders(): { token: string | null; headers?: HeadersInit } {
  const token = localStorage.getItem("auth_token");
  return {
    token,
    headers: token ? { Authorization: `Bearer ${token}` } : undefined,
  };
}

type IndexState = {
  artist: Artist | null;
  albums: Album[] | null;
  signedIn: boolean;
  failed: boolean;
  missing: boolean;
  attempt: number;
};

const EMPTY_INDEX: IndexState = {
  artist: null,
  albums: null,
  signedIn: false,
  failed: false,
  missing: false,
  attempt: 0,
};

/**
 * The published albums, and at ``/api/artists/<slug>`` that artist's public copy
 * with them. No photographs: this is what an index page renders.
 */
export function useAlbumIndex(artistSlug?: string) {
  const [state, setState] = useState<IndexState>(EMPTY_INDEX);

  useEffect(() => {
    let cancelled = false;
    setState((s) => ({ ...s, failed: false, missing: false }));

    (async () => {
      const { token, headers } = authHeaders();
      setState((s) => ({ ...s, signedIn: Boolean(token) }));

      try {
        const response = await fetch(
          artistSlug
            ? `${API_BASE}/api/artists/${artistSlug}`
            : `${API_BASE}/api/media/albums`,
          { headers },
        );
        if (response.status === 404) {
          if (!cancelled) setState((s) => ({ ...s, missing: true }));
          return;
        }
        renewSessionFrom(response);
        const data = await response.json();
        if (!response.ok) throw new Error(data.message);
        if (cancelled) return;

        setState((s) => ({
          ...s,
          artist: artistSlug ? (data.artist as Artist) : null,
          albums: data.albums as Album[],
        }));
      } catch {
        if (!cancelled) setState((s) => ({ ...s, failed: true }));
      }
    })();

    return () => {
      cancelled = true;
    };
  }, [artistSlug, state.attempt]);

  return {
    artist: state.artist,
    albums: state.albums,
    signedIn: state.signedIn,
    failed: state.failed,
    missing: state.missing,
    loading: state.albums === null && !state.failed && !state.missing,
    retry: useCallback(
      () => setState((s) => ({ ...s, attempt: s.attempt + 1 })),
      [],
    ),
  };
}

type AlbumState = {
  album: Album | null;
  photos: Photo[] | null;
  failed: boolean;
  missing: boolean;
  attempt: number;
};

const EMPTY_ALBUM: AlbumState = {
  album: null,
  photos: null,
  failed: false,
  missing: false,
  attempt: 0,
};

/**
 * One album with its photographs, in order, for the album's own page.
 *
 * Its own request rather than the index's: an index should never pay to load the
 * frames of every album it lists, and this one only ever pays for one.
 */
export function useAlbum(slug: string) {
  const [state, setState] = useState<AlbumState>(EMPTY_ALBUM);

  useEffect(() => {
    let cancelled = false;
    setState((s) => ({ ...s, failed: false, missing: false }));

    (async () => {
      const { headers } = authHeaders();
      try {
        const response = await fetch(`${API_BASE}/api/media/albums/${slug}`, {
          headers,
        });
        if (response.status === 404) {
          if (!cancelled) setState((s) => ({ ...s, missing: true }));
          return;
        }
        renewSessionFrom(response);
        const data = await response.json();
        if (!response.ok) throw new Error(data.message);
        if (cancelled) return;

        setState((s) => ({
          ...s,
          album: data.album as Album,
          photos: data.photos as Photo[],
        }));
      } catch {
        if (!cancelled) setState((s) => ({ ...s, failed: true }));
      }
    })();

    return () => {
      cancelled = true;
    };
  }, [slug, state.attempt]);

  // The album's photographs as a page-wide sequence: the viewer walks this, and
  // each frame keeps its position in it so the numbering matches the sheet.
  const frames: Frame[] = useMemo(
    () =>
      (state.photos ?? []).map((photo, index) => ({
        ...photo,
        credit: state.album?.credit ?? null,
        index,
      })),
    [state.photos, state.album],
  );

  // Size the album to the frame it is shown in.
  useFittedGrids(state.album);

  return {
    album: state.album,
    frames,
    failed: state.failed,
    missing: state.missing,
    loading: state.album === null && !state.failed && !state.missing,
    retry: useCallback(
      () => setState((s) => ({ ...s, attempt: s.attempt + 1 })),
      [],
    ),
  };
}
