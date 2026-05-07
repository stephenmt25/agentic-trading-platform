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
