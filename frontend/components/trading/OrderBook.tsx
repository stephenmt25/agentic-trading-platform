"use client";

import {
  forwardRef,
  memo,
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
  type HTMLAttributes,
  type KeyboardEvent,
} from "react";
import { Virtuoso } from "react-virtuoso";
import { cn } from "@/lib/utils";

/**
 * OrderBook per docs/design/04-component-specs/trading-specific.md.
 *
 * Critical-path (per frontend/DESIGN.md): must virtualize and never
 * block the main thread on update bursts. Implementation:
 *   - >50 levels per side: use react-virtuoso to bound rendered DOM
 *   - flash overlay is pure CSS (timed via setTimeout, not animation)
 *   - SNAP, never animate row insertion (per spec — animation at typical
 *     update rates is seizure-inducing)
 *
 * Two layouts:
 *   - split (default): asks left column, bids right column, mid bar between
 *   - stacked: asks on top descending, mid bar middle, bids below descending
 *
 * Each row carries a left→right cumulative-fill bg in the side color
 * at 12% alpha. Wide-spread state (configurable bps) shows the spread
 * badge in warn.500.
 */

export interface OrderBookLevel {
  price: number;
  /** Liquidity at this level (NOT cumulative). */
  size: number;
}

export type OrderBookStyle = "split" | "stacked";

export interface OrderBookProps
  extends Omit<HTMLAttributes<HTMLDivElement>, "children" | "style"> {
  bids: OrderBookLevel[];
  asks: OrderBookLevel[];
  /** Layout — split (default) or stacked. Per spec OrderBook spec. */
  style?: OrderBookStyle;
  /** Levels per side. Above 50 → virtualized. */
  depthRows?: number;
  /** Spread threshold in bps; above this the badge turns warn.500. */
  wideSpreadBps?: number;
  /** When set, briefly highlights a row on update for --duration-tick. */
  flashPrice?: number | null;
  flashSide?: "bid" | "ask";
  /** Display digits for price/size. */
  priceDigits?: number;
  sizeDigits?: number;
  /** Aggregation tick size (UI-only, caller does the bucketing). */
  aggregation?: number;
  /** Optional grouping highlight bar — when aggregation coarser than native. */
  showGroupingHighlight?: boolean;
  /** Threshold above which a row gets the large-print left bar.
   *  Default: 95th percentile of provided sizes. */
  largePrintQuantile?: number;
  onSelectLevel?: (level: OrderBookLevel, side: "bid" | "ask") => void;
}

interface LevelWithCum extends OrderBookLevel {
  cum: number;
  pctOfMax: number;
  isLargePrint: boolean;
}

function withCumulative(
  levels: OrderBookLevel[],
  largePrintThreshold: number
): { rows: LevelWithCum[]; cumMax: number } {
  let cum = 0;
  const rows = levels.map((l) => {
    cum += l.size;
    return {
      ...l,
      cum,
      pctOfMax: 0,
      isLargePrint: l.size >= largePrintThreshold,
    };
  });
  const cumMax = cum || 1;
  for (const r of rows) r.pctOfMax = r.cum / cumMax;
  return { rows, cumMax };
}

function quantile(values: number[], q: number): number {
  if (values.length === 0) return Infinity;
  const sorted = [...values].sort((a, b) => a - b);
  const pos = (sorted.length - 1) * q;
  const base = Math.floor(pos);
  const rest = pos - base;
  if (sorted[base + 1] !== undefined) {
    return sorted[base] + rest * (sorted[base + 1] - sorted[base]);
  }
  return sorted[base];
}

function fmt(v: number, digits: number): string {
  return v.toLocaleString(undefined, {
    minimumFractionDigits: digits,
    maximumFractionDigits: digits,
  });
}

interface RowProps {
  level: LevelWithCum;
  side: "bid" | "ask";
  priceDigits: number;
  sizeDigits: number;
  flashing: boolean;
  rowHeight: string;
  showGroupingHighlight: boolean;
  isFocused: boolean;
  onClick?: () => void;
  onFocus?: () => void;
  rowIndex: number;
}

function BookRowImpl({
  level,
  side,
  priceDigits,
  sizeDigits,
  flashing,
  rowHeight,
  showGroupingHighlight,
  isFocused,
  onClick,
  onFocus,
  rowIndex,
}: RowProps) {
  return (
    <div
      role="row"
      tabIndex={isFocused ? 0 : -1}
      aria-rowindex={rowIndex + 1}
      data-side={side}
      data-large-print={level.isLargePrint || undefined}
      data-flashing={flashing || undefined}
      onClick={onClick}
      onFocus={onFocus}
      aria-label={`${side === "bid" ? "Bid" : "Ask"} ${fmt(level.price, priceDigits)}, size ${fmt(level.size, sizeDigits)}, cumulative ${fmt(level.cum, sizeDigits)}`}
      className={cn(
        "relative grid grid-cols-3 items-center gap-2 px-2 num-tabular font-mono text-[12px]",
        "cursor-default select-none",
        rowHeight,
        // base text by side
        side === "bid" ? "text-bid-300" : "text-ask-300",
        // focus ring
        isFocused && "outline outline-1 outline-accent-500 -outline-offset-1",
        // flash class — caller controls duration via timer
        flashing &&
          (side === "bid" ? "bg-bid-tick-flash" : "bg-ask-tick-flash"),
        level.isLargePrint && side === "bid" && "border-l-2 border-bid-500",
        level.isLargePrint && side === "ask" && "border-l-2 border-ask-500"
      )}
    >
      {/* cumulative-fill background, left→right */}
      <span
        aria-hidden
        className={cn(
          "absolute inset-y-0 left-0",
          side === "bid" ? "bg-bid-500/12" : "bg-ask-500/12"
        )}
        style={{ width: `${(level.pctOfMax * 100).toFixed(2)}%` }}
      />
      {showGroupingHighlight && (
        <span
          aria-hidden
          className="absolute inset-y-0 left-0 right-0 bg-accent-500/8"
        />
      )}
      <span role="cell" className="relative text-left">
        {fmt(level.price, priceDigits)}
      </span>
      <span role="cell" className="relative text-right text-fg-secondary">
        {fmt(level.size, sizeDigits)}
      </span>
      <span role="cell" className="relative text-right text-fg-muted">
        {fmt(level.cum, sizeDigits)}
      </span>
    </div>
  );
}

// Memoized so a parent re-render (every store update) doesn't re-render
// every BookRow when its level / focus / flash state hasn't changed.
// Critical-path: parent updates at up to 100Hz under live load.
const BookRow = memo(BookRowImpl);

export const OrderBook = forwardRef<HTMLDivElement, OrderBookProps>(
  (
    {
      bids,
      asks,
      style: layout = "split",
      depthRows = 20,
      wideSpreadBps = 25,
      flashPrice,
      flashSide,
      priceDigits = 2,
      sizeDigits = 4,
      aggregation,
      showGroupingHighlight = false,
      largePrintQuantile = 0.95,
      onSelectLevel,
      className,
      ...props
    },
    ref
  ) => {
    // Sort: asks ascending (best ask = lowest price first), bids descending.
    // Per spec, asks are rendered top-down with prices descending toward mid;
    // we keep ascending here and reverse at render-time for split layout.
    const sortedAsks = useMemo(
      () => [...asks].sort((a, b) => a.price - b.price).slice(0, depthRows),
      [asks, depthRows]
    );
    const sortedBids = useMemo(
      () => [...bids].sort((a, b) => b.price - a.price).slice(0, depthRows),
      [bids, depthRows]
    );

    const allSizes = useMemo(
      () => [...sortedAsks, ...sortedBids].map((l) => l.size),
      [sortedAsks, sortedBids]
    );
    const lpThreshold = useMemo(
      () => quantile(allSizes, largePrintQuantile),
      [allSizes, largePrintQuantile]
    );

    const askCum = useMemo(
      () => withCumulative(sortedAsks, lpThreshold),
      [sortedAsks, lpThreshold]
    );
    const bidCum = useMemo(
      () => withCumulative(sortedBids, lpThreshold),
      [sortedBids, lpThreshold]
    );

    const bestBid = sortedBids[0]?.price;
    const bestAsk = sortedAsks[0]?.price;
    const mid =
      bestBid !== undefined && bestAsk !== undefined
        ? (bestBid + bestAsk) / 2
        : undefined;
    const spread =
      bestBid !== undefined && bestAsk !== undefined
        ? bestAsk - bestBid
        : undefined;
    const spreadBps =
      spread !== undefined && mid !== undefined
        ? (spread / mid) * 10000
        : undefined;
    const isWide =
      spreadBps !== undefined && spreadBps > wideSpreadBps;

    // Tick flash decay (--duration-tick = 120ms)
    const [flashKey, setFlashKey] = useState<{
      price: number;
      side: "bid" | "ask";
    } | null>(null);
    useEffect(() => {
      if (flashPrice == null || !flashSide) return;
      setFlashKey({ price: flashPrice, side: flashSide });
      const t = window.setTimeout(() => setFlashKey(null), 120);
      return () => window.clearTimeout(t);
    }, [flashPrice, flashSide]);

    const isFlashing = (price: number, side: "bid" | "ask") =>
      !!flashKey && flashKey.side === side && flashKey.price === price;

    const rowHeight = "h-6"; // 24px per spec compact

    // Keyboard navigation: arrow keys move between price levels.
    // Indices are concatenated [asks descending visually, bids descending].
    const allLevelsForKeyboard = useMemo(() => {
      // Visual order (top→bottom for both layouts):
      //   asks top-down with descending price (so reverse the ascending sort)
      //   then bids descending price (already sorted)
      const visualAsks = [...askCum.rows].reverse().map((l) => ({
        l,
        side: "ask" as const,
      }));
      const visualBids = bidCum.rows.map((l) => ({ l, side: "bid" as const }));
      return [...visualAsks, ...visualBids];
    }, [askCum.rows, bidCum.rows]);

    // Precomputed price → globalIdx lookup so each render isn't doing
    // O(n) findIndex per row. At 25 levels × 2 sides × ~10Hz this saves
    // ~250 lookups/sec; under the Phase 8.4 100-update/s budget it
    // saves 5000 lookups/sec.
    const keyboardIndex = useMemo(() => {
      const m = new Map<string, number>();
      allLevelsForKeyboard.forEach((x, i) => {
        m.set(`${x.side}-${x.l.price}`, i);
      });
      return m;
    }, [allLevelsForKeyboard]);

    const [focusIdx, setFocusIdx] = useState(0);
    const handleKey = useCallback(
      (e: KeyboardEvent<HTMLDivElement>) => {
        if (allLevelsForKeyboard.length === 0) return;
        if (e.key === "ArrowUp") {
          e.preventDefault();
          setFocusIdx((i) => Math.max(0, i - 1));
        } else if (e.key === "ArrowDown") {
          e.preventDefault();
          setFocusIdx((i) =>
            Math.min(allLevelsForKeyboard.length - 1, i + 1)
          );
        } else if (e.key === "Enter" || e.key === " ") {
          const target = allLevelsForKeyboard[focusIdx];
          if (target) {
            e.preventDefault();
            onSelectLevel?.(target.l, target.side);
          }
        }
      },
      [allLevelsForKeyboard, focusIdx, onSelectLevel]
    );

    const virtualize = depthRows > 50;

    const renderAsks = () => {
      // Display order: TOP = highest price (descending toward mid)
      const visualOrder = [...askCum.rows].reverse();
      if (virtualize) {
        return (
          <Virtuoso
            data={visualOrder}
            itemContent={(_idx, level) => {
              const globalIdx = keyboardIndex.get(`ask-${level.price}`) ?? 0;
              return (
                <BookRow
                  level={level}
                  side="ask"
                  priceDigits={priceDigits}
                  sizeDigits={sizeDigits}
                  flashing={isFlashing(level.price, "ask")}
                  rowHeight={rowHeight}
                  showGroupingHighlight={
                    !!aggregation && showGroupingHighlight
                  }
                  isFocused={focusIdx === globalIdx}
                  onFocus={() => setFocusIdx(globalIdx)}
                  onClick={() => onSelectLevel?.(level, "ask")}
                  rowIndex={globalIdx}
                />
              );
            }}
            style={{ height: 200 }}
          />
        );
      }
      return visualOrder.map((level) => {
        const globalIdx = keyboardIndex.get(`ask-${level.price}`) ?? 0;
        return (
          <BookRow
            key={`ask-${level.price}`}
            level={level}
            side="ask"
            priceDigits={priceDigits}
            sizeDigits={sizeDigits}
            flashing={isFlashing(level.price, "ask")}
            rowHeight={rowHeight}
            showGroupingHighlight={!!aggregation && showGroupingHighlight}
            isFocused={focusIdx === globalIdx}
            onFocus={() => setFocusIdx(globalIdx)}
            onClick={() => onSelectLevel?.(level, "ask")}
            rowIndex={globalIdx}
          />
        );
      });
    };

    const renderBids = () => {
      const visualOrder = bidCum.rows;
      if (virtualize) {
        return (
          <Virtuoso
            data={visualOrder}
            itemContent={(_idx, level) => {
              const globalIdx = keyboardIndex.get(`bid-${level.price}`) ?? 0;
              return (
                <BookRow
                  level={level}
                  side="bid"
                  priceDigits={priceDigits}
                  sizeDigits={sizeDigits}
                  flashing={isFlashing(level.price, "bid")}
                  rowHeight={rowHeight}
                  showGroupingHighlight={
                    !!aggregation && showGroupingHighlight
                  }
                  isFocused={focusIdx === globalIdx}
                  onFocus={() => setFocusIdx(globalIdx)}
                  onClick={() => onSelectLevel?.(level, "bid")}
                  rowIndex={globalIdx}
                />
              );
            }}
            style={{ height: 200 }}
          />
        );
      }
      return visualOrder.map((level) => {
        const globalIdx = keyboardIndex.get(`bid-${level.price}`) ?? 0;
        return (
          <BookRow
            key={`bid-${level.price}`}
            level={level}
            side="bid"
            priceDigits={priceDigits}
            sizeDigits={sizeDigits}
            flashing={isFlashing(level.price, "bid")}
            rowHeight={rowHeight}
            showGroupingHighlight={!!aggregation && showGroupingHighlight}
            isFocused={focusIdx === globalIdx}
            onFocus={() => setFocusIdx(globalIdx)}
            onClick={() => onSelectLevel?.(level, "bid")}
            rowIndex={globalIdx}
          />
        );
      });
    };

    const headerCx =
      "grid grid-cols-3 gap-2 px-2 h-6 items-center text-[10px] uppercase tracking-wider text-fg-muted num-tabular border-b border-border-subtle";

    const midBar = (
      <div
        role="separator"
        data-wide-spread={isWide || undefined}
        aria-label={
          mid !== undefined
            ? `Mid ${fmt(mid, priceDigits)}, spread ${spreadBps !== undefined ? spreadBps.toFixed(1) : "—"} bps`
            : "Mid"
        }
        className={cn(
          "flex items-center justify-between gap-3 px-2 h-7 border-y border-border-subtle bg-bg-panel num-tabular font-mono text-[12px]",
          isWide && "bg-warn-500/10"
        )}
      >
        <span className={cn("text-fg-secondary")}>
          {mid !== undefined ? fmt(mid, priceDigits) : "—"}
        </span>
        <span
          className={cn(
            "px-1.5 py-0.5 rounded-sm text-[10px] font-semibold",
            isWide
              ? "bg-warn-500/30 text-warn-400"
              : "bg-neutral-800 text-fg-muted"
          )}
        >
          {spreadBps !== undefined ? `${spreadBps.toFixed(1)} bps` : "—"}
        </span>
        <span className="text-fg-muted text-right">
          {spread !== undefined ? fmt(spread, priceDigits) : "—"}
        </span>
      </div>
    );

    return (
      <div
        ref={ref}
        role="grid"
        aria-rowcount={allLevelsForKeyboard.length}
        aria-label="Order book"
        tabIndex={0}
        onKeyDown={handleKey}
        className={cn(
          "flex flex-col bg-bg-canvas border border-border-subtle rounded-md overflow-hidden",
          "focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent-500",
          className
        )}
        {...props}
      >
        {layout === "split" ? (
          <>
            <div className="grid grid-cols-2 divide-x divide-border-subtle">
              <div className="flex flex-col">
                <div className={headerCx}>
                  <span>price</span>
                  <span className="text-right">size</span>
                  <span className="text-right">cum</span>
                </div>
                <div role="rowgroup" data-side="ask">
                  {renderAsks()}
                </div>
              </div>
              <div className="flex flex-col">
                <div className={headerCx}>
                  <span>price</span>
                  <span className="text-right">size</span>
                  <span className="text-right">cum</span>
                </div>
                <div role="rowgroup" data-side="bid">
                  {renderBids()}
                </div>
              </div>
            </div>
            {midBar}
          </>
        ) : (
          <>
            <div className={headerCx}>
              <span>price</span>
              <span className="text-right">size</span>
              <span className="text-right">cum</span>
            </div>
            <div role="rowgroup" data-side="ask">
              {renderAsks()}
            </div>
            {midBar}
            <div role="rowgroup" data-side="bid">
              {renderBids()}
            </div>
          </>
        )}
      </div>
    );
  }
);
OrderBook.displayName = "OrderBook";

export default OrderBook;
