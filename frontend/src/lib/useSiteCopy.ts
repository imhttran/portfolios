"use client";

import { useEffect, useState } from "react";
import { API_BASE } from "./api";
import { SITE, copyFrom, type SiteCopy } from "./site";

// The public copy for a page to render.
//
// Starts at the built-in defaults so the page paints immediately and still
// works if the API is unreachable, then swaps in whatever the artist
// saved in /studio. Shared so the portfolio and the client area can never
// disagree about the site's name.
export function useSiteCopy(): SiteCopy {
  const [copy, setCopy] = useState<SiteCopy>(SITE);

  useEffect(() => {
    let cancelled = false;

    (async () => {
      try {
        const response = await fetch(`${API_BASE}/api/artist/profile`);
        if (!response.ok) return;
        const data = await response.json();
        if (!cancelled) setCopy(copyFrom(data.profile));
      } catch {
        // The defaults already on screen are the fallback; nothing to do.
      }
    })();

    return () => {
      cancelled = true;
    };
  }, []);

  return copy;
}
