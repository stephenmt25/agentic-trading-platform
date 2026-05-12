"use client";

import { createContext, useContext, useEffect, useMemo } from "react";
import { usePathname } from "next/navigation";

export type Mode = "hot" | "cool" | "calm";

const MODE_DEFAULT: Mode = "hot";

/**
 * Map a pathname to its mode per the target IA in
 * docs/design/02-information-architecture.md §1. Routes that don't
 * yet exist in the redesign IA fall through to the default. This
 * keeps existing (legacy) routes rendering in HOT until Phase 6
 * remaps them.
 */
function modeForPath(pathname: string | null): Mode {
  if (!pathname) return MODE_DEFAULT;
  if (pathname.startsWith("/hot")) return "hot";
  if (pathname === "/risk" || pathname.startsWith("/risk/")) return "hot";
  if (pathname.startsWith("/agents")) return "cool";
  if (pathname.startsWith("/canvas")) return "cool";
  if (pathname.startsWith("/backtests")) return "cool";
  if (pathname.startsWith("/settings")) return "calm";
  if (pathname === "/login") return "calm";
  return MODE_DEFAULT;
}

const ModeContext = createContext<Mode>(MODE_DEFAULT);

/**
 * Wire `data-mode` on `<html>` based on the current route. Per the
 * execution plan §4.2.
 *
 * Known limitation: SSR renders `<html data-mode="hot">` (the static
 * default in app/layout.tsx) regardless of route, so non-HOT routes
 * paint once with HOT tokens before this effect runs and swaps to
 * COOL/CALM. The fix is route-aware SSR via middleware that sets
 * `data-mode` on the response — defer until a flash regression is
 * observed in user testing.
 *
 * Per-page `<div data-mode="...">` overrides remain valid for
 * sectional overrides (e.g., a CALM modal inside a COOL surface).
 */
export function ModeProvider({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const mode = useMemo(() => modeForPath(pathname), [pathname]);

  useEffect(() => {
    document.documentElement.setAttribute("data-mode", mode);
  }, [mode]);

  return <ModeContext.Provider value={mode}>{children}</ModeContext.Provider>;
}

export function useMode(): Mode {
  return useContext(ModeContext);
}
