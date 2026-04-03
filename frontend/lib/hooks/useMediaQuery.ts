"use client";

import { useEffect, useState } from "react";

/**
 * Returns true when the viewport matches the given media query string.
 * Falls back to `false` during SSR / initial hydration.
 */
export function useMediaQuery(query: string): boolean {
  const [matches, setMatches] = useState(false);

  useEffect(() => {
    const mql = window.matchMedia(query);
    setMatches(mql.matches);
    const handler = (e: MediaQueryListEvent) => setMatches(e.matches);
    mql.addEventListener("change", handler);
    return () => mql.removeEventListener("change", handler);
  }, [query]);

  return matches;
}

/** Convenience: true when viewport is < 768px (Tailwind `md` breakpoint). */
export function useIsMobile(): boolean {
  return useMediaQuery("(max-width: 767px)");
}
