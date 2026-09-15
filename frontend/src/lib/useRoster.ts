"use client";

import { useEffect, useState } from "react";
import { API_BASE } from "@/lib/api";

export type RosterArtist = {
  slug: string;
  displayName: string;
  tagline: string;
  location: string;
};

// Everyone with a profile, front-page artist first. Shared by every page that
// points a visitor at the rest of the roster, so they can't drift apart about
// who's on the site.
export function useRoster(): RosterArtist[] {
  const [roster, setRoster] = useState<RosterArtist[]>([]);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const response = await fetch(`${API_BASE}/api/artists`);
        if (!response.ok) return;
        const data = await response.json();
        if (!cancelled) setRoster(data.artists as RosterArtist[]);
      } catch {
        // The roster is a convenience; the page works without it.
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  return roster;
}
