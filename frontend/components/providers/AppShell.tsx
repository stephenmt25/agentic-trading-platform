"use client";

import { useSession } from "next-auth/react";
import { usePathname, useRouter } from "next/navigation";
import { useEffect } from "react";
import { RedesignShell } from "@/components/shell/RedesignShell";
import { ShellSkeleton } from "@/components/shell/PageLoading";

const PUBLIC_PATHS = ["/login"];

/**
 * Auth gate wrapper. Visual chrome (rail, top bar, banners, command
 * palette) is delegated to RedesignShell. The WebSocket + health-polling
 * lifecycle moved to AuthProvider's SessionSync in FE-W0 so the socket is
 * warm the moment the JWT lands. The legacy aside/header was removed at
 * Phase 4.3 — see frontend/DESIGN-SYSTEM.legacy.md for the prior
 * implementation.
 */
export function AppShell({ children }: { children: React.ReactNode }) {
  const { data: session, status } = useSession();
  const pathname = usePathname();
  const router = useRouter();

  const isPublic = PUBLIC_PATHS.some((p) => pathname.startsWith(p));

  useEffect(() => {
    if (status === "loading") return;
    if (!session && !isPublic) {
      router.replace("/login");
    }
  }, [session, status, isPublic, router]);

  // Loading state for protected routes — faded chrome + skeleton body
  // instead of a bare spinner, so first paint shows the app frame (FE-W0).
  if (status === "loading" && !isPublic) {
    return <ShellSkeleton />;
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
