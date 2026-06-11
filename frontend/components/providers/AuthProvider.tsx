"use client";

import { SessionProvider, useSession } from "next-auth/react";
import { useEffect } from "react";
import { useAuthStore } from "@/lib/stores/authStore";
import { useConnectionStore } from "@/lib/stores/connectionStore";
import { wsClient } from "@/lib/ws/client";

/**
 * Syncs the NextAuth session into authStore and owns the realtime
 * lifecycle (WebSocket + backend health polling).
 *
 * FE-W0 hoisted the lifecycle here from AppShell so the socket initiates
 * in the same effect that writes the JWT — warm before the first page
 * paint instead of one render later. The effect is keyed on the access
 * token: rotation runs the cleanup (disconnect) and reconnects with the
 * fresh JWT, matching the prior AppShell semantics.
 */
function SessionSync({ children }: { children: React.ReactNode }) {
  const { data: session, status } = useSession();
  const setSession = useAuthStore((s) => s.setSession);
  const logout = useAuthStore((s) => s.logout);

  const accessToken = (session?.accessToken as string | undefined) ?? null;
  const userName = session?.user?.name ?? session?.user?.email ?? null;

  useEffect(() => {
    if (status === "loading") return;

    if (!accessToken) {
      logout();
      wsClient.disconnect();
      useConnectionStore.getState().stopHealthPolling();
      return;
    }

    // Zustand set() is synchronous — wsClient.connect() below reads the
    // fresh JWT from the store in the same tick.
    setSession(accessToken, userName);
    wsClient.connect();
    useConnectionStore.getState().startHealthPolling();

    return () => {
      // Runs on token rotation (effect re-runs and reconnects with the
      // fresh JWT) and on unmount.
      wsClient.disconnect();
      useConnectionStore.getState().stopHealthPolling();
    };
  }, [accessToken, userName, status, setSession, logout]);

  return <>{children}</>;
}

export function AuthProvider({ children }: { children: React.ReactNode }) {
  return (
    <SessionProvider>
      <SessionSync>{children}</SessionSync>
    </SessionProvider>
  );
}
