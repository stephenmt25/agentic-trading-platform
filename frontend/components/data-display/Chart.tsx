"use client";

import {
  useCallback,
  useEffect,
  useId,
  useMemo,
  useRef,
  useState,
  type KeyboardEvent,
  type PointerEvent as ReactPointerEvent,
  type ReactNode,
} from "react";
import { cn } from "@/lib/utils";

/* ----------------------------------------------------------------------- */
/* Types                                                                    */
/* ----------------------------------------------------------------------- */

export type ChartTone = "bid" | "ask" | "accent" | "neutral" | "auto";
export type ChartShape = "line" | "area" | "bar";
export type ChartXType = "time" | "numeric" | "categorical";
export type ChartYScale = "linear" | "log" | "signed-symmetric";
export type ChartDensity = "compact" | "standard" | "comfortable";
export type ChartLegend = "auto" | "always" | "never";
export type ChartTooltip = "crosshair" | "nearest" | "none";
export type ChartAxes = "both" | "x-only" | "y-only" | "none";
export type ChartGridLines = "horizontal" | "none" | "both";
export type ChartStrokeStyle = "solid" | "dashed" | "dotted";

export interface ChartPoint {
  x: number | string | Date;
  y: number;
}

export interface ChartSeries {
  id: string;
  label?: string;
  shape?: ChartShape;
  tone?: ChartTone;
  data: ChartPoint[];
  /** Baseline for area shape: numeric value, "zero", or "min" (default "min"). */
  baseline?: number | "zero" | "min";
  /** Stroke style for differentiation in compare views (default "solid"). */
  stroke?: ChartStrokeStyle;
}

export interface ChartProps {
  series: ChartSeries[];
  /**
   * Required: a one-line summary read by screen readers. Spec example:
   * "Equity curve from 10,000 USDC to 11,430 USDC over 113 days".
   */
  ariaLabel: string;
  title?: ReactNode;
  axes?: ChartAxes;
  gridLines?: ChartGridLines;
  xType?: ChartXType;
  yScale?: ChartYScale;
  legend?: ChartLegend;
  tooltip?: ChartTooltip;
  density?: ChartDensity;
  barLayout?: "grouped" | "stacked";
  /** Render at most N x-positions; min/max bucket downsampling. */
  downsample?: number;
  /** Render at 60% opacity (compare view non-baseline). */
  dimmed?: boolean;
  /**
   * Render a visually-hidden table after the SVG so screen readers can
   * read every point. Required for the equity-curve usage in Backtesting.
   */
  tableFallback?: boolean;
  loading?: boolean;
  error?: string;
  emptyMessage?: string;
  formatY?: (v: number) => string;
  formatX?: (v: number | string | Date) => string;
  yTickCount?: number;
  xTickCount?: number;
  className?: string;
}

/* ----------------------------------------------------------------------- */
/* Tokens                                                                   */
/* ----------------------------------------------------------------------- */

const TONE_STROKE: Record<Exclude<ChartTone, "auto">, string> = {
  bid: "var(--color-bid-500)",
  ask: "var(--color-ask-500)",
  accent: "var(--color-accent-500)",
  neutral: "var(--color-neutral-300)",
};

const TONE_FILL: Record<Exclude<ChartTone, "auto">, string> = {
  bid: "var(--color-bid-500)",
  ask: "var(--color-ask-500)",
  accent: "var(--color-accent-500)",
  neutral: "var(--color-neutral-700)",
};

const TONE_FILL_OPACITY: Record<Exclude<ChartTone, "auto">, number> = {
  bid: 0.12,
  ask: 0.12,
  accent: 0.12,
  neutral: 0.4,
};

const DENSITY_HEIGHT: Record<ChartDensity, number> = {
  compact: 160,
  standard: 240,
  comfortable: 320,
};

const STROKE_DASHARRAY: Record<ChartStrokeStyle, string | undefined> = {
  solid: undefined,
  dashed: "5 3",
  dotted: "1.5 3",
};

/* ----------------------------------------------------------------------- */
/* Helpers                                                                  */
/* ----------------------------------------------------------------------- */

function toX(value: number | string | Date, xType: ChartXType): number {
  if (xType === "time") {
    if (value instanceof Date) return value.getTime();
    if (typeof value === "string") return Date.parse(value);
    return value;
  }
  if (xType === "categorical") {
    return typeof value === "number" ? value : 0;
  }
  return typeof value === "number" ? value : Number(value);
}

function resolveTone(tone: ChartTone | undefined, sampleY: number): Exclude<ChartTone, "auto"> {
  if (tone === undefined) return "accent";
  if (tone === "auto") {
    if (sampleY > 0) return "bid";
    if (sampleY < 0) return "ask";
    return "neutral";
  }
  return tone;
}

/**
 * Min/max bucket downsample. For each of N buckets, emit the min and max
 * y-value (as separate points, in original order). This preserves visual
 * extremes — what matters for line/area rendering — without DOM cost.
 */
function downsampleSeries(data: ChartPoint[], target: number): ChartPoint[] {
  if (data.length <= target) return data;
  const buckets = Math.max(2, Math.floor(target / 2));
  const bucketSize = data.length / buckets;
  const out: ChartPoint[] = [];
  for (let i = 0; i < buckets; i++) {
    const start = Math.floor(i * bucketSize);
    const end = Math.min(data.length, Math.floor((i + 1) * bucketSize));
    if (start >= end) continue;
    let minIdx = start;
    let maxIdx = start;
    for (let j = start + 1; j < end; j++) {
      if (data[j].y < data[minIdx].y) minIdx = j;
      if (data[j].y > data[maxIdx].y) maxIdx = j;
    }
    if (minIdx === maxIdx) {
      out.push(data[minIdx]);
    } else if (minIdx < maxIdx) {
      out.push(data[minIdx], data[maxIdx]);
    } else {
      out.push(data[maxIdx], data[minIdx]);
    }
  }
  return out;
}

/** "Nice number" tick generation — pick rounded steps that include extremes. */
function niceTicks(min: number, max: number, count: number): number[] {
  if (!Number.isFinite(min) || !Number.isFinite(max) || min === max) {
    return [min];
  }
  const range = max - min;
  const step = niceStep(range / Math.max(1, count - 1));
  const start = Math.ceil(min / step) * step;
  const ticks: number[] = [];
  for (let v = start; v <= max + step / 2; v += step) {
    ticks.push(Number(v.toFixed(10)));
    if (ticks.length > count + 2) break;
  }
  return ticks;
}

function niceStep(rough: number): number {
  if (rough <= 0 || !Number.isFinite(rough)) return 1;
  const exp = Math.floor(Math.log10(rough));
  const f = rough / Math.pow(10, exp);
  let nice: number;
  if (f < 1.5) nice = 1;
  else if (f < 3) nice = 2;
  else if (f < 7) nice = 5;
  else nice = 10;
  return nice * Math.pow(10, exp);
}

function formatNumberShort(v: number): string {
  if (!Number.isFinite(v)) return "—";
  const abs = Math.abs(v);
  if (abs >= 1_000_000) return `${(v / 1_000_000).toFixed(1)}M`;
  if (abs >= 10_000) return `${(v / 1_000).toFixed(0)}k`;
  if (abs >= 1_000) return `${(v / 1_000).toFixed(1)}k`;
  if (abs >= 1) return v.toFixed(2);
  return v.toFixed(3);
}

function defaultFormatY(v: number): string {
  return formatNumberShort(v);
}

function defaultFormatX(v: number | string | Date, xType: ChartXType): string {
  if (xType === "time") {
    const ms = v instanceof Date ? v.getTime() : typeof v === "string" ? Date.parse(v) : v;
    if (!Number.isFinite(ms)) return String(v);
    const d = new Date(ms);
    return `${d.getUTCFullYear()}-${String(d.getUTCMonth() + 1).padStart(2, "0")}-${String(
      d.getUTCDate()
    ).padStart(2, "0")}`;
  }
  if (xType === "categorical") return String(v);
  return typeof v === "number" ? v.toLocaleString() : String(v);
}

/* ----------------------------------------------------------------------- */
/* Component                                                                */
/* ----------------------------------------------------------------------- */

/**
 * Chart per `docs/design/04-component-specs/chart.md`. A general-purpose
 * XY chart for line / area / bar series, COOL-mode focused. Sits alongside
 * `Sparkline` — Sparkline is shape-only and inline; Chart is full-blown
 * with axes, gridlines, legend, and crosshair tooltip.
 *
 * Not for OHLC candlesticks — that's the deferred `PriceChart`. Not for
 * heatmaps. Don't reach for chromatic series colors outside the bid /
 * ask / accent / neutral palette.
 *
 * Hand-rolled SVG path generation (no d3 / recharts / chart.js); follows
 * the same SVG-first pattern as `Sparkline`.
 */
export function Chart({
  series,
  ariaLabel,
  title,
  axes = "both",
  gridLines = "horizontal",
  xType = "numeric",
  yScale = "linear",
  legend = "auto",
  tooltip = "crosshair",
  density = "standard",
  // `barLayout` is in the spec for grouped/stacked bars but not yet
  // wired — bars render as a single grouped series. Prop is kept on the
  // type so callers won't need to migrate when it lands.
  downsample,
  dimmed = false,
  tableFallback = false,
  loading = false,
  error,
  emptyMessage = "No data",
  formatY,
  formatX,
  yTickCount = 5,
  xTickCount = 6,
  className,
}: ChartProps) {
  const id = useId();
  const containerRef = useRef<HTMLDivElement | null>(null);
  const [containerWidth, setContainerWidth] = useState(800);
  const [hoverIndex, setHoverIndex] = useState<number | null>(null);
  const [focused, setFocused] = useState(false);
  const liveRegionRef = useRef<HTMLDivElement | null>(null);

  const height = DENSITY_HEIGHT[density];

  // ResizeObserver: track container width so the chart fills its parent
  // without distorting line geometry (preserveAspectRatio="none" would
  // squish the strokes).
  useEffect(() => {
    const el = containerRef.current;
    if (!el) return;
    const ro = new ResizeObserver((entries) => {
      for (const entry of entries) {
        const w = entry.contentRect.width;
        if (w > 0 && Math.abs(w - containerWidth) > 1) {
          setContainerWidth(w);
        }
      }
    });
    ro.observe(el);
    return () => ro.disconnect();
  }, [containerWidth]);

  // Plot-area margins. Trimmed when an axis is suppressed.
  const margin = useMemo(() => {
    const showY = axes === "both" || axes === "y-only";
    const showX = axes === "both" || axes === "x-only";
    return {
      top: 12,
      right: 12,
      bottom: showX ? (density === "compact" ? 22 : 28) : 8,
      left: showY ? (density === "compact" ? 36 : 44) : 8,
    };
  }, [axes, density]);

  const width = containerWidth;
  const innerW = Math.max(40, width - margin.left - margin.right);
  const innerH = Math.max(40, height - margin.top - margin.bottom);

  // Downsample per-series before scaling. The spec requires this for any
  // series with > 2,000 points.
  const processedSeries = useMemo<ChartSeries[]>(() => {
    if (!series.length) return [];
    return series.map((s) => {
      if (downsample && s.data.length > downsample) {
        return { ...s, data: downsampleSeries(s.data, downsample) };
      }
      return s;
    });
  }, [series, downsample]);

  const allPoints = useMemo(
    () => processedSeries.flatMap((s) => s.data),
    [processedSeries]
  );

  const isEmpty = allPoints.length === 0;

  // X domain. Bars are categorical-by-band; line/area can be time/numeric.
  const xDomain = useMemo(() => {
    if (allPoints.length === 0) return { min: 0, max: 1, count: 0 };
    let min = Infinity;
    let max = -Infinity;
    let count = 0;
    for (const p of allPoints) {
      const xv = toX(p.x, xType);
      if (Number.isFinite(xv)) {
        if (xv < min) min = xv;
        if (xv > max) max = xv;
        count++;
      }
    }
    if (!Number.isFinite(min) || !Number.isFinite(max) || min === max) {
      return { min: 0, max: Math.max(1, count - 1), count };
    }
    return { min, max, count };
  }, [allPoints, xType]);

  // Y domain.
  const yDomain = useMemo(() => {
    if (allPoints.length === 0) return { min: 0, max: 1 };
    let min = Infinity;
    let max = -Infinity;
    for (const p of allPoints) {
      if (Number.isFinite(p.y)) {
        if (p.y < min) min = p.y;
        if (p.y > max) max = p.y;
      }
    }
    if (!Number.isFinite(min) || !Number.isFinite(max)) {
      return { min: 0, max: 1 };
    }
    if (yScale === "signed-symmetric") {
      const m = Math.max(Math.abs(min), Math.abs(max));
      return { min: -m, max: m };
    }
    if (min === max) {
      const pad = Math.abs(min) * 0.1 || 1;
      return { min: min - pad, max: max + pad };
    }
    // 6% headroom above + below so strokes don't kiss the plot edges.
    const pad = (max - min) * 0.06;
    return { min: min - pad, max: max + pad };
  }, [allPoints, yScale]);

  const xToPx = useCallback(
    (v: number | string | Date): number => {
      const xv = toX(v, xType);
      if (xDomain.max === xDomain.min) return margin.left + innerW / 2;
      const t = (xv - xDomain.min) / (xDomain.max - xDomain.min);
      return margin.left + t * innerW;
    },
    [xDomain, xType, margin.left, innerW]
  );

  const yToPx = useCallback(
    (v: number): number => {
      let t: number;
      if (yScale === "log") {
        const min = Math.max(yDomain.min, Number.MIN_VALUE);
        const max = Math.max(yDomain.max, Number.MIN_VALUE);
        const lv = Math.log(Math.max(v, Number.MIN_VALUE));
        const lmin = Math.log(min);
        const lmax = Math.log(max);
        t = lmax === lmin ? 0.5 : (lv - lmin) / (lmax - lmin);
      } else {
        t = yDomain.max === yDomain.min ? 0.5 : (v - yDomain.min) / (yDomain.max - yDomain.min);
      }
      return margin.top + (1 - t) * innerH;
    },
    [yDomain, yScale, margin.top, innerH]
  );

  // Y ticks
  const yTicks = useMemo(
    () => niceTicks(yDomain.min, yDomain.max, yTickCount),
    [yDomain, yTickCount]
  );

  // X ticks (numeric / time only — categorical uses series indices)
  const xTicks = useMemo(() => {
    if (xType === "categorical" || allPoints.length === 0) return [];
    return niceTicks(xDomain.min, xDomain.max, xTickCount);
  }, [xType, xDomain, xTickCount, allPoints.length]);

  // Path builders
  const buildLinePath = useCallback(
    (data: ChartPoint[]): string => {
      if (data.length < 2) {
        if (data.length === 1) {
          const x = xToPx(data[0].x);
          const y = yToPx(data[0].y);
          return `M${x.toFixed(2)},${y.toFixed(2)} L${x.toFixed(2)},${y.toFixed(2)}`;
        }
        return "";
      }
      let d = "";
      for (let i = 0; i < data.length; i++) {
        const x = xToPx(data[i].x).toFixed(2);
        const y = yToPx(data[i].y).toFixed(2);
        d += `${i === 0 ? "M" : "L"}${x},${y} `;
      }
      return d.trim();
    },
    [xToPx, yToPx]
  );

  const buildAreaPath = useCallback(
    (data: ChartPoint[], baseline: number | "zero" | "min"): string => {
      if (data.length < 2) return "";
      const base = baseline === "zero" ? 0 : baseline === "min" ? yDomain.min : baseline;
      const baseY = yToPx(base).toFixed(2);
      const top: string[] = [];
      for (let i = 0; i < data.length; i++) {
        const x = xToPx(data[i].x).toFixed(2);
        const y = yToPx(data[i].y).toFixed(2);
        top.push(`${i === 0 ? "M" : "L"}${x},${y}`);
      }
      const lastX = xToPx(data[data.length - 1].x).toFixed(2);
      const firstX = xToPx(data[0].x).toFixed(2);
      return `${top.join(" ")} L${lastX},${baseY} L${firstX},${baseY} Z`;
    },
    [xToPx, yToPx, yDomain]
  );

  // Shared x-bucket axis for crosshair tooltip. We use series[0]'s data as
  // the index reference (common case: backtest equity curves are aligned
  // by sample index across runs). For mixed cases, callers pass xType=
  // "numeric" and the nearest-x lookup per series falls back below.
  const referenceData = useMemo(
    () => processedSeries[0]?.data ?? [],
    [processedSeries]
  );
  const bucketCount = referenceData.length;

  const showLegend =
    legend === "always" || (legend === "auto" && processedSeries.length >= 2);

  /* ------- pointer + keyboard interaction ------------------------------- */

  const onPointerMove = useCallback(
    (e: ReactPointerEvent<HTMLDivElement>) => {
      if (tooltip === "none" || bucketCount === 0) return;
      const rect = e.currentTarget.getBoundingClientRect();
      const x = e.clientX - rect.left;
      const plotX = x - margin.left;
      if (plotX < 0 || plotX > innerW) {
        setHoverIndex(null);
        return;
      }
      const t = innerW === 0 ? 0 : plotX / innerW;
      const idx = Math.round(t * (bucketCount - 1));
      setHoverIndex(Math.max(0, Math.min(bucketCount - 1, idx)));
    },
    [tooltip, bucketCount, margin.left, innerW]
  );

  const onPointerLeave = useCallback(() => setHoverIndex(null), []);

  const onKeyDown = useCallback(
    (e: KeyboardEvent<HTMLDivElement>) => {
      if (tooltip === "none" || bucketCount === 0) return;
      if (e.key === "Escape") {
        setHoverIndex(null);
        e.currentTarget.blur();
        return;
      }
      if (e.key === "Home") {
        e.preventDefault();
        setHoverIndex(0);
        return;
      }
      if (e.key === "End") {
        e.preventDefault();
        setHoverIndex(bucketCount - 1);
        return;
      }
      if (e.key === "ArrowLeft" || e.key === "ArrowRight") {
        e.preventDefault();
        const dir = e.key === "ArrowRight" ? 1 : -1;
        setHoverIndex((prev) => {
          const cur = prev ?? 0;
          return Math.max(0, Math.min(bucketCount - 1, cur + dir));
        });
      }
    },
    [tooltip, bucketCount]
  );

  // Polite live region: when crosshair moves under keyboard control, read
  // the values to assistive tech.
  useEffect(() => {
    if (!focused || hoverIndex == null || !liveRegionRef.current) return;
    const fmtY = formatY ?? defaultFormatY;
    const fmtX = formatX ?? ((v: number | string | Date) => defaultFormatX(v, xType));
    const xLabel = referenceData[hoverIndex]?.x;
    const parts: string[] = [];
    if (xLabel !== undefined) parts.push(String(fmtX(xLabel)));
    for (const s of processedSeries) {
      const pt = s.data[hoverIndex];
      if (pt) {
        parts.push(`${s.label ?? s.id}: ${fmtY(pt.y)}`);
      }
    }
    liveRegionRef.current.textContent = parts.join(", ");
  }, [focused, hoverIndex, processedSeries, referenceData, formatX, formatY, xType]);

  /* ------- render ------------------------------------------------------- */

  return (
    <div
      ref={containerRef}
      className={cn("w-full flex flex-col", className)}
    >
      {(title || showLegend) && (
        <div className="flex items-center justify-between gap-3 mb-1.5">
          {title ? (
            <div className="text-[13px] text-fg num-tabular leading-none">{title}</div>
          ) : (
            <span />
          )}
          {showLegend && (
            <div className="flex items-center gap-3 text-[12px] text-fg-secondary">
              {processedSeries.map((s) => {
                const tone = resolveTone(s.tone, s.data[0]?.y ?? 0);
                return (
                  <span key={s.id} className="inline-flex items-center gap-1.5">
                    <span
                      aria-hidden
                      className="inline-block w-3 h-[2px] rounded-sm"
                      style={{
                        background: TONE_STROKE[tone],
                        ...(s.stroke && s.stroke !== "solid"
                          ? {
                              borderTop: `2px ${
                                s.stroke === "dashed" ? "dashed" : "dotted"
                              } ${TONE_STROKE[tone]}`,
                              background: "transparent",
                              height: 0,
                            }
                          : {}),
                      }}
                    />
                    <span>{s.label ?? s.id}</span>
                  </span>
                );
              })}
            </div>
          )}
        </div>
      )}

      <div
        role="img"
        aria-label={ariaLabel}
        tabIndex={tooltip === "none" ? -1 : 0}
        onFocus={() => setFocused(true)}
        onBlur={() => {
          setFocused(false);
          setHoverIndex(null);
        }}
        onPointerMove={onPointerMove}
        onPointerLeave={onPointerLeave}
        onKeyDown={onKeyDown}
        className={cn(
          "relative outline-none",
          "focus-visible:ring-1 focus-visible:ring-accent-500 rounded-sm",
          dimmed && "opacity-60"
        )}
        style={{ height }}
      >
        <svg
          width={width}
          height={height}
          role="presentation"
          aria-hidden
          className="block"
        >
          <defs>
            {processedSeries.map((s) => {
              const tone = resolveTone(s.tone, s.data[0]?.y ?? 0);
              return (
                <linearGradient
                  key={`grad-${s.id}-${id}`}
                  id={`chart-fill-${id}-${s.id}`}
                  x1="0"
                  y1="0"
                  x2="0"
                  y2="1"
                >
                  <stop
                    offset="0%"
                    stopColor={TONE_FILL[tone]}
                    stopOpacity={TONE_FILL_OPACITY[tone]}
                  />
                  <stop offset="100%" stopColor={TONE_FILL[tone]} stopOpacity={0} />
                </linearGradient>
              );
            })}
            <clipPath id={`chart-clip-${id}`}>
              <rect
                x={margin.left}
                y={margin.top}
                width={innerW}
                height={innerH}
              />
            </clipPath>
          </defs>

          {/* Gridlines */}
          {gridLines !== "none" &&
            yTicks.map((t, i) => {
              const y = yToPx(t);
              return (
                <line
                  key={`ygrid-${i}`}
                  x1={margin.left}
                  x2={margin.left + innerW}
                  y1={y}
                  y2={y}
                  stroke="var(--color-border-subtle)"
                  strokeWidth={0.5}
                />
              );
            })}
          {gridLines === "both" &&
            xTicks.map((t, i) => {
              const x = xToPx(t);
              return (
                <line
                  key={`xgrid-${i}`}
                  x1={x}
                  x2={x}
                  y1={margin.top}
                  y2={margin.top + innerH}
                  stroke="var(--color-border-subtle)"
                  strokeWidth={0.5}
                />
              );
            })}

          {/* Series */}
          {!isEmpty && !loading && !error && (
            <g clipPath={`url(#chart-clip-${id})`}>
              {processedSeries.map((s) => {
                const tone = resolveTone(s.tone, s.data[0]?.y ?? 0);
                const stroke = TONE_STROKE[tone];
                const dasharray = STROKE_DASHARRAY[s.stroke ?? "solid"];
                const strokeWidth = processedSeries.length >= 3 ? 1 : 1.25;
                const shape: ChartShape = s.shape ?? "line";

                if (shape === "bar") {
                  const bandWidth =
                    s.data.length > 1
                      ? Math.max(2, (innerW / s.data.length) * 0.6)
                      : Math.min(24, innerW * 0.4);
                  const baseY = yToPx(0);
                  return (
                    <g key={`series-${s.id}`}>
                      {s.data.map((p, i) => {
                        const px = xToPx(p.x);
                        const py = yToPx(p.y);
                        const top = Math.min(py, baseY);
                        const h = Math.abs(py - baseY);
                        const barTone =
                          s.tone === "auto" ? resolveTone("auto", p.y) : tone;
                        return (
                          <rect
                            key={`bar-${s.id}-${i}`}
                            x={px - bandWidth / 2}
                            y={top}
                            width={bandWidth}
                            height={Math.max(0.5, h)}
                            fill={TONE_FILL[barTone]}
                            opacity={0.9}
                          />
                        );
                      })}
                    </g>
                  );
                }

                const linePath = buildLinePath(s.data);
                const areaPath =
                  shape === "area"
                    ? buildAreaPath(s.data, s.baseline ?? "min")
                    : null;

                return (
                  <g key={`series-${s.id}`}>
                    {areaPath && (
                      <path
                        d={areaPath}
                        fill={`url(#chart-fill-${id}-${s.id})`}
                        stroke="none"
                      />
                    )}
                    <path
                      d={linePath}
                      fill="none"
                      stroke={stroke}
                      strokeWidth={strokeWidth}
                      strokeDasharray={dasharray}
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      opacity={
                        hoverIndex != null && processedSeries.length >= 2
                          ? 1
                          : 1
                      }
                    />
                  </g>
                );
              })}
            </g>
          )}

          {/* Loading skeleton: pulsing baseline path */}
          {loading && !error && (
            <line
              x1={margin.left}
              x2={margin.left + innerW}
              y1={margin.top + innerH / 2}
              y2={margin.top + innerH / 2}
              stroke="var(--color-border-strong)"
              strokeWidth={1}
              strokeDasharray="4 4"
              className="animate-pulse"
            />
          )}

          {/* Y axis */}
          {(axes === "both" || axes === "y-only") &&
            yTicks.map((t, i) => {
              const y = yToPx(t);
              const fmt = formatY ?? defaultFormatY;
              return (
                <text
                  key={`ytick-${i}`}
                  x={margin.left - 6}
                  y={y}
                  textAnchor="end"
                  dominantBaseline="middle"
                  className="num-tabular"
                  style={{
                    fontSize: density === "compact" ? 10 : 11,
                    fill: "var(--color-fg-muted)",
                    fontFeatureSettings: '"tnum"',
                  }}
                >
                  {fmt(t)}
                </text>
              );
            })}

          {/* X axis */}
          {(axes === "both" || axes === "x-only") &&
            xTicks.map((t, i) => {
              const x = xToPx(t);
              const fmt = formatX ?? ((v: number | string | Date) => defaultFormatX(v, xType));
              return (
                <text
                  key={`xtick-${i}`}
                  x={x}
                  y={margin.top + innerH + (density === "compact" ? 12 : 16)}
                  textAnchor="middle"
                  className="num-tabular"
                  style={{
                    fontSize: density === "compact" ? 10 : 11,
                    fill: "var(--color-fg-muted)",
                    fontFeatureSettings: '"tnum"',
                  }}
                >
                  {fmt(t)}
                </text>
              );
            })}

          {/* Crosshair line */}
          {tooltip !== "none" && hoverIndex != null && referenceData[hoverIndex] != null && (() => {
            const x = xToPx(referenceData[hoverIndex].x);
            return (
              <line
                x1={x}
                x2={x}
                y1={margin.top}
                y2={margin.top + innerH}
                stroke="var(--color-border-strong)"
                strokeWidth={0.5}
                strokeDasharray="3 3"
              />
            );
          })()}

          {/* Crosshair dots — one per series at hover index */}
          {tooltip !== "none" &&
            hoverIndex != null &&
            processedSeries.map((s) => {
              const pt = s.data[hoverIndex];
              if (!pt) return null;
              const tone = resolveTone(s.tone, pt.y);
              return (
                <circle
                  key={`dot-${s.id}`}
                  cx={xToPx(pt.x)}
                  cy={yToPx(pt.y)}
                  r={2.5}
                  fill={TONE_STROKE[tone]}
                  stroke="var(--color-bg-panel)"
                  strokeWidth={1}
                />
              );
            })}
        </svg>

        {/* Tooltip box */}
        {tooltip !== "none" &&
          hoverIndex != null &&
          referenceData[hoverIndex] != null && (
            <ChartTooltip
              x={xToPx(referenceData[hoverIndex].x)}
              y={margin.top}
              plotWidth={innerW}
              plotLeft={margin.left}
              xLabel={(formatX ?? ((v: number | string | Date) => defaultFormatX(v, xType)))(
                referenceData[hoverIndex].x
              )}
              entries={processedSeries.map((s) => {
                const pt = s.data[hoverIndex];
                const tone = resolveTone(s.tone, pt?.y ?? 0);
                return {
                  id: s.id,
                  label: s.label ?? s.id,
                  value: pt ? (formatY ?? defaultFormatY)(pt.y) : "—",
                  swatch: TONE_STROKE[tone],
                };
              })}
            />
          )}

        {/* Empty / error overlays */}
        {(isEmpty || error) && !loading && (
          <div
            className="absolute inset-0 flex items-center justify-center pointer-events-none"
            aria-hidden
          >
            <span
              className={cn(
                "text-[12px]",
                error ? "text-ask-400" : "text-fg-muted"
              )}
            >
              {error ?? emptyMessage}
            </span>
          </div>
        )}

        {/* Polite live region for keyboard crosshair narration */}
        <div
          ref={liveRegionRef}
          aria-live="polite"
          aria-atomic="true"
          className="sr-only"
        />
      </div>

      {/* Visually-hidden table for screen readers (full data dump) */}
      {tableFallback && !isEmpty && (
        <table className="sr-only">
          <caption>{ariaLabel}</caption>
          <thead>
            <tr>
              <th scope="col">x</th>
              {processedSeries.map((s) => (
                <th key={s.id} scope="col">
                  {s.label ?? s.id}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {referenceData.map((p, i) => (
              <tr key={`row-${i}`}>
                <th scope="row">
                  {(formatX ?? ((v: number | string | Date) => defaultFormatX(v, xType)))(p.x)}
                </th>
                {processedSeries.map((s) => {
                  const pt = s.data[i];
                  return (
                    <td key={`${s.id}-${i}`}>
                      {pt ? (formatY ?? defaultFormatY)(pt.y) : ""}
                    </td>
                  );
                })}
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}

/* ----------------------------------------------------------------------- */
/* Tooltip box                                                              */
/* ----------------------------------------------------------------------- */

interface TooltipEntry {
  id: string;
  label: string;
  value: string;
  swatch: string;
}

function ChartTooltip({
  x,
  y,
  plotWidth,
  plotLeft,
  xLabel,
  entries,
}: {
  x: number;
  y: number;
  plotWidth: number;
  plotLeft: number;
  xLabel: string;
  entries: TooltipEntry[];
}) {
  // Tooltip box width estimate; flip to the left of the crosshair when
  // we'd otherwise overflow the plot area.
  const estW = 160;
  const flip = x + 12 + estW > plotLeft + plotWidth;
  const left = flip ? x - 12 - estW : x + 12;

  return (
    <div
      role="tooltip"
      className={cn(
        "absolute pointer-events-none z-10",
        "rounded-sm border border-border-subtle bg-bg-raised",
        "px-2.5 py-1.5 shadow-[var(--shadow-popover)]"
      )}
      style={{ left, top: y, minWidth: 100, maxWidth: estW }}
    >
      <div className="text-[10px] uppercase tracking-wider text-fg-muted num-tabular leading-none mb-1">
        {xLabel}
      </div>
      <div className="flex flex-col gap-0.5">
        {entries.map((e) => (
          <div
            key={e.id}
            className="flex items-center justify-between gap-3 text-[12px] leading-tight"
          >
            <span className="inline-flex items-center gap-1.5 min-w-0">
              <span
                aria-hidden
                className="inline-block w-2 h-2 rounded-sm shrink-0"
                style={{ background: e.swatch }}
              />
              <span className="truncate text-fg-secondary">{e.label}</span>
            </span>
            <span className="font-mono num-tabular text-fg shrink-0">
              {e.value}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}

export default Chart;
