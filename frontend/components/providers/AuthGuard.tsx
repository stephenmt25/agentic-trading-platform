/**
 * @deprecated Auth guarding is now handled entirely by AppShell.
 * This file is kept as a no-op re-export to avoid breaking any stale imports.
 * Remove this file once all references have been cleaned up.
 */
"use client";

export function AuthGuard({ children }: { children: React.ReactNode }) {
  return <>{children}</>;
}
