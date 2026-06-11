"use client";

import { LeftRail } from "./LeftRail";

/**
 * Generic page-body skeleton (FE-W0). Mirrors the common surface layout
 * (title row, metric cards, two content panels) so the real page paints
 * into already-reserved space (CLS ≈ 0). Used as the root Suspense
 * fallback in RedesignShell and by the pre-auth ShellSkeleton.
 */
export function PageLoading() {
  return (
    <div
      role="status"
      aria-label="Loading"
      className="p-4 md:p-6 space-y-4 animate-pulse-subtle"
    >
      <div className="h-7 w-48 rounded-md bg-bg-raised" />
      <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
        <div className="h-24 rounded-lg border border-border-subtle bg-bg-panel" />
        <div className="h-24 rounded-lg border border-border-subtle bg-bg-panel" />
        <div className="h-24 rounded-lg border border-border-subtle bg-bg-panel" />
      </div>
      <div className="h-64 rounded-lg border border-border-subtle bg-bg-panel" />
      <div className="h-40 rounded-lg border border-border-subtle bg-bg-panel" />
    </div>
  );
}

/**
 * Pre-auth streaming shell: the real LeftRail plus a static ChromeBar
 * placeholder and skeleton body, faded and inert while NextAuth resolves.
 * Replaces the bare full-screen spinner so first paint shows the app frame
 * the user is about to get (no blank-then-pop).
 */
export function ShellSkeleton() {
  return (
    <div
      className="flex h-screen overflow-hidden bg-bg-canvas text-fg opacity-80 pointer-events-none select-none"
      role="status"
      aria-busy="true"
      aria-label="Authenticating"
    >
      <LeftRail />
      <div className="flex-1 flex flex-col min-w-0 overflow-hidden">
        <header className="h-11 px-3 md:px-4 shrink-0 border-b border-border-subtle bg-bg-panel flex items-center">
          <div className="h-4 w-32 rounded bg-bg-raised animate-pulse-subtle" />
        </header>
        <main className="flex-1 overflow-hidden">
          <PageLoading />
        </main>
      </div>
    </div>
  );
}
