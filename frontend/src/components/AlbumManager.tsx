"use client";

import { useCallback, useEffect, useState, type FormEvent } from "react";
import { API_BASE, callApi } from "@/lib/api";

type ManagedAlbum = {
  id: number;
  slug: string;
  title: string;
  description: string | null;
  credit: string | null;
  access: string;
  isPublished: boolean;
  photoCount: number;
};

type Rejection = { name: string; reason: string };

const TIERS = ["free", "paid", "premium"] as const;

// The artist's own album work: make an album in a bucket, add photos to it,
// move it between buckets, publish or hide it.
export function AlbumManager({ token }: { token: string }) {
  const [albums, setAlbums] = useState<ManagedAlbum[] | null>(null);
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState<string | null>(null);
  const [rejections, setRejections] = useState<Rejection[]>([]);
  // Which album is currently receiving files, so only that row shows progress.
  const [uploadingTo, setUploadingTo] = useState<string | null>(null);
  const [failed, setFailed] = useState(false);

  const load = useCallback(async () => {
    try {
      const response = await fetch(`${API_BASE}/api/manage/albums`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      const data = await response.json();
      if (!response.ok) throw new Error(data.message);
      setAlbums(data.albums as ManagedAlbum[]);
      setFailed(false);
    } catch {
      setFailed(true);
    }
  }, [token]);

  useEffect(() => {
    void load();
  }, [load]);

  const replace = (album: ManagedAlbum) =>
    setAlbums((current) =>
      (current ?? []).map((a) => (a.slug === album.slug ? album : a)),
    );

  const handleCreate = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const form = event.currentTarget;
    const data = new FormData(form);
    setBusy(true);
    setNotice(null);
    setRejections([]);

    const result = await callApi<{ album: ManagedAlbum; message: string }>(
      token,
      "/api/manage/albums",
      "POST",
      {
        title: String(data.get("title") ?? ""),
        access: String(data.get("access") ?? "free"),
        isPublished: data.get("published") === "on",
      },
    );
    setBusy(false);
    if (!result) {
      setNotice("Could not create the album.");
      return;
    }
    form.reset();
    setAlbums((current) => [...(current ?? []), result.album]);
    setNotice(result.message);
  };

  // Multipart, so no callApi: the browser sets the boundary, and the reply is a
  // per-file report rather than a single message.
  const handleUpload = async (album: ManagedAlbum, files: FileList | null) => {
    if (!files || files.length === 0) return;

    const body = new FormData();
    for (const file of Array.from(files)) body.append("files", file);

    setUploadingTo(album.slug);
    setNotice(null);
    setRejections([]);
    try {
      const response = await fetch(
        `${API_BASE}/api/manage/albums/${album.slug}/photos`,
        {
          method: "POST",
          headers: { Authorization: `Bearer ${token}` },
          body,
        },
      );
      const result = await response.json();
      if (result.album) replace(result.album as ManagedAlbum);
      setNotice(result.message ?? null);
      setRejections((result.rejected as Rejection[]) ?? []);
      if (!response.ok && !result.message) {
        setNotice("The upload failed.");
      }
    } catch {
      setNotice("Connection error while uploading. Is the backend running?");
    } finally {
      setUploadingTo(null);
    }
  };

  const handlePatch = async (
    album: ManagedAlbum,
    patch: Record<string, unknown>,
  ) => {
    const result = await callApi<{ album: ManagedAlbum }>(
      token,
      `/api/manage/albums/${album.slug}`,
      "PATCH",
      patch,
      false,
    );
    if (result) replace(result.album);
    else setNotice("Could not save that change.");
  };

  // Title, credit and description: the copy that appears on the album. A blank
  // field clears it, which is how you take a credit off work that is your own.
  const handleSaveCopy = async (
    event: FormEvent<HTMLFormElement>,
    album: ManagedAlbum,
  ) => {
    event.preventDefault();
    const data = new FormData(event.currentTarget);
    setNotice(null);
    await handlePatch(album, {
      title: String(data.get("title") ?? ""),
      credit: String(data.get("credit") ?? ""),
      description: String(data.get("description") ?? ""),
    });
    setNotice(`Saved "${String(data.get("title") ?? album.title)}".`);
  };

  const handleDelete = async (album: ManagedAlbum) => {
    const warning =
      album.photoCount > 0
        ? `Delete "${album.title}" and its ${album.photoCount} photo(s)? The files go too, and this can't be undone.`
        : `Delete "${album.title}"?`;
    if (!window.confirm(warning)) return;

    const result = await callApi<{ message: string }>(
      token,
      `/api/manage/albums/${album.slug}`,
      "DELETE",
      undefined,
      false,
    );
    if (!result) {
      setNotice("Could not delete that album.");
      return;
    }
    setAlbums((current) =>
      (current ?? []).filter((a) => a.slug !== album.slug),
    );
    setNotice(result.message);
    setRejections([]);
  };

  return (
    <fieldset className="studio-albums">
      <legend className="mono">Albums</legend>

      {failed ? (
        <p className="sheet-note">Could not load your albums.</p>
      ) : albums === null ? (
        <p className="sheet-note">Loading your albums...</p>
      ) : albums.length === 0 ? (
        <p className="sheet-note">
          No albums yet. Make one below, then add photos to it.
        </p>
      ) : (
        <ul className="album-list">
          {albums.map((album) => (
            <li className="album-row" key={album.id}>
              <div className="album-main">
                <span className="album-title">{album.title}</span>
                <span className="album-meta">
                  {album.photoCount}{" "}
                  {album.photoCount === 1 ? "photo" : "photos"} ·{" "}
                  {album.isPublished ? "published" : "hidden"} · /{album.slug}
                </span>
              </div>

              <div className="album-actions">
                <label className="album-field">
                  <span className="visually-hidden">
                    Bucket for {album.title}
                  </span>
                  <select
                    value={album.access}
                    onChange={(event) =>
                      handlePatch(album, { access: event.target.value })
                    }
                  >
                    {TIERS.map((tier) => (
                      <option key={tier} value={tier}>
                        {tier}
                      </option>
                    ))}
                  </select>
                </label>

                <button
                  type="button"
                  className="album-button"
                  onClick={() =>
                    handlePatch(album, { isPublished: !album.isPublished })
                  }
                >
                  {album.isPublished ? "Hide" : "Publish"}
                </button>

                <label className="album-button album-upload">
                  <input
                    className="visually-hidden"
                    type="file"
                    multiple
                    accept="image/jpeg,image/png,image/webp,image/tiff"
                    disabled={uploadingTo !== null}
                    onChange={(event) => {
                      void handleUpload(album, event.target.files);
                      // Let the same file be picked again later.
                      event.target.value = "";
                    }}
                  />
                  {uploadingTo === album.slug ? "Uploading..." : "Add photos"}
                </label>

                <button
                  type="button"
                  className="album-button album-button--danger"
                  onClick={() => void handleDelete(album)}
                >
                  Delete
                </button>
              </div>

              {/* <details> rather than an inline form: the copy is edited
                  occasionally, and the row stays one line otherwise. */}
              <details className="album-edit">
                <summary className="album-edit-toggle">Edit copy</summary>
                <form
                  className="album-edit-form"
                  onSubmit={(event) => void handleSaveCopy(event, album)}
                >
                  <div className="input-group">
                    <label htmlFor={`title-${album.id}`}>Title</label>
                    <input
                      id={`title-${album.id}`}
                      name="title"
                      defaultValue={album.title}
                      required
                    />
                  </div>

                  <div className="input-group">
                    <label htmlFor={`credit-${album.id}`}>Credit</label>
                    <input
                      id={`credit-${album.id}`}
                      name="credit"
                      defaultValue={album.credit ?? ""}
                      placeholder="Blank for your own work"
                    />
                    <p className="field-hint">
                      For work shot by someone else. Your own albums are already
                      credited to you, so a credit naming you is not shown.
                    </p>
                  </div>

                  <div className="input-group">
                    <label htmlFor={`description-${album.id}`}>
                      Description
                    </label>
                    <textarea
                      id={`description-${album.id}`}
                      name="description"
                      rows={3}
                      defaultValue={album.description ?? ""}
                    />
                    <p className="field-hint">
                      Blank fields are cleared. The URL keeps /{album.slug},
                      whatever the title becomes.
                    </p>
                  </div>

                  <div className="studio-actions">
                    <button type="submit" className="login-button">
                      Save
                    </button>
                  </div>
                </form>
              </details>
            </li>
          ))}
        </ul>
      )}

      {notice ? <p className="studio-notice">{notice}</p> : null}
      {rejections.length > 0 ? (
        <ul className="studio-rejections">
          {rejections.map((r) => (
            <li key={r.name}>
              <span className="mono">{r.name}</span> — {r.reason}
            </li>
          ))}
        </ul>
      ) : null}

      <form className="studio-new-album" onSubmit={handleCreate}>
        <div className="input-group">
          <label htmlFor="new-album-title">New album</label>
          <input
            id="new-album-title"
            name="title"
            placeholder="Title"
            required
          />
        </div>

        <div className="input-group">
          <label htmlFor="new-album-access">Bucket</label>
          <select id="new-album-access" name="access" defaultValue="free">
            {TIERS.map((tier) => (
              <option key={tier} value={tier}>
                {tier}
              </option>
            ))}
          </select>
          <p className="field-hint">
            Free is downloadable by any registered user; paid and premium need a
            subscription at that level.
          </p>
        </div>

        <label className="studio-check">
          <input type="checkbox" name="published" />
          <span>Publish it now</span>
        </label>

        <div className="studio-actions">
          <button type="submit" className="login-button" disabled={busy}>
            {busy ? "Creating..." : "Create album"}
          </button>
        </div>
      </form>
    </fieldset>
  );
}
