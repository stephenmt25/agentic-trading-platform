"use client";

import { forwardRef, type HTMLAttributes } from "react";
import { cn } from "@/lib/utils";

/**
 * TapeRow per docs/design/04-component-specs/trading-specific.md.
 *
 * Single row in the time-and-sales (trade tape) feed:
 *   [time | side | size | price]
 *
 * Side is encoded as a subtle bg tint on the row (bid.500/10% or
 * ask.500/10%). Per spec: "show side as just text 'BUY'/'SELL'" is
 * an explicit Don't — the row itself carries direction.
 *
 * Time is HH:MM:SS.mmm in mono. Tabular numerics on every numeric
 * cell. The component does NOT animate insertion — per spec, snap
 * (no animation) in HOT mode at typical update rates.
 */

export interface TapeRowProps
  extends Omit<HTMLAttributes<HTMLDivElement>, "children"> {
  side: "bid" | "ask";
  /** ms epoch or formatted string. If number, formatted to HH:MM:SS.mmm. */
  time: number | string;
  size: number | string;
  price: number | string;
  /** Display digits for size (default 4). */
  sizeDigits?: number;
  /** Display digits for price (default 2). */
  priceDigits?: number;
  /** Mark this row as a large print (>95th percentile size).
   *  Adds a 2px left bar in the side color per spec. */
  largePrint?: boolean;
  /** Density variant per the standard density taxonomy. */
  density?: "compact" | "standard" | "comfortable";
}

function fmt(value: number | string, digits: number): string {
  if (typeof value === "string") return value;
  return value.toLocaleString(undefined, {
    minimumFractionDigits: digits,
    maximumFractionDigits: digits,
  });
}

function fmtTime(time: number | string): string {
  if (typeof time === "string") return time;
  const d = new Date(time);
  const hh = String(d.getHours()).padStart(2, "0");
  const mm = String(d.getMinutes()).padStart(2, "0");
  const ss = String(d.getSeconds()).padStart(2, "0");
  const ms = String(d.getMilliseconds()).padStart(3, "0");
  return `${hh}:${mm}:${ss}.${ms}`;
}

export const TapeRow = forwardRef<HTMLDivElement, TapeRowProps>(
  (
    {
      side,
      time,
      size,
      price,
      sizeDigits = 4,
      priceDigits = 2,
      largePrint,
      density = "standard",
      className,
      ...props
    },
    ref
  ) => {
    const rowHeight =
      density === "compact"
        ? "h-5"
        : density === "comfortable"
          ? "h-7"
          : "h-6";

    const cellSize = density === "compact" ? "text-[11px]" : "text-[12px]";

    return (
      <div
        ref={ref}
        role="row"
        aria-label={`${side === "bid" ? "Buy" : "Sell"} ${size} at ${price}`}
        data-side={side}
        className={cn(
          "relative grid grid-cols-[auto_auto_1fr_auto] items-center gap-3 px-2",
          rowHeight,
          cellSize,
          "num-tabular font-mono",
          side === "bid" ? "bg-bid-500/10 text-bid-300" : "bg-ask-500/10 text-ask-300",
          className
        )}
        {...props}
      >
        {largePrint && (
          <span
            aria-hidden
            className={cn(
              "absolute left-0 top-0 bottom-0 w-0.5",
              side === "bid" ? "bg-bid-500" : "bg-ask-500"
            )}
          />
        )}
        <span className="text-fg-muted tracking-tight">
          {fmtTime(time)}
        </span>
        <span aria-hidden className={side === "bid" ? "text-bid-400" : "text-ask-400"}>
          {side === "bid" ? "▲" : "▼"}
        </span>
        <span className="text-fg-secondary text-right">
          {fmt(size, sizeDigits)}
        </span>
        <span className={cn("text-right", side === "bid" ? "text-bid-300" : "text-ask-300")}>
          {fmt(price, priceDigits)}
        </span>
      </div>
    );
  }
);
TapeRow.displayName = "TapeRow";

export default TapeRow;
