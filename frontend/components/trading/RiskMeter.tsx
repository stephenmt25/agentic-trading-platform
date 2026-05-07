"use client";

import { forwardRef, type HTMLAttributes } from "react";
import { cva, type VariantProps } from "class-variance-authority";
import { cn } from "@/lib/utils";

/**
 * RiskMeter per docs/design/04-component-specs/trading-specific.md.
 *
 * Centerpiece of Risk Control, compact variant on Hot Trading. Discrete
 * segmented bar — explicitly NOT a smooth gradient (per spec: thresholds
 * are decisions, not preferences).
 *
 * Default segmenting:
 *   - 0–60%   green-zone (bid.500)
 *   - 60–85%  amber-zone (warn.500)
 *   - 85–100% red-zone   (danger.500)
 *
 * Needle marks current value. Pulse animation in amber/red zones.
 * Caller is responsible for the surface-level `kill-switch armed-soft`
 * behavior when red — this component just renders the meter state.
 *
 * Inputs may exceed 100% (over-budget); clamped visually but the
 * numeric readout shows the true value so the user sees the breach.
 */

const root = cva("relative w-full select-none num-tabular", {
  variants: {
    compact: {
      true: "",
      false: "",
    },
  },
  defaultVariants: { compact: false },
});

export type RiskMeterKind =
  | "leverage"
  | "portfolio-var"
  | "concentration"
  | "drawdown"
  | "custom";

export interface RiskMeterProps
  extends Omit<HTMLAttributes<HTMLDivElement>, "children">,
    VariantProps<typeof root> {
  /** Current value, in the same units as `max`. */
  value: number;
  /** Budget upper bound (e.g., 100% leverage = max 100). */
  max: number;
  /** Lower bound, defaults to 0. */
  min?: number;
  kind?: RiskMeterKind;
  /** Override segment thresholds (defaults: [0.6, 0.85] of max). */
  thresholds?: [number, number];
  /** Hide the numeric readout (compact wants this off). */
  hideReadout?: boolean;
  /** Hide the threshold tick marks. */
  hideThresholds?: boolean;
  /** Optional units suffix shown next to value (e.g., "x", "%"). */
  unit?: string;
  /** Format the readout. Default rounds to 2 dp + appends unit. */
  format?: (value: number, max: number) => string;
  label?: string;
}

const KIND_LABEL: Record<RiskMeterKind, string> = {
  leverage: "Leverage",
  "portfolio-var": "Portfolio VaR",
  concentration: "Concentration",
  drawdown: "Drawdown",
  custom: "",
};

const KIND_UNIT: Partial<Record<RiskMeterKind, string>> = {
  leverage: "x",
  "portfolio-var": "%",
  concentration: "%",
  drawdown: "%",
};

export const RiskMeter = forwardRef<HTMLDivElement, RiskMeterProps>(
  (
    {
      value,
      max,
      min = 0,
      kind = "custom",
      thresholds,
      compact = false,
      hideReadout,
      hideThresholds,
      unit,
      format,
      label,
      className,
      ...props
    },
    ref
  ) => {
    const range = max - min || 1;
    const ratio = (value - min) / range;
    const clampedRatio = Math.max(0, Math.min(1, ratio));

    const [t1Ratio, t2Ratio] = thresholds ?? [0.6, 0.85];
    const t1 = min + range * t1Ratio;
    const t2 = min + range * t2Ratio;

    const zone: "green" | "amber" | "red" =
      value >= t2 ? "red" : value >= t1 ? "amber" : "green";

    const resolvedUnit = unit ?? KIND_UNIT[kind] ?? "";
    const resolvedLabel = label ?? KIND_LABEL[kind];
    const resolvedFormat =
      format ??
      ((v: number) => {
        const digits = resolvedUnit === "x" ? 1 : 1;
        return `${v.toLocaleString(undefined, {
          minimumFractionDigits: digits,
          maximumFractionDigits: digits,
        })}${resolvedUnit}`;
      });

    // Compact = 8px tall per spec, no thresholds visible.
    const barHeight = compact ? "h-2" : "h-3";
    const wrapperEffectiveHide = compact ? true : hideThresholds;

    const needleLeft = `${(clampedRatio * 100).toFixed(2)}%`;

    return (
      <div
        ref={ref}
        role="meter"
        aria-valuemin={min}
        aria-valuemax={max}
        aria-valuenow={value}
        aria-label={resolvedLabel || `Risk meter`}
        data-zone={zone}
        className={cn(root({ compact }), "flex flex-col gap-1.5", className)}
        {...props}
      >
        {!compact && (resolvedLabel || !hideReadout) && (
          <div className="flex items-baseline justify-between gap-3">
            {resolvedLabel && (
              <span className="text-[11px] uppercase tracking-wider text-fg-muted">
                {resolvedLabel}
              </span>
            )}
            {!hideReadout && (
              <span
                className={cn(
                  "text-[13px] font-mono font-semibold",
                  zone === "red"
                    ? "text-danger-500"
                    : zone === "amber"
                      ? "text-warn-500"
                      : "text-fg"
                )}
              >
                {resolvedFormat(value, max)}
              </span>
            )}
          </div>
        )}

        {/* Bar: three discrete segments laid out via percentage widths. */}
        <div
          className={cn(
            "relative w-full rounded-sm overflow-hidden bg-neutral-800",
            barHeight,
            // Keep the bar focusable indirectly via the wrapping role=meter
          )}
        >
          {/* Green zone */}
          <div
            className="absolute inset-y-0 left-0 bg-bid-500/30"
            style={{ width: `${t1Ratio * 100}%` }}
            aria-hidden
          />
          {/* Amber zone */}
          <div
            className="absolute inset-y-0 bg-warn-500/30"
            style={{
              left: `${t1Ratio * 100}%`,
              width: `${(t2Ratio - t1Ratio) * 100}%`,
            }}
            aria-hidden
          />
          {/* Red zone */}
          <div
            className="absolute inset-y-0 bg-danger-500/30"
            style={{
              left: `${t2Ratio * 100}%`,
              right: 0,
            }}
            aria-hidden
          />

          {/* Discrete threshold dividers — visible boundaries per spec. */}
          {!wrapperEffectiveHide && (
            <>
              <span
                aria-hidden
                className="absolute inset-y-0 w-px bg-border-strong"
                style={{ left: `${t1Ratio * 100}%` }}
              />
              <span
                aria-hidden
                className="absolute inset-y-0 w-px bg-border-strong"
                style={{ left: `${t2Ratio * 100}%` }}
              />
            </>
          )}

          {/* Filled portion (the value bar): solid color for the zone. */}
          <div
            aria-hidden
            className={cn(
              "absolute inset-y-0 left-0 transition-[width] duration-[180ms] ease-out",
              zone === "red"
                ? "bg-danger-500/70"
                : zone === "amber"
                  ? "bg-warn-500/70"
                  : "bg-bid-500/60"
            )}
            style={{ width: needleLeft }}
          />

          {/* Needle marker. */}
          <span
            aria-hidden
            data-testid="risk-meter-needle"
            className={cn(
              "absolute top-0 bottom-0 -translate-x-1/2 w-[2px]",
              zone === "red"
                ? "bg-danger-500 animate-pulse"
                : zone === "amber"
                  ? "bg-warn-500 animate-pulse"
                  : "bg-fg"
            )}
            style={{ left: needleLeft }}
          />
        </div>

        {!compact && !hideThresholds && (
          <div className="relative w-full text-[10px] uppercase tracking-wider text-fg-muted h-3">
            <span
              className="absolute -translate-x-1/2 num-tabular"
              style={{ left: `${t1Ratio * 100}%` }}
            >
              {resolvedFormat(t1, max)}
            </span>
            <span
              className="absolute -translate-x-1/2 num-tabular"
              style={{ left: `${t2Ratio * 100}%` }}
            >
              {resolvedFormat(t2, max)}
            </span>
          </div>
        )}
      </div>
    );
  }
);
RiskMeter.displayName = "RiskMeter";

export default RiskMeter;
