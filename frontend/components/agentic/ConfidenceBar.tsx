"use client";

import { forwardRef, type HTMLAttributes } from "react";
import { cn } from "@/lib/utils";

/**
 * ConfidenceBar per docs/design/04-component-specs/agentic.md.
 *
 * Stacked horizontal probability bar; segments labeled with their
 * probability; widths proportional to mass. Tallest segment label
 * uses fg-primary, others fg-muted (per spec).
 *
 * ADR-012 reconciliation: the original spec mentioned "regime_hmm
 * uses 3 violet shades." Per ADR-012 we collapse all agent identity
 * colors to accent — so multi-modal regime outputs use 3 ACCENT
 * shades (300/500/700) instead. Direction outputs (long/neutral/
 * short) keep bid/neutral/ask, which is unchanged. Per philosophy
 * P5, single point estimates throw away information; this component
 * is the canonical way to display probabilistic outputs.
 */

export interface ConfidenceSegment {
  /** Segment label, e.g., "trending", "long". */
  label: string;
  /** Probability mass in [0, 1]. */
  probability: number;
  /** Visual tone — semantic where possible. */
  tone?: "bid" | "ask" | "neutral" | "accent" | "accent-strong" | "accent-weak";
}

export interface ConfidenceBarProps
  extends Omit<HTMLAttributes<HTMLDivElement>, "children"> {
  segments: ConfidenceSegment[];
  /** Show probability percentages inside each segment when wide enough. */
  showInlineLabels?: boolean;
  /** Compact (16px tall, no inline labels) or standard (24px tall). */
  density?: "compact" | "standard";
  /** Optional historic distribution for backdrop comparison. Same shape. */
  historic?: ConfidenceSegment[];
  /** Optional title displayed above the bar. */
  title?: string;
  /** Optional subtitle (e.g., source agent + timestamp). */
  subtitle?: string;
}

const TONE_BG: Record<NonNullable<ConfidenceSegment["tone"]>, string> = {
  bid: "bg-bid-500/70",
  ask: "bg-ask-500/70",
  neutral: "bg-neutral-500/70",
  accent: "bg-accent-500/70",
  "accent-strong": "bg-accent-700/80",
  "accent-weak": "bg-accent-300/60",
};

const TONE_BG_HISTORIC: Record<
  NonNullable<ConfidenceSegment["tone"]>,
  string
> = {
  bid: "bg-bid-500/15",
  ask: "bg-ask-500/15",
  neutral: "bg-neutral-500/15",
  accent: "bg-accent-500/15",
  "accent-strong": "bg-accent-700/15",
  "accent-weak": "bg-accent-300/15",
};

function dominantIndex(segments: ConfidenceSegment[]): number {
  let best = 0;
  let bestVal = -Infinity;
  for (let i = 0; i < segments.length; i++) {
    if (segments[i].probability > bestVal) {
      bestVal = segments[i].probability;
      best = i;
    }
  }
  return best;
}

function fmtPct(p: number): string {
  return `${Math.round(p * 100)}%`;
}

export const ConfidenceBar = forwardRef<HTMLDivElement, ConfidenceBarProps>(
  (
    {
      segments,
      showInlineLabels = true,
      density = "standard",
      historic,
      title,
      subtitle,
      className,
      ...props
    },
    ref
  ) => {
    const dom = dominantIndex(segments);
    const total = segments.reduce((s, x) => s + x.probability, 0) || 1;
    const rowHeight = density === "compact" ? "h-4" : "h-6";

    return (
      <div
        ref={ref}
        role="group"
        aria-label={title ?? "Confidence distribution"}
        className={cn("flex flex-col gap-1.5 num-tabular", className)}
        {...props}
      >
        {(title || subtitle) && (
          <div className="flex items-baseline justify-between gap-3">
            {title && (
              <span className="text-[11px] uppercase tracking-wider text-fg-muted">
                {title}
              </span>
            )}
            {subtitle && (
              <span className="text-[10px] text-fg-muted font-mono">
                {subtitle}
              </span>
            )}
          </div>
        )}

        <div
          role="img"
          aria-label={
            "Distribution: " +
            segments
              .map((s) => `${s.label} ${fmtPct(s.probability / total)}`)
              .join(", ")
          }
          className={cn(
            "relative flex w-full overflow-hidden rounded-sm",
            rowHeight,
            "bg-neutral-800"
          )}
        >
          {historic && historic.length === segments.length && (
            <span
              aria-hidden
              className="absolute inset-0 flex"
              data-testid="confidence-historic-layer"
            >
              {historic.map((seg, i) => {
                const w = (seg.probability / total) * 100;
                const tone = seg.tone ?? "accent";
                return (
                  <span
                    key={`hist-${i}`}
                    className={cn("h-full", TONE_BG_HISTORIC[tone])}
                    style={{ width: `${w}%` }}
                  />
                );
              })}
            </span>
          )}

          {segments.map((seg, i) => {
            const w = (seg.probability / total) * 100;
            const tone = seg.tone ?? "accent";
            const isDom = i === dom;
            return (
              <span
                key={i}
                title={`${seg.label}: ${fmtPct(seg.probability / total)}`}
                className={cn(
                  "relative h-full flex items-center justify-center px-1 text-[10px] tracking-tight",
                  TONE_BG[tone],
                  isDom ? "text-fg" : "text-fg-muted",
                  i > 0 && "border-l border-bg-canvas/40"
                )}
                style={{ width: `${w}%` }}
              >
                {showInlineLabels && density === "standard" && w >= 12 ? (
                  <span className="truncate">
                    {seg.label} {fmtPct(seg.probability / total)}
                  </span>
                ) : null}
              </span>
            );
          })}
        </div>

        {/* Always show the legend below in compact mode (no inline labels) */}
        {(density === "compact" || !showInlineLabels) && (
          <ul className="flex flex-wrap items-center gap-x-3 gap-y-0.5 text-[10px] text-fg-secondary">
            {segments.map((seg, i) => {
              const tone = seg.tone ?? "accent";
              const isDom = i === dom;
              return (
                <li
                  key={i}
                  className={cn(
                    "inline-flex items-center gap-1",
                    isDom ? "text-fg" : "text-fg-muted"
                  )}
                >
                  <span
                    aria-hidden
                    className={cn(
                      "inline-block w-2 h-2 rounded-sm",
                      TONE_BG[tone]
                    )}
                  />
                  <span>{seg.label}</span>
                  <span className="text-fg-muted">
                    {fmtPct(seg.probability / total)}
                  </span>
                </li>
              );
            })}
          </ul>
        )}
      </div>
    );
  }
);
ConfidenceBar.displayName = "ConfidenceBar";

export default ConfidenceBar;
