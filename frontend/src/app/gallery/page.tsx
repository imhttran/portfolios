"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { API_BASE, LOGIN_PATH, renewSessionFrom } from "@/lib/api";
import { creditFor } from "@/lib/credits";
import { useSiteCopy } from "@/lib/useSiteCopy";
import { fitGrid, useFittedGrids } from "@/lib/useFittedGrids";
import { PhotoViewer } from "@/components/PhotoViewer";
import { PageTitle } from "@/components/PageTitle";
import { SignOut } from "@/components/SignOut";
import { ThemeToggle } from "@/components/ThemeToggle";

type Album = {
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
  canDownload: boolean;
  downloadUrl: string;
};

type Photo = {
  id: number;
  title: string | null;
  previewUrl: string;
  downloadUrl: string;
};

type Loaded = { album: Album; photos: Photo[] };

// The backend already names every download it serves, so take the name from
// its Content-Disposition rather than re-deriving it here - a hardcoded
// ".png" would mislabel every JPEG that isn't a placeholder. Same-origin, so
// the header is readable.
function filenameFrom(response: Response, fallback: string): string {
  const header = response.headers.get("content-disposition") ?? "";
  const match = /filename="?([^";]+)"?/.exec(header);
  return match ? match[1] : fallback;
}

export default function GalleryPage() {
  const [albums, setAlbums] = useState<Loaded[] | null>(null);
  const [failed, setFailed] = useState(false);
  const [busy, setBusy] = useState<string | null>(null);
  const [viewing, setViewing] = useState<number | null>(null);
  // Read once on mount: the download buttons only care whether a session
  // exists, and the header only cares whether to offer Sign in or Dashboard.
  const [signedIn, setSignedIn] = useState(false);
  const copy = useSiteCopy();

  useEffect(() => {
    // The album endpoints are public but answer differently for a signed-in
    // visitor - canDownload is computed per caller - so this page has to send
    // its token, or a subscriber sees everything as locked.
    const token = localStorage.getItem("auth_token");
    setSignedIn(Boolean(token));
    const headers = token ? { Authorization: `Bearer ${token}` } : undefined;

    (async () => {
      try {
        const response = await fetch(`${API_BASE}/api/media/albums`, {
          headers,
        });
        renewSessionFrom(response);
        const data = await response.json();
        if (!response.ok) throw new Error(data.message);

        // One detail request per album: small at this size, and it keeps the
        // listing endpoint from inlining every photo in the library.
        const loaded = await Promise.all(
          (data.albums as Album[]).map(async (album) => {
            const detail = await fetch(
              `${API_BASE}/api/media/albums/${album.slug}`,
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
        setAlbums(loaded);
      } catch {
        setFailed(true);
      }
    })();
  }, []);

  // Downloads carry the session token, so they can't be plain links: fetch the
  // bytes, then hand the blob to a synthetic anchor click. No token means no
  // download, so send the visitor to sign in first.
  const saveAs = useCallback(async (path: string, fallbackName: string) => {
    const token = localStorage.getItem("auth_token");
    if (!token) {
      window.location.href = LOGIN_PATH;
      return;
    }

    setBusy(path);
    try {
      const response = await fetch(`${API_BASE}${path}`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!response.ok) {
        const body = await response.json().catch(() => null);
        alert(`Error: ${body?.message ?? response.statusText}`);
        return;
      }
      const blob = await response.blob();
      const url = URL.createObjectURL(blob);
      const anchor = document.createElement("a");
      anchor.href = url;
      anchor.download = filenameFrom(response, fallbackName);
      document.body.appendChild(anchor);
      anchor.click();
      anchor.remove();
      URL.revokeObjectURL(url);
    } catch {
      alert("Connection error. Is the backend running?");
    } finally {
      setBusy(null);
    }
  }, []);

  const closeViewer = useCallback(() => setViewing(null), []);
  const changeViewer = useCallback((next: number) => setViewing(next), []);

  // Same flat-with-offsets shape as the public page, so the viewer's sequence
  // runs continuously across albums here too.
  const sections = useMemo(() => {
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
  }, [albums]);

  // Size every album to the frame it is shown in.
  useFittedGrids(albums);

  const frames = useMemo(() => sections.flatMap((s) => s.frames), [sections]);

  const requestDownload = useCallback(
    (photo: { id: number; downloadUrl?: string }) => {
      if (photo.downloadUrl)
        void saveAs(photo.downloadUrl, `photo-${photo.id}`);
    },
    [saveAs],
  );

  return (
    <div className="site">
      <PageTitle title={`Client access | ${copy.name}`} />
      <header className="site-bar">
        <a className="site-identity" href="/">
          <span className="site-name">{copy.name}</span>
          <span className="site-role">{copy.role}</span>
        </a>
        <nav className="site-nav">
          <a href="/#work">Work</a>
          <a href="/#about">About</a>
          {signedIn ? (
            <a href="/dashboard">Dashboard</a>
          ) : (
            <a href={LOGIN_PATH}>Sign in</a>
          )}
          <ThemeToggle />
          <SignOut />
        </nav>
      </header>

      <main>
        {failed ? (
          <section className="sheet">
            <p className="sheet-note">The gallery couldn’t be loaded.</p>
          </section>
        ) : albums === null ? (
          <section className="sheet">
            <p className="sheet-note">Loading the gallery…</p>
          </section>
        ) : albums.length === 0 ? (
          <section className="sheet">
            <p className="sheet-note">No albums are published yet.</p>
          </section>
        ) : (
          sections.map(({ album, frames: albumFrames }) => (
            <section className="sheet" key={album.id}>
              <div className="sheet-head">
                <h1>{album.title}</h1>
                {/* The tier is stated, and the action only appears when this
                    visitor is entitled - the server refuses the rest anyway. */}
                <span className="sheet-actions">
                  <span className="tier">{album.access}</span>
                  {album.canDownload ? (
                    <button
                      type="button"
                      className="site-button"
                      disabled={busy !== null}
                      onClick={() =>
                        saveAs(album.downloadUrl, `${album.slug}.zip`)
                      }
                    >
                      {busy === album.downloadUrl
                        ? "Preparing…"
                        : `Download all ${albumFrames.length}`}
                    </button>
                  ) : (
                    <span className="tier-note">
                      {!signedIn
                        ? "Sign in to download"
                        : album.access === "premium"
                          ? `Premium subscription to ${album.artistName ?? "this artist"} required`
                          : `Subscribe to ${album.artistName ?? "this artist"} to download`}
                    </span>
                  )}
                </span>
              </div>
              {/* Whose album this is matters here: with more than one artist
                  on the site, the subscribe prompt has to name them. */}
              <p className="sheet-credit">
                {album.artistSlug ? (
                  <a href={`/artist/${album.artistSlug}`}>
                    {album.artistName ?? album.artistSlug}
                  </a>
                ) : null}
                {creditFor(album) ? <> · {creditFor(album)}</> : null}
              </p>

              <div className="sheet-grid" ref={fitGrid}>
                {albumFrames.map((frame) => (
                  <figure className="frame" key={frame.id}>
                    <button
                      type="button"
                      className="frame-open"
                      onClick={() => setViewing(frame.index)}
                      aria-label={`View ${frame.title ?? "this frame"} larger`}
                    >
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
                      <span
                        className="frame-title"
                        title={frame.title ?? undefined}
                      >
                        {frame.title ?? "Untitled"}
                      </span>
                      {album.canDownload ? (
                        <button
                          type="button"
                          className="frame-action"
                          disabled={busy !== null}
                          onClick={() =>
                            saveAs(frame.downloadUrl, `photo-${frame.id}`)
                          }
                        >
                          {busy === frame.downloadUrl ? "…" : "Download"}
                        </button>
                      ) : (
                        <span className="frame-locked" aria-hidden="true">
                          Locked
                        </span>
                      )}
                    </figcaption>
                  </figure>
                ))}
              </div>
            </section>
          ))
        )}
      </main>

      {!signedIn && albums && albums.length > 0 ? (
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

      {viewing !== null ? (
        <PhotoViewer
          items={frames}
          index={viewing}
          onClose={closeViewer}
          onIndexChange={changeViewer}
          onDownload={requestDownload}
          busy={busy !== null}
        />
      ) : null}
    </div>
  );
}
