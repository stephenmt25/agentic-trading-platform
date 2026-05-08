"use client";

import {
  useEffect,
  useMemo,
  useRef,
  useState,
  type HTMLAttributes,
  type ReactNode,
} from "react";
import {
  CandlestickSeries,
  HistogramSeries,
  createChart,
  type IChartApi,
  type ISeriesApi,
  type CandlestickData,
  type HistogramData,
  type Time,
  type DeepPartial,
  type ChartOptions,
} from "lightweight-charts";
import { Loader2, Pencil } from "lucide-react";
import { cn } from "@/lib/utils";
import { Pill, StatusDot } from "@/components/data-display";
import { Tag } from "@/components/primitives";

/**
 * PriceChart per docs/design/04-component-specs/price-chart.md.
 *
 * OHLC + volume chart. Thin Praxis-themed wrapper around `lightweight-charts`.
 * Theming flows from CSS custom properties — read via getComputedStyle and
 * applied via chart.applyOptions / series.applyOptions on every mode change.
 *
 * Data is caller-owned; this component does not fetch. Callers swap the
 * `candles` prop on timeframe / symbol changes; the wrapper diff-applies
 * via setData() (full replace) or update() (last-tick-only) as appropriate.
 *
 * Per spec:
 *   - up = bid color, down = ask color, wicks match.
 *   - volume sub-pane is an overlay on the price pane, pinned to the bottom 18%.
 *   - tick updates snap (no tween).
 *   - drawing tools, multi-pane indicators, replay-playback strip, range
 *     brush, and keyboard candle nav are deferred to v2 — surfaced inline.
 */

export type PriceChartTimeframe = "1m" | "5m" | "15m" | "1h" | "4h" | "1d";
export type PriceChartMode = "live" | "replay";
export type PriceChartDensity = "compact" | "standard" | "comfortable";

export interface PriceChartCandle {
  /** Unix epoch milliseconds for this candle's open time. */
  time: number;
  open: number;
  high: number;
  low: number;
  close: number;
  /** Volume for this bar (optional; falls through to no histogram if absent). */
  volume?: number;
}

const TIMEFRAMES: PriceChartTimeframe[] = [
  "1m",
  "5m",
  "15m",
  "1h",
  "4h",
  "1d",
];

const DENSITY_HEIGHT: Record<PriceChartDensity, number> = {
  compact: 300,
  standard: 420,
  comfortable: 560,
};

export interface PriceChartProps
  extends Omit<HTMLAttributes<HTMLDivElement>, "children"> {
  /** Candles, sorted ascending by time. */
  candles: PriceChartCandle[];
  /** Symbol shown in the header. e.g., "BTC-PERP". */
  symbol: string;
  /** Currently active timeframe; renders the tab as selected. */
  timeframe: PriceChartTimeframe;
  /** Called when the user clicks a timeframe tab. */
  onTimeframeChange?: (next: PriceChartTimeframe) => void;
  /** Subset of timeframes to render (default = all six). */
  timeframes?: PriceChartTimeframe[];
  /** Symbol selector slot. Caller renders e.g. a Select; rendered after the
   *  timeframe tabs. */
  symbolSlot?: ReactNode;
  /** Header status slot (right side); caller can pass a Pill / Tag / arbitrary
   *  content. When omitted, the wrapper renders a default "live" / "replay"
   *  pill based on `mode`. */
  statusSlot?: ReactNode;
  mode?: PriceChartMode;
  withVolume?: boolean;
  /** v1: surfaces a Pending tag in the left strip; no actual tools yet. */
  withDrawingTools?: boolean;
  /** Hook for the future depth-chart strip; v1 surfaces as Pending if true. */
  withDepthChart?: boolean;
  density?: PriceChartDensity;
  loading?: boolean;
  error?: string;
  emptyMessage?: string;
}

interface ChartRefs {
  chart: IChartApi;
  candle: ISeriesApi<"Candlestick">;
  volume: ISeriesApi<"Histogram"> | null;
}

export function PriceChart({
  candles,
  symbol,
  timeframe,
  onTimeframeChange,
  timeframes = TIMEFRAMES,
  symbolSlot,
  statusSlot,
  mode = "live",
  withVolume = true,
  withDrawingTools = true,
  withDepthChart = false,
  density = "standard",
  loading,
  error,
  emptyMessage = "No candles for this range.",
  className,
  ...props
}: PriceChartProps) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const chartRef = useRef<ChartRefs | null>(null);
  const [ready, setReady] = useState(false);

  const plotHeight = DENSITY_HEIGHT[density];

  // ---- Construct the chart on mount; dispose on unmount ----
  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;

    const tokens = readTokens();
    const chart = createChart(container, baseChartOptions(tokens));
    const candle = chart.addSeries(CandlestickSeries, candleOptions(tokens));
    const volume = withVolume
      ? chart.addSeries(HistogramSeries, volumeOptions())
      : null;
    if (volume) {
      // Pin volume to the bottom 18% of the price pane via priceScale margins.
      volume.priceScale().applyOptions({
        scaleMargins: { top: 0.82, bottom: 0 },
      });
    }
    chartRef.current = { chart, candle, volume };
    setReady(true);

    // Resize handling.
    const resize = () => {
      if (!container || !chartRef.current) return;
      chartRef.current.chart.applyOptions({
        width: container.clientWidth,
        height: plotHeight,
      });
    };
    resize();
    const ro = new ResizeObserver(resize);
    ro.observe(container);

    return () => {
      ro.disconnect();
      try {
        chart.remove();
      } catch {
        /* already disposed */
      }
      chartRef.current = null;
      setReady(false);
    };
    // We intentionally do NOT depend on tokens / withVolume here — those
    // remap via separate effects so the chart instance survives prop edits.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // ---- React to density changes (height only) ----
  useEffect(() => {
    if (!chartRef.current) return;
    const { chart } = chartRef.current;
    chart.applyOptions({ height: plotHeight });
  }, [plotHeight]);

  // ---- Re-theme when CSS tokens may have shifted (mode swap, dark-toggle) ----
  // We poll cheaply on a timer instead of subscribing to mutation observers —
  // mode swaps are rare and the cost is one getComputedStyle call per second.
  useEffect(() => {
    if (!ready) return;
    const apply = () => {
      if (!chartRef.current) return;
      const tokens = readTokens();
      chartRef.current.chart.applyOptions(baseChartOptions(tokens));
      chartRef.current.candle.applyOptions(candleOptions(tokens));
    };
    apply();
    const id = window.setInterval(apply, 1500);
    return () => window.clearInterval(id);
  }, [ready]);

  // ---- Apply data ----
  // Strategy: replace data on series identity / length change; otherwise
  // call update() with the last bar so live ticks stay snappy.
  const lastTimeRef = useRef<number | null>(null);

  useEffect(() => {
    if (!ready || !chartRef.current) return;
    const { candle, volume } = chartRef.current;
    if (candles.length === 0) {
      candle.setData([]);
      volume?.setData([]);
      lastTimeRef.current = null;
      return;
    }

    const lastIncoming = candles[candles.length - 1];
    const last = lastTimeRef.current;
    const isAppendOnly =
      last !== null &&
      candles.length >= 2 &&
      candles[0].time <= last &&
      lastIncoming.time >= last;

    if (!isAppendOnly) {
      // Full replace.
      candle.setData(toCandleData(candles));
      if (volume) volume.setData(toVolumeData(candles));
      lastTimeRef.current = lastIncoming.time;
      return;
    }

    // Append-only path — only the last bar (and possibly the previous one)
    // changed. Push the latest two via update() to keep the prior bar fully
    // resolved and the latest in-progress.
    const tail = candles.slice(-2);
    for (const bar of tail) {
      candle.update(toCandleDatum(bar));
      if (volume && bar.volume !== undefined) {
        volume.update(toVolumeDatum(bar));
      }
    }
    lastTimeRef.current = lastIncoming.time;
  }, [candles, ready]);

  // ---- Header summary line: last close, change, time ----
  const summary = useMemo(() => {
    if (candles.length === 0) return null;
    const last = candles[candles.length - 1];
    const prev = candles.length > 1 ? candles[candles.length - 2] : null;
    const change = prev ? (last.close - prev.close) / prev.close : 0;
    return { last: last.close, change };
  }, [candles]);

  // ---- Render ----
  return (
    <div
      className={cn(
        "flex flex-col rounded-md border border-border-subtle bg-bg-panel overflow-hidden",
        className
      )}
      data-mode-hint="hot"
      role="region"
      aria-label={`${symbol} candle chart, ${timeframe}`}
      {...props}
    >
      {/* Header */}
      <header className="flex items-center gap-3 px-3 h-10 border-b border-border-subtle">
        <div role="tablist" aria-label="Timeframe" className="flex items-center gap-0.5">
          {timeframes.map((tf) => {
            const active = tf === timeframe;
            return (
              <button
                key={tf}
                type="button"
                role="tab"
                aria-selected={active}
                onClick={() => onTimeframeChange?.(tf)}
                className={cn(
                  "h-7 px-2 text-[12px] font-medium num-tabular rounded-sm transition-colors",
                  "focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent-500",
                  active
                    ? "text-fg border-b-2 border-accent-500 -mb-px"
                    : "text-fg-muted hover:text-fg-secondary hover:bg-bg-rowhover"
                )}
              >
                {tf}
              </button>
            );
          })}
        </div>
        <div className="text-[12px] text-fg-secondary num-tabular truncate">
          {symbolSlot ?? <span className="font-mono">{symbol}</span>}
        </div>
        <div className="ml-auto flex items-center gap-2">
          {summary && (
            <span className="text-[11px] num-tabular text-fg-muted">
              last{" "}
              <span className="font-mono text-fg">
                {formatPrice(summary.last)}
              </span>{" "}
              <span
                className={cn(
                  "font-mono",
                  summary.change >= 0 ? "text-bid-300" : "text-ask-300"
                )}
              >
                {summary.change >= 0 ? "+" : ""}
                {(summary.change * 100).toFixed(2)}%
              </span>
            </span>
          )}
          {statusSlot ?? (
            <Pill
              intent={mode === "live" ? "bid" : "neutral"}
              icon={
                <StatusDot
                  state={mode === "live" ? "live" : "idle"}
                  size={6}
                  pulse={mode === "live"}
                />
              }
            >
              {mode === "live" ? "live" : "replay"}
            </Pill>
          )}
        </div>
      </header>

      {/* Plot area */}
      <div className="relative" style={{ height: plotHeight }}>
        {withDrawingTools && (
          <div className="absolute top-2 left-2 z-10 flex flex-col items-center gap-1.5 rounded-sm border border-border-subtle bg-bg-canvas/80 backdrop-blur-sm p-1.5">
            <button
              type="button"
              disabled
              aria-disabled
              title="Drawing tools — Pending v2"
              className="w-6 h-6 flex items-center justify-center text-fg-muted cursor-not-allowed"
            >
              <Pencil className="w-3.5 h-3.5" strokeWidth={1.5} aria-hidden />
            </button>
            <Tag intent="warn">v2</Tag>
          </div>
        )}

        <div ref={containerRef} className="w-full h-full" aria-hidden />

        {loading && (
          <div className="absolute inset-0 flex items-center justify-center pointer-events-none">
            <div className="flex items-center gap-2 text-[12px] text-fg-muted bg-bg-panel/80 px-3 py-1.5 rounded-sm">
              <Loader2 className="w-3.5 h-3.5 animate-spin" aria-hidden />
              Loading candles…
            </div>
          </div>
        )}

        {!loading && error && (
          <div className="absolute inset-0 flex items-center justify-center pointer-events-none">
            <p className="text-[12px] text-ask-400">{error}</p>
          </div>
        )}

        {!loading && !error && candles.length === 0 && (
          <div className="absolute inset-0 flex items-center justify-center pointer-events-none">
            <p className="text-[12px] text-fg-muted">{emptyMessage}</p>
          </div>
        )}
      </div>

      {/* Optional DepthChart strip — Pending v2 (the spec calls for the
          existing DepthChart component composed below the price pane; we
          surface the affordance and tag it for now). */}
      {withDepthChart && (
        <div className="border-t border-border-subtle px-3 py-2 flex items-center gap-2">
          <Tag intent="warn">DepthChart Pending</Tag>
          <span className="text-[11px] text-fg-muted">
            Inline depth strip composes the existing DepthChart component;
            wiring lands with Hot Trading (6.5).
          </span>
        </div>
      )}
    </div>
  );
}

/* -------------------------- Token reading -------------------------------- */

interface ChartTokens {
  bg: string;
  text: string;
  textMuted: string;
  borderSubtle: string;
  bid: string;
  ask: string;
  bidVolume: string;
  askVolume: string;
  crosshair: string;
}

function readTokens(): ChartTokens {
  if (typeof window === "undefined") return FALLBACK_TOKENS;
  const root = document.documentElement;
  const cs = window.getComputedStyle(root);
  const get = (v: string) => cs.getPropertyValue(v).trim();

  // The token CSS is OKLCH-based; lightweight-charts wants color strings it
  // can parse — modern browsers accept color() and oklch() in canvas paint
  // contexts via the CSS Houdini fallback chain. If a token isn't resolved
  // we fall back to safe defaults.
  return {
    bg: get("--color-bg-panel") || FALLBACK_TOKENS.bg,
    text: get("--color-fg") || FALLBACK_TOKENS.text,
    textMuted: get("--color-fg-muted") || FALLBACK_TOKENS.textMuted,
    borderSubtle: get("--color-border-subtle") || FALLBACK_TOKENS.borderSubtle,
    bid: get("--color-bid-500") || FALLBACK_TOKENS.bid,
    ask: get("--color-ask-500") || FALLBACK_TOKENS.ask,
    bidVolume: `color-mix(in oklch, ${get("--color-bid-500") || FALLBACK_TOKENS.bid} 50%, transparent)`,
    askVolume: `color-mix(in oklch, ${get("--color-ask-500") || FALLBACK_TOKENS.ask} 50%, transparent)`,
    crosshair: get("--color-neutral-400") || FALLBACK_TOKENS.crosshair,
  };
}

const FALLBACK_TOKENS: ChartTokens = {
  bg: "rgba(0,0,0,0)",
  text: "#e4e4e7",
  textMuted: "#9ca3af",
  borderSubtle: "rgba(255,255,255,0.08)",
  bid: "#22c55e",
  ask: "#ef4444",
  bidVolume: "rgba(34,197,94,0.5)",
  askVolume: "rgba(239,68,68,0.5)",
  crosshair: "#9ca3af",
};

/* -------------------------- Library option builders ---------------------- */

function baseChartOptions(t: ChartTokens): DeepPartial<ChartOptions> {
  return {
    layout: {
      background: { color: t.bg },
      textColor: t.textMuted,
      fontFamily: "var(--font-mono)",
      fontSize: 11,
    },
    grid: {
      vertLines: { color: "transparent" },
      horzLines: { color: t.borderSubtle },
    },
    crosshair: {
      mode: 1, // Magnet
      vertLine: { color: t.crosshair, style: 2, width: 1 },
      horzLine: { color: t.crosshair, style: 2, width: 1 },
    },
    rightPriceScale: {
      borderColor: t.borderSubtle,
    },
    timeScale: {
      borderColor: t.borderSubtle,
      timeVisible: true,
      secondsVisible: false,
    },
    autoSize: false,
  };
}

function candleOptions(t: ChartTokens) {
  return {
    upColor: t.bid,
    downColor: t.ask,
    borderUpColor: t.bid,
    borderDownColor: t.ask,
    wickUpColor: t.bid,
    wickDownColor: t.ask,
  };
}

function volumeOptions() {
  return {
    priceFormat: { type: "volume" as const },
    priceScaleId: "volume",
    color: "rgba(255,255,255,0.4)",
  };
}

/* -------------------------- Data adapters -------------------------------- */

function toCandleData(rows: PriceChartCandle[]): CandlestickData[] {
  return rows.map(toCandleDatum);
}

function toCandleDatum(r: PriceChartCandle): CandlestickData {
  return {
    time: msToLwcTime(r.time),
    open: r.open,
    high: r.high,
    low: r.low,
    close: r.close,
  };
}

function toVolumeData(rows: PriceChartCandle[]): HistogramData[] {
  return rows
    .filter((r) => r.volume !== undefined)
    .map(toVolumeDatum);
}

function toVolumeDatum(r: PriceChartCandle): HistogramData {
  const up = r.close >= r.open;
  return {
    time: msToLwcTime(r.time),
    value: r.volume ?? 0,
    color: up
      ? "color-mix(in oklch, var(--color-bid-500) 50%, transparent)"
      : "color-mix(in oklch, var(--color-ask-500) 50%, transparent)",
  };
}

/** lightweight-charts wants seconds since epoch (UTCTimestamp). Floor to int. */
function msToLwcTime(ms: number): Time {
  return Math.floor(ms / 1000) as Time;
}

function formatPrice(n: number): string {
  if (!Number.isFinite(n)) return "—";
  if (Math.abs(n) >= 1000) return n.toLocaleString(undefined, { maximumFractionDigits: 2 });
  if (Math.abs(n) >= 1) return n.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 4 });
  return n.toLocaleString(undefined, { minimumFractionDigits: 4, maximumFractionDigits: 6 });
}

export default PriceChart;
