"use client";

import { useCallback, useState } from "react";
import { API_BASE, LOGIN_PATH } from "@/lib/api";
import { useSiteCopy } from "@/lib/useSiteCopy";
import { usePortfolio, type Frame } from "@/lib/usePortfolio";
import { AlbumSheet, SheetNote } from "@/components/AlbumSheet";
import { PageTitle } from "@/components/PageTitle";
import { PhotoViewer } from "@/components/PhotoViewer";
import { SiteBar } from "@/components/SiteBar";

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
  const { sections, frames, signedIn, failed, loading, retry } = usePortfolio();
  const [viewing, setViewing] = useState<number | null>(null);
  // The path being fetched right now, so only that control shows progress.
  const [busy, setBusy] = useState<string | null>(null);
  const copy = useSiteCopy();

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
        ) : loading ? (
          <SheetNote>Loading the gallery…</SheetNote>
        ) : sections.length === 0 ? (
          <SheetNote>No albums are published yet.</SheetNote>
        ) : (
          sections.map(({ album, frames: albumFrames }) => (
            <AlbumSheet
              key={album.id}
              album={album}
              frames={albumFrames}
              heading="h1"
              onOpen={setViewing}
              // The tier is stated, and the action only appears when this
              // visitor is entitled - the server refuses the rest anyway.
              actions={
                <span className="sheet-actions">
                  <span className="tier">{album.access}</span>
                  {album.canDownload ? (
                    <button
                      type="button"
                      className="site-button"
                      disabled={busy !== null}
                      onClick={() =>
                        void saveAs(album.downloadUrl, `${album.slug}.zip`)
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
              }
              frameAction={(frame: Frame) =>
                album.canDownload ? (
                  <button
                    type="button"
                    className="frame-action"
                    disabled={busy !== null}
                    onClick={() =>
                      void saveAs(frame.downloadUrl, `photo-${frame.id}`)
                    }
                  >
                    {busy === frame.downloadUrl ? "…" : "Download"}
                  </button>
                ) : (
                  <span className="frame-locked" aria-hidden="true">
                    Locked
                  </span>
                )
              }
            />
          ))
        )}
      </main>

      {!signedIn && !loading && sections.length > 0 ? (
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
          onClose={() => setViewing(null)}
          onIndexChange={setViewing}
          onDownload={(item) => {
            if (item.downloadUrl) {
              void saveAs(item.downloadUrl, `photo-${item.id}`);
            }
          }}
          busy={busy !== null}
        />
      ) : null}
    </div>
  );
}
