"use client";

import { useId, type SVGAttributes } from "react";
import { cn } from "@/lib/utils";

/**
 * DepthChart per docs/design/04-component-specs/trading-specific.md.
 *
 * XY chart, x = price, y = cumulative size. Two stepped curves:
 *   - bid (left of mid, descending price)
 *   - ask (right of mid, ascending price)
 * Filled below the line in the side color at 15% alpha. Mid marker
 * as a vertical dotted line.
 *
 * Per spec: NO grid lines. The shape of the depth curve IS the data.
 *
 * Inputs are pre-aggregated levels — caller controls aggregation/tick
 * size. The component does no bucketing of its own.
 */

export interface DepthLevel {
  price: number;
  /** Liquidity available at this level (NOT cumulative — we cumulate). */
  size: number;
}

export interface DepthChartProps
  extends Omit<SVGAttributes<SVGSVGElement>, "width" | "height"> {
  bids: DepthLevel[];
  asks: DepthLevel[];
  /** Mid price. Defaults to (best-bid + best-ask) / 2. */
  mid?: number;
  width?: number;
  height?: number;
  /** Visible price range as a fraction of mid. e.g., 0.005 = ±0.5%.
   *  Special: "fit" uses full input range. */
  range?: number | "fit";
  /** Y-axis scale. */
  yScale?: "linear" | "log";
  /** Show numeric mid label above the line. */
  showMidLabel?: boolean;
}

interface CurvePoint {
  x: number;
  y: number;
}

function buildCumulative(
  levels: DepthLevel[],
  ascending: boolean
): { price: number; cum: number }[] {
  const sorted = [...levels].sort((a, b) =>
    ascending ? a.price - b.price : b.price - a.price
  );
  let cum = 0;
  return sorted.map((l) => {
    cum += l.size;
    return { price: l.price, cum };
  });
}

export function DepthChart({
  bids,
  asks,
  mid,
  width = 320,
  height = 120,
  range = 0.01,
  yScale = "linear",
  showMidLabel = false,
  className,
  ...props
}: DepthChartProps) {
  const id = useId();

  if (bids.length === 0 || asks.length === 0) {
    return (
      <svg
        width={width}
        height={height}
        viewBox={`0 0 ${width} ${height}`}
        aria-label="Depth chart (no data)"
        className={cn("inline-block", className)}
      >
        <line
          x1={width / 2}
          y1={0}
          x2={width / 2}
          y2={height}
          stroke="var(--color-neutral-700)"
          strokeWidth={1}
          strokeDasharray="2 3"
        />
      </svg>
    );
  }

  const bestBid = Math.max(...bids.map((b) => b.price));
  const bestAsk = Math.min(...asks.map((a) => a.price));
  const resolvedMid = mid ?? (bestBid + bestAsk) / 2;

  // Bids cumulate descending from mid, asks cumulate ascending.
  const bidCum = buildCumulative(bids, /* ascending */ false);
  const askCum = buildCumulative(asks, /* ascending */ true);

  const fitRange =
    range === "fit"
      ? Math.max(
          resolvedMid - Math.min(...bidCum.map((b) => b.price)),
          Math.max(...askCum.map((a) => a.price)) - resolvedMid
        )
      : resolvedMid * range;

  const xMin = resolvedMid - fitRange;
  const xMax = resolvedMid + fitRange;

  const visibleBids = bidCum.filter(
    (b) => b.price >= xMin && b.price <= xMax
  );
  const visibleAsks = askCum.filter(
    (a) => a.price >= xMin && a.price <= xMax
  );

  const yMaxRaw = Math.max(
    ...visibleBids.map((b) => b.cum),
    ...visibleAsks.map((a) => a.cum),
    1
  );
  const yMax = yScale === "log" ? Math.log10(yMaxRaw + 1) : yMaxRaw;

  const px = (price: number) =>
    ((price - xMin) / (xMax - xMin)) * width;
  const py = (cum: number) => {
    const v = yScale === "log" ? Math.log10(cum + 1) : cum;
    const top = 4;
    const bottom = height - 4;
    const ratio = v / yMax;
    return bottom - ratio * (bottom - top);
  };

  // Build stepped paths. For bids (descending), we step from price→price.
  // We anchor each curve to the mid x-coordinate at the running cum.
  const buildStepped = (
    points: { price: number; cum: number }[],
    side: "bid" | "ask"
  ): { line: string; area: string } => {
    if (points.length === 0) return { line: "", area: "" };

    // Bids: descending price away from mid; ask: ascending from mid.
    const sortedForDraw =
      side === "bid"
        ? [...points].sort((a, b) => b.price - a.price) // mid → far-left
        : [...points].sort((a, b) => a.price - b.price); // mid → far-right

    // Start from mid baseline at the first cum (anchor at the side).
    const midX = px(resolvedMid);

    const pts: CurvePoint[] = [];
    pts.push({ x: midX, y: py(sortedForDraw[0].cum) });
    for (const p of sortedForDraw) {
      const x = px(p.price);
      const y = py(p.cum);
      // Step: horizontal then vertical — gives the staircase look.
      const last = pts[pts.length - 1];
      pts.push({ x, y: last.y });
      pts.push({ x, y });
    }

    const line = pts
      .map((p, i) => `${i === 0 ? "M" : "L"}${p.x.toFixed(2)},${p.y.toFixed(2)}`)
      .join(" ");

    const baselineY = (height - 4).toFixed(2);
    const lastX = pts[pts.length - 1].x.toFixed(2);
    const firstX = pts[0].x.toFixed(2);
    const area = `${line} L${lastX},${baselineY} L${firstX},${baselineY} Z`;
    return { line, area };
  };

  const bid = buildStepped(visibleBids, "bid");
  const ask = buildStepped(visibleAsks, "ask");
  const midX = px(resolvedMid);
  const bidGradId = `dc-bid-${id}`;
  const askGradId = `dc-ask-${id}`;

  return (
    <svg
      width={width}
      height={height}
      viewBox={`0 0 ${width} ${height}`}
      role="img"
      aria-label={`Depth chart at mid ${resolvedMid.toLocaleString()}`}
      className={cn("inline-block", className)}
      {...props}
    >
      <defs>
        <linearGradient id={bidGradId} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor="var(--color-bid-500)" stopOpacity={0.22} />
          <stop offset="100%" stopColor="var(--color-bid-500)" stopOpacity={0.04} />
        </linearGradient>
        <linearGradient id={askGradId} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor="var(--color-ask-500)" stopOpacity={0.22} />
          <stop offset="100%" stopColor="var(--color-ask-500)" stopOpacity={0.04} />
        </linearGradient>
      </defs>

      {bid.area && <path d={bid.area} fill={`url(#${bidGradId})`} />}
      {ask.area && <path d={ask.area} fill={`url(#${askGradId})`} />}
      {bid.line && (
        <path
          d={bid.line}
          fill="none"
          stroke="var(--color-bid-500)"
          strokeWidth={1.25}
          strokeLinejoin="miter"
        />
      )}
      {ask.line && (
        <path
          d={ask.line}
          fill="none"
          stroke="var(--color-ask-500)"
          strokeWidth={1.25}
          strokeLinejoin="miter"
        />
      )}

      {/* Mid marker */}
      <line
        x1={midX}
        y1={0}
        x2={midX}
        y2={height}
        stroke="var(--color-neutral-400)"
        strokeWidth={1}
        strokeDasharray="2 3"
      />
      {showMidLabel && (
        <text
          x={midX}
          y={10}
          textAnchor="middle"
          className="num-tabular"
          fontFamily="var(--font-mono)"
          fontSize="9"
          fill="var(--color-neutral-400)"
        >
          {resolvedMid.toLocaleString()}
        </text>
      )}
    </svg>
  );
}

export default DepthChart;
