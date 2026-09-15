"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { API_BASE, renewSessionFrom } from "./api";
import { useFittedGrids } from "./useFittedGrids";

// Everything the three portfolio pages need to show work: the site's whole
// published library, or one artist's. Shared so the pages can't drift about how
// an album is loaded, which fields it carries, or how a visitor's entitlement
// is read - the three used to restate all of it.

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
  photoCount: number;
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

// A photograph with its place in the page-wide sequence and whose work it is.
export type Frame = Photo & { credit: string | null; index: number };

export type AlbumSection = { album: Album; frames: Frame[] };

type Loaded = { album: Album; photos: Photo[] };

/**
 * One flat list for the viewer, and each frame keeps its position in it, so the
 * sequence continues across albums instead of restarting per section.
 */
function toSections(albums: Loaded[] | null): AlbumSection[] {
  let offset = 0;
  return (albums ?? []).map(({ album, photos }) => {
    const start = offset;
    offset += photos.length;
    return {
      album,
      frames: photos.map((photo, i) => ({
        ...photo,
        credit: album.credit,
        index: start + i,
      })),
    };
  });
}

/**
 * The published work at ``/api/media/albums``, or at ``/api/artists/<slug>``
 * when a slug is given - which also returns that artist's public copy.
 */
export function usePortfolio(artistSlug?: string) {
  const [artist, setArtist] = useState<Artist | null>(null);
  const [albums, setAlbums] = useState<Loaded[] | null>(null);
  const [signedIn, setSignedIn] = useState(false);
  const [failed, setFailed] = useState(false);
  const [missing, setMissing] = useState(false);
  const [attempt, setAttempt] = useState(0);

  useEffect(() => {
    let cancelled = false;
    setFailed(false);
    setMissing(false);

    (async () => {
      // These endpoints are public but answer differently for a signed-in
      // visitor - canDownload is computed per caller - so the token has to go
      // with the request, or a subscriber sees everything as locked.
      const token = localStorage.getItem("auth_token");
      setSignedIn(Boolean(token));
      const headers = token ? { Authorization: `Bearer ${token}` } : undefined;

      try {
        const response = await fetch(
          artistSlug
            ? `${API_BASE}/api/artists/${artistSlug}`
            : `${API_BASE}/api/media/albums`,
          { headers },
        );
        if (response.status === 404) {
          if (!cancelled) setMissing(true);
          return;
        }
        renewSessionFrom(response);
        const data = await response.json();
        if (!response.ok) throw new Error(data.message);
        if (cancelled) return;

        if (artistSlug) setArtist(data.artist as Artist);

        // One detail request per album: small at this size, and it keeps the
        // listing endpoint from inlining every photo in the library.
        const loaded = await Promise.all(
          (data.albums as Album[]).map(async (stub) => {
            const detail = await fetch(
              `${API_BASE}/api/media/albums/${stub.slug}`,
              { headers },
            );
            renewSessionFrom(detail);
            const body = await detail.json();
            if (!detail.ok) throw new Error(body.message);
            return {
              album: body.album as Album,
              photos: body.photos as Photo[],
            };
          }),
        );
        if (!cancelled) setAlbums(loaded);
      } catch {
        if (!cancelled) setFailed(true);
      }
    })();

    return () => {
      cancelled = true;
    };
  }, [artistSlug, attempt]);

  const sections = useMemo(() => toSections(albums), [albums]);
  const frames = useMemo(() => sections.flatMap((s) => s.frames), [sections]);

  // Size every album to the frame it is shown in.
  useFittedGrids(albums);

  return {
    artist,
    sections,
    frames,
    signedIn,
    failed,
    missing,
    loading: albums === null && !failed && !missing,
    retry: useCallback(() => setAttempt((n) => n + 1), []),
  };
}
