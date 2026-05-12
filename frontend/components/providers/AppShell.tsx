"use client";

import { useSession } from "next-auth/react";
import { usePathname, useRouter } from "next/navigation";
import { useEffect } from "react";
import { wsClient } from "@/lib/ws/client";
import { useAuthStore } from "@/lib/stores/authStore";
import { useConnectionStore } from "@/lib/stores/connectionStore";
import { RedesignShell } from "@/components/shell/RedesignShell";

const PUBLIC_PATHS = ["/login"];

/**
 * Auth gate + WebSocket lifecycle wrapper. Visual chrome (rail, top bar,
 * banners, command palette) is delegated to RedesignShell on the
 * redesign branch. The legacy aside/header was removed at Phase 4.3 —
 * see frontend/DESIGN-SYSTEM.legacy.md for the prior implementation.
 */
export function AppShell({ children }: { children: React.ReactNode }) {
  const { data: session, status } = useSession();
  const pathname = usePathname();
  const router = useRouter();
  const jwt = useAuthStore((s) => s.jwt);

  const isPublic = PUBLIC_PATHS.some((p) => pathname.startsWith(p));

  // Connect/disconnect WebSocket and health polling based on auth state
  useEffect(() => {
    if (jwt) {
      wsClient.connect();
      useConnectionStore.getState().startHealthPolling();
    } else {
      wsClient.disconnect();
      useConnectionStore.getState().stopHealthPolling();
    }
    return () => {
      wsClient.disconnect();
      useConnectionStore.getState().stopHealthPolling();
    };
  }, [jwt]);

  useEffect(() => {
    if (status === "loading") return;
    if (!session && !isPublic) {
      router.replace("/login");
    }
  }, [session, status, isPublic, router]);

  // Loading state for protected routes
  if (status === "loading" && !isPublic) {
    return (
      <div className="flex items-center justify-center h-screen bg-bg-canvas">
        <div className="flex flex-col items-center gap-4">
          <div className="h-8 w-8 rounded-full border-2 border-accent-500 border-t-transparent animate-spin" />
          <p className="text-xs text-fg-muted font-mono uppercase tracking-widest num-tabular">
            Authenticating...
          </p>
        </div>
      </div>
    );
  }

  // Unauthenticated on protected route — don't render
  if (!session && !isPublic) {
    return null;
  }

  // Public route (login) — render children directly without shell
  if (isPublic) {
    return <>{children}</>;
  }

  // Authenticated route — render the redesign shell
  return <RedesignShell>{children}</RedesignShell>;
}
