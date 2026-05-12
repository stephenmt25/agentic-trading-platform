"use client";

import {
  forwardRef,
  useEffect,
  useRef,
  useState,
  type HTMLAttributes,
} from "react";
import { cva, type VariantProps } from "class-variance-authority";
import { cn } from "@/lib/utils";

/**
 * PnLBadge per docs/design/04-component-specs/trading-specific.md.
 *
 * Critical-path: must update at every PnL tick without dropping frames
 * (per frontend/DESIGN.md). Implementation keeps the work pure-CSS:
 *   - tick-flash bg uses a CSS class toggled for --duration-tick
 *   - no layout-affecting transitions; only background-color
 *   - tabular numerics so the digit shape never reflows on update
 *
 * Modes:
 *   - absolute (default): "1,234.56" with optional currency
 *   - pct: "+2.34%"
 *   - bps: "+45 bps"
 *   - r-multiple: "+1.2R" (backtests)
 *
 * Sign tone derives from the value unless `tone` is supplied directly.
 * Caller should pass already-rounded numbers — the component does NOT
 * decide precision (per Decimal contract: don't round silently).
 */

const wrapper = cva(
  "inline-flex items-center gap-1 num-tabular leading-none whitespace-nowrap",
  {
    variants: {
      size: {
        inline: "text-[13px] font-medium",
        prominent: "text-2xl font-semibold tracking-tight",
      },
      tone: {
        bid: "text-bid-400",
        ask: "text-ask-500",
        neutral: "text-fg-muted",
      },
      flashing: {
        none: "",
        bid: "bg-bid-tick-flash rounded-sm px-1 -mx-1",
        ask: "bg-ask-tick-flash rounded-sm px-1 -mx-1",
      },
    },
    defaultVariants: { size: "inline", tone: "neutral", flashing: "none" },
  }
);

type Mode = "absolute" | "pct" | "bps" | "r-multiple";

export interface PnLBadgeProps
  extends Omit<HTMLAttributes<HTMLSpanElement>, "children">,
    VariantProps<typeof wrapper> {
  /** Numeric value. Pass it pre-rounded (Decimal contract). */
  value: number;
  mode?: Mode;
  /** Currency suffix when mode="absolute" (e.g., "USDC"). */
  currency?: string;
  /** Always show "+" for positive (default true for non-absolute modes). */
  signed?: boolean;
  /** Hide the ▲▼ arrow glyph (default shown). */
  hideArrow?: boolean;
  /** Force a tone — by default tone is derived from value sign. */
  tone?: "bid" | "ask" | "neutral";
  /** When true, briefly highlights the bg in the tick-flash color
   *  matching the value's sign on every value change.
   *  --duration-tick = 120ms. */
  flashOnChange?: boolean;
  /** Override decimal places used for default formatting.
   *  Default depends on mode: absolute=2, pct=2, bps=0, r-multiple=2. */
  digits?: number;
}

const ARROW_UP = "▲";
const ARROW_DOWN = "▼";
const ARROW_FLAT = "•";

function defaultDigits(mode: Mode): number {
  switch (mode) {
    case "bps":
      return 0;
    case "absolute":
    case "pct":
    case "r-multiple":
    default:
      return 2;
  }
}

function formatValue(
  value: number,
  mode: Mode,
  digits: number,
  signed: boolean,
  currency?: string
): { display: string; suffix?: string } {
  const sign = value > 0 ? "+" : value < 0 ? "−" : "";
  // Use minus sign U+2212 for typographic correctness on negative numbers.
  // Number.prototype.toFixed gives a hyphen-minus; we replace it.
  const abs = Math.abs(value);
  const absStr = abs.toLocaleString(undefined, {
    minimumFractionDigits: digits,
    maximumFractionDigits: digits,
  });
  const showSign = signed || value < 0;
  const display = showSign ? `${sign}${absStr}` : absStr;

  switch (mode) {
    case "pct":
      return { display: `${display}%` };
    case "bps":
      return { display: `${display} bps` };
    case "r-multiple":
      return { display: `${display}R` };
    case "absolute":
    default:
      return { display, suffix: currency };
  }
}

export const PnLBadge = forwardRef<HTMLSpanElement, PnLBadgeProps>(
  (
    {
      value,
      mode = "absolute",
      currency,
      signed,
      hideArrow,
      tone,
      flashOnChange = false,
      size,
      digits,
      className,
      ...props
    },
    ref
  ) => {
    // Derive tone from value sign if not provided.
    const resolvedTone =
      tone ?? (value > 0 ? "bid" : value < 0 ? "ask" : "neutral");

    // Default `signed` is true for non-absolute modes — pct/bps/r-multiple
    // are conventionally always signed in trading UIs.
    const resolvedSigned = signed ?? mode !== "absolute";
    const resolvedDigits = digits ?? defaultDigits(mode);

    const { display, suffix } = formatValue(
      value,
      mode,
      resolvedDigits,
      resolvedSigned,
      currency
    );

    // Tick flash: when value changes, set flashing for --duration-tick.
    const prev = useRef(value);
    const [flashing, setFlashing] = useState<"none" | "bid" | "ask">("none");
    useEffect(() => {
      if (!flashOnChange) return;
      if (prev.current === value) return;
      const dir = value > prev.current ? "bid" : "ask";
      prev.current = value;
      setFlashing(dir);
      const t = window.setTimeout(() => setFlashing("none"), 120);
      return () => window.clearTimeout(t);
    }, [value, flashOnChange]);

    const arrow =
      value > 0 ? ARROW_UP : value < 0 ? ARROW_DOWN : ARROW_FLAT;

    return (
      <span
        ref={ref}
        className={cn(
          wrapper({ size, tone: resolvedTone, flashing }),
          // ensure flashing transitions cleanly (no layout reflow)
          "transition-colors duration-[120ms]",
          className
        )}
        data-tone={resolvedTone}
        data-mode={mode}
        {...props}
      >
        {!hideArrow && (
          <span aria-hidden className="text-[0.85em]">
            {arrow}
          </span>
        )}
        <span>{display}</span>
        {suffix && (
          <span className="text-fg-muted text-[0.85em] ml-0.5">{suffix}</span>
        )}
      </span>
    );
  }
);
PnLBadge.displayName = "PnLBadge";

export default PnLBadge;
