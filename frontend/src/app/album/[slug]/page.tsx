"use client";

import { use, useState } from "react";
import { CLIENT_ACCESS_LABEL, SITE } from "@/lib/site";
import { useAlbum, type Frame } from "@/lib/usePortfolio";
import { useDownload } from "@/lib/useDownload";
import { AlbumSheet, SheetNote } from "@/components/AlbumSheet";
import { BackToTop } from "@/components/BackToTop";
import { PageTitle } from "@/components/PageTitle";
import { PhotoViewer } from "@/components/PhotoViewer";
import { SiteBar } from "@/components/SiteBar";
import { SiteFooter } from "@/components/SiteFooter";

/**
 * One album, and the only page that shows photographs.
 *
 * The index pages send a visitor here rather than inlining every frame, so this
 * is where the sheet is sized to the window, where the viewer opens, and where
 * an album is downloaded.
 */
export default function AlbumPage({
  params,
}: {
  params: Promise<{ slug: string }>;
}) {
  // Next hands route params to a client page as a promise.
  const { slug } = use(params);

  const { album, frames, failed, missing, loading, retry } = useAlbum(slug);
  const [viewing, setViewing] = useState<number | null>(null);
  const { busy, isBusy, saveAs } = useDownload();

  return (
    <div className="site" data-artist-theme={album?.artistTheme ?? undefined}>
      <PageTitle
        title={
          album
            ? `${album.title} — ${album.artistName ?? SITE.name} | ${SITE.name}`
            : SITE.name
        }
      />
      <SiteBar
        name={album?.artistName ?? SITE.name}
        role={album?.credit ?? SITE.role}
        links={[
          { href: "/#work", label: "All work" },
          { href: "/gallery", label: CLIENT_ACCESS_LABEL },
        ]}
      />

      {missing ? (
        <SheetNote>
          No album at that address. <a href="/#work">See all work</a>.
        </SheetNote>
      ) : failed ? (
        <SheetNote>
          This album couldn’t be loaded.{" "}
          <button type="button" className="frame-action" onClick={retry}>
            Try again
          </button>
        </SheetNote>
      ) : loading || !album ? (
        <SheetNote>Loading the album…</SheetNote>
      ) : (
        <main>
          <AlbumSheet
            album={album}
            frames={frames}
            heading="h1"
            onOpen={setViewing}
            // The tier is stated, and the action only appears when this visitor
            // is entitled - the server refuses the rest anyway.
            actions={
              <span className="sheet-actions">
                <a className="header-link" href="/#work">
                  ← All work
                </a>
                <span className="tier">{album.access}</span>
                {album.canDownload ? (
                  <button
                    type="button"
                    className="site-button"
                    disabled={isBusy}
                    onClick={() =>
                      void saveAs(album.downloadUrl, `${album.slug}.zip`)
                    }
                  >
                    {busy === album.downloadUrl
                      ? "Preparing…"
                      : `Download all ${frames.length}`}
                  </button>
                ) : (
                  <span className="tier-note">
                    {album.access === "premium"
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
                  disabled={isBusy}
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
        </main>
      )}

      <SiteFooter
        name={album?.artistName ?? SITE.name}
        role={album?.credit ?? SITE.role}
        email={album?.artistEmail ?? SITE.email}
        instagram={album?.artistInstagram}
        showSignIn
      />

      {viewing !== null ? (
        <PhotoViewer
          items={frames}
          index={viewing}
          onClose={() => setViewing(null)}
          onIndexChange={setViewing}
          onDownload={(item) => {
            if (item.downloadUrl)
              void saveAs(item.downloadUrl, `photo-${item.id}`);
          }}
          busy={isBusy}
        />
      ) : null}

      <BackToTop />
    </div>
  );
}
