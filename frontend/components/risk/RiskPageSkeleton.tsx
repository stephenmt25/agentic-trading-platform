"use client";

/**
 * /risk initial-load skeleton (FE-W1). Built from the PageLoading.tsx
 * pattern — h-7 header row + pulse cards mirroring the page's section
 * layout (matrix strip, kill-switch panel, exposure panel, limits list)
 * so the real page paints into already-reserved space instead of the
 * empty-state pop. `inert` keeps it out of tab order and the a11y tree.
 */
export function RiskPageSkeleton() {
  return (
    <div
      role="status"
      aria-label="Loading risk control"
      inert
      className="flex flex-col h-full bg-bg-canvas"
    >
      <div className="border-b border-border-subtle px-6 py-4 animate-pulse-subtle">
        <div className="h-3 w-24 rounded bg-bg-raised" />
        <div className="h-7 w-48 rounded-md bg-bg-raised mt-2" />
        <div className="h-3 w-72 rounded bg-bg-raised mt-2" />
      </div>
      <div className="px-6 py-6 flex flex-col gap-6 max-w-4xl animate-pulse-subtle">
        {/* Profiles risk matrix strip */}
        <div className="flex gap-3">
          <div className="h-44 w-72 shrink-0 rounded-md border border-border-subtle bg-bg-panel" />
          <div className="h-44 w-72 shrink-0 rounded-md border border-border-subtle bg-bg-panel" />
        </div>
        {/* Kill switch panel */}
        <div className="h-40 rounded-md border border-border-subtle bg-bg-panel" />
        {/* Exposure panel */}
        <div className="h-64 rounded-md border border-border-subtle bg-bg-panel" />
        {/* Active limits list */}
        <div className="h-40 rounded-md border border-border-subtle bg-bg-panel" />
      </div>
    </div>
  );
}

export default RiskPageSkeleton;
