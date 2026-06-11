"use client";

import { useState } from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

/**
 * App-wide React Query provider (FE-W0). One client per browser session,
 * created lazily in state so re-renders never recreate it.
 *
 * Defaults tuned for a trading dashboard: short staleTime so reads stay
 * fresh, no focus refetch (surfaces poll explicitly via refetchInterval),
 * single retry so failures surface to the offline banner fast.
 *
 * Mounted in app/layout.tsx OUTSIDE AppShell — chrome components
 * (StatusPills, EngineTotalsPill) are query consumers too.
 */
export function QueryProvider({ children }: { children: React.ReactNode }) {
  const [client] = useState(
    () =>
      new QueryClient({
        defaultOptions: {
          queries: {
            staleTime: 5_000,
            gcTime: 300_000,
            refetchOnWindowFocus: false,
            retry: 1,
          },
        },
      })
  );

  return <QueryClientProvider client={client}>{children}</QueryClientProvider>;
}
