"use client";

import {
  forwardRef,
  useEffect,
  useRef,
  useState,
  type HTMLAttributes,
} from "react";
import { Edit3, GitBranch, X } from "lucide-react";
import { cn } from "@/lib/utils";
import { Button } from "@/components/primitives/Button";
import { Tag } from "@/components/primitives/Tag";
import { PnLBadge } from "./PnLBadge";

/**
 * PositionRow per docs/design/04-component-specs/trading-specific.md.
 *
 * Wide row in a positions table. Cols:
 *   [symbol | side | size | entry | mark | unrealized | margin | leverage | actions]
 *
 * Implemented as a CSS grid div-row (role="row") so the actions can
 * be hover-revealed and the row can carry its own confirmation state
 * for partial-close clicks (per spec: only modal-equivalent in HOT).
 *
 * States:
 *   - default     bg-canvas
 *   - hover       actions reveal; bg-row-hover
 *   - near-liq    left bar warn.500; mark flashes warn.tick-flash
 *   - liquidating left bar danger.500; row dimmed
 *   - closed-just-now  6s bid.tick-flash for the row (caller controls)
 *
 * Two-click confirm: every close action requires a second click within
 * 2s (spec). The button label changes to "click again to confirm." Per
 * spec, this is the only modal-equivalent permitted in HOT mode.
 */

export type PositionSide = "long" | "short";
export type PositionState =
  | "default"
  | "near-liq"
  | "liquidating"
  | "closed-just-now";

export interface PositionRowProps
  extends Omit<HTMLAttributes<HTMLDivElement>, "children"> {
  symbol: string;
  side: PositionSide;
  /** Position size in base units. */
  size: number;
  entry: number;
  mark: number;
  /** Unrealized PnL in quote currency. */
  unrealized: number;
  /** Margin used in quote currency. */
  margin: number;
  /** Effective leverage (e.g., 5 for 5x). */
  leverage: number;
  state?: PositionState;
  /** Quote currency symbol shown in absolute values (e.g., "USDC"). */
  quoteCurrency?: string;
  /** Display digits per cell. */
  sizeDigits?: number;
  priceDigits?: number;
  /** Action callbacks. Component handles 2-click confirmation. */
  onClosePartial?: (pct: 25 | 50 | 100) => void;
  onEditStop?: () => void;
  onTraceCanvas?: () => void;
  density?: "compact" | "standard" | "comfortable";
}

function fmtPrice(v: number, digits: number): string {
  return v.toLocaleString(undefined, {
    minimumFractionDigits: digits,
    maximumFractionDigits: digits,
  });
}

function fmtSize(v: number, digits: number): string {
  return v.toLocaleString(undefined, {
    minimumFractionDigits: digits,
    maximumFractionDigits: digits,
  });
}

const CONFIRM_TIMEOUT_MS = 2000;

export const PositionRow = forwardRef<HTMLDivElement, PositionRowProps>(
  (
    {
      symbol,
      side,
      size,
      entry,
      mark,
      unrealized,
      margin,
      leverage,
      state = "default",
      quoteCurrency = "USDC",
      sizeDigits = 4,
      priceDigits = 2,
      onClosePartial,
      onEditStop,
      onTraceCanvas,
      density = "standard",
      className,
      ...props
    },
    ref
  ) => {
    // 2-click confirm machinery — armed pct + a timer.
    const [armed, setArmed] = useState<25 | 50 | 100 | null>(null);
    const armedTimer = useRef<number | null>(null);
    const clearArmed = () => {
      if (armedTimer.current !== null) {
        window.clearTimeout(armedTimer.current);
        armedTimer.current = null;
      }
      setArmed(null);
    };
    useEffect(() => () => clearArmed(), []);

    const handleCloseClick = (pct: 25 | 50 | 100) => {
      if (!onClosePartial) return;
      if (armed === pct) {
        clearArmed();
        onClosePartial(pct);
        return;
      }
      clearArmed();
      setArmed(pct);
      armedTimer.current = window.setTimeout(() => {
        setArmed(null);
      }, CONFIRM_TIMEOUT_MS);
    };

    const rowHeight =
      density === "compact"
        ? "h-7"
        : density === "comfortable"
          ? "h-11"
          : "h-9";

    const baseBg =
      state === "liquidating"
        ? "opacity-60"
        : state === "closed-just-now"
          ? "bg-bid-tick-flash"
          : "";

    const leftBarColor =
      state === "near-liq"
        ? "bg-warn-500"
        : state === "liquidating"
          ? "bg-danger-500"
          : null;

    return (
      <div
        ref={ref}
        role="row"
        data-state={state}
        data-side={side}
        aria-label={`${symbol} ${side} position, size ${fmtSize(size, sizeDigits)}, unrealized ${unrealized}`}
        className={cn(
          "relative grid items-center gap-x-4 px-3",
          rowHeight,
          // 9 columns: symbol, side, size, entry, mark, unrealized, margin, lev, actions.
          // Minimums sized for typical mid-cap perp values; the row asserts its
          // own width and the parent should overflow-x-auto if narrower than
          // the content. Right-aligned numeric content otherwise visually bleeds
          // into adjacent cells when columns crush below content width.
          "grid-cols-[100px_60px_minmax(72px,1fr)_minmax(80px,1fr)_minmax(80px,1fr)_minmax(140px,1.4fr)_minmax(80px,1fr)_56px_minmax(140px,auto)]",
          "text-[13px] num-tabular",
          "border-b border-border-subtle",
          "bg-bg-canvas hover:bg-bg-rowhover transition-colors",
          "group/row",
          baseBg,
          className
        )}
        {...props}
      >
        {leftBarColor && (
          <span
            aria-hidden
            className={cn(
              "absolute left-0 top-0 bottom-0 w-0.5",
              leftBarColor
            )}
          />
        )}

        {/* Symbol */}
        <span className="text-fg font-medium truncate min-w-0" role="cell">
          {symbol}
        </span>

        {/* Side */}
        <span role="cell" className="min-w-0 overflow-hidden">
          <Tag intent={side === "long" ? "bid" : "ask"}>{side}</Tag>
        </span>

        {/* Size */}
        <span className="text-right text-fg min-w-0 overflow-hidden" role="cell">
          {fmtSize(size, sizeDigits)}
        </span>

        {/* Entry */}
        <span
          className="text-right text-fg-secondary min-w-0 overflow-hidden"
          role="cell"
        >
          {fmtPrice(entry, priceDigits)}
        </span>

        {/* Mark */}
        <span
          role="cell"
          className={cn(
            "text-right min-w-0 overflow-hidden",
            state === "near-liq" ? "text-warn-500" : "text-fg-secondary",
            state === "near-liq" && "bg-warn-500/10 rounded-sm px-1 -mx-1"
          )}
        >
          {fmtPrice(mark, priceDigits)}
        </span>

        {/* Unrealized PnL */}
        <span
          className="text-right min-w-0 overflow-hidden flex justify-end"
          role="cell"
        >
          <PnLBadge
            value={unrealized}
            currency={quoteCurrency}
            mode="absolute"
            signed
            hideArrow
          />
        </span>

        {/* Margin */}
        <span
          className="text-right text-fg-secondary min-w-0 overflow-hidden"
          role="cell"
        >
          {fmtPrice(margin, priceDigits)}
        </span>

        {/* Leverage */}
        <span
          className="text-right text-fg-muted min-w-0 overflow-hidden"
          role="cell"
        >
          {leverage.toLocaleString()}x
        </span>

        {/* Actions — hover-revealed (display only on hover/focus-within) */}
        <span
          role="cell"
          className={cn(
            "flex items-center justify-end gap-1 transition-opacity",
            "opacity-0 group-hover/row:opacity-100 focus-within:opacity-100"
          )}
        >
          {([25, 50, 100] as const).map((pct) => {
            const isArmed = armed === pct;
            return (
              <Button
                key={pct}
                size="xs"
                intent={isArmed ? "danger" : "secondary"}
                onClick={() => handleCloseClick(pct)}
                aria-label={
                  isArmed
                    ? `Confirm close ${pct}% of ${symbol}`
                    : `Close ${pct}% of ${symbol}`
                }
              >
                {isArmed ? "confirm" : `${pct}%`}
              </Button>
            );
          })}
          {onEditStop && (
            <Button
              size="xs"
              intent="secondary"
              iconOnly
              aria-label={`Edit stop for ${symbol}`}
              onClick={onEditStop}
            >
              <Edit3 className="w-3 h-3" strokeWidth={1.5} />
            </Button>
          )}
          {onTraceCanvas && (
            <Button
              size="xs"
              intent="secondary"
              iconOnly
              aria-label={`Trace ${symbol} to canvas`}
              onClick={onTraceCanvas}
            >
              <GitBranch className="w-3 h-3" strokeWidth={1.5} />
            </Button>
          )}
          {!onEditStop && !onTraceCanvas && !onClosePartial && (
            <span aria-hidden>
              <X className="w-3 h-3 text-fg-disabled" strokeWidth={1.5} />
            </span>
          )}
        </span>
      </div>
    );
  }
);
PositionRow.displayName = "PositionRow";

export default PositionRow;
