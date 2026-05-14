"use client";

import { cn } from "@/lib/utils";

/**
 * Placeholder rendered while the lazy-loaded PriceChart bundle is being
 * fetched + mounted. Dimensions and outer chrome match the real component
 * (rounded border, 40px header, fluid plot area) so CLS stays at 0 when
 * the chart slots in.
 *
 * Visual: a faint grid + a baseline shimmer line. No text, no spinner —
 * the skeleton's job is to occupy the right space and signal "loading"
 * by structure, not motion. The shimmer is intentionally subtle (10%
 * opacity, slow pulse) so it doesn't compete with the live data already
 * painted in adjacent panels.
 */

const TIMEFRAMES = ["1m", "5m", "15m", "1h", "4h", "1d"];

export function PriceChartSkeleton({ className }: { className?: string }) {
  return (
    <div
      role="status"
      aria-label="Chart loading"
      className={cn(
        "flex flex-col rounded-md border border-border-subtle bg-bg-panel overflow-hidden",
        "flex-1 min-h-0",
        className,
      )}
      data-mode-hint="hot"
    >
      {/* Header — mirrors PriceChart.tsx:317 layout (44px) */}
      <header className="flex items-center gap-3 px-3 h-10 border-b border-border-subtle shrink-0">
        <div className="flex items-center gap-0.5" aria-hidden>
          {TIMEFRAMES.map((tf) => (
            <span
              key={tf}
              className="h-7 px-2 text-[12px] font-medium num-tabular text-fg-muted/40 flex items-center"
            >
              {tf}
            </span>
          ))}
        </div>
        <div className="ml-auto h-3 w-16 rounded-sm bg-bg-raised animate-pulse" />
      </header>

      {/* Plot area — faint grid lines + horizontal baseline shimmer */}
      <div className="flex-1 min-h-0 relative">
        <svg
          className="absolute inset-0 w-full h-full opacity-10"
          aria-hidden
          preserveAspectRatio="none"
          viewBox="0 0 100 100"
        >
          {[20, 40, 60, 80].map((y) => (
            <line
              key={y}
              x1="0"
              y1={y}
              x2="100"
              y2={y}
              stroke="currentColor"
              strokeWidth="0.1"
              strokeDasharray="0.5 0.5"
            />
          ))}
        </svg>
        <div className="absolute inset-x-0 top-1/2 -translate-y-1/2 h-px bg-fg-muted/20 animate-pulse" />
      </div>
    </div>
  );
}
