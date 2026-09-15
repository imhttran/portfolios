"use client";

import { useCallback, useState } from "react";
import { API_BASE, LOGIN_PATH } from "./api";

// Downloads carry the session token, so they can't be plain links: fetch the
// bytes, then hand the blob to a synthetic anchor click. No token means no
// download, so send the visitor to sign in first.
//
// Extracted because three surfaces download now - the album's own page for both
// an album and a single frame, and the viewer's button bar - and they must not
// disagree about how a token is sent or a filename is read.

/** The backend names every download it serves; re-deriving that would drift. */
function filenameFrom(response: Response, fallback: string): string {
  const header = response.headers.get("content-disposition") ?? "";
  const match = /filename="?([^";]+)"?/.exec(header);
  return match ? match[1] : fallback;
}

export type Downloader = {
  /** The path being fetched right now, so only that control shows progress. */
  busy: string | null;
  isBusy: boolean;
  saveAs: (path: string, fallbackName: string) => Promise<void>;
};

export function useDownload(): Downloader {
  const [busy, setBusy] = useState<string | null>(null);

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

  return { busy, isBusy: busy !== null, saveAs };
}
