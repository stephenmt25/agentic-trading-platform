"use client";

import { useId, type SVGAttributes } from "react";
import { cn } from "@/lib/utils";

export interface SparklineProps
  extends Omit<SVGAttributes<SVGSVGElement>, "values" | "width" | "height"> {
  /** Series values. Trend direction is derived from first vs. last. */
  values: number[];
  width?: number;
  height?: number;
  /** Override automatic trend detection. */
  tone?: "bid" | "ask" | "neutral";
  area?: boolean;
  /** Faint horizontal line at the series midpoint. */
  withMid?: boolean;
}

const STROKE = {
  bid: "var(--color-bid-500)",
  ask: "var(--color-ask-500)",
  neutral: "var(--color-neutral-400)",
};

/**
 * Sparkline per data-display.md. SVG-based, no axes, no labels — pure
 * shape. Trend tone is auto-detected from first vs. last value but can
 * be overridden via `tone`. Last-point dot at end (1.5px radius).
 *
 * Don't label the y-axis. If precise values are needed, surface them in
 * an adjacent KeyValue or a Tooltip on hover (per spec).
 */
export function Sparkline({
  values,
  width = 96,
  height = 20,
  tone,
  area = false,
  withMid = false,
  className,
  ...props
}: SparklineProps) {
  const id = useId();
  const gradientId = `sparkline-fill-${id}`;

  if (!values || values.length < 2) {
    return (
      <svg
        width={width}
        height={height}
        className={cn("inline-block", className)}
        viewBox={`0 0 ${width} ${height}`}
        aria-hidden
      >
        <line
          x1={0}
          y1={height / 2}
          x2={width}
          y2={height / 2}
          stroke="var(--color-neutral-700)"
          strokeWidth={1}
        />
      </svg>
    );
  }

  const min = Math.min(...values);
  const max = Math.max(...values);
  const range = max - min || 1;
  const padding = 1.5; // keep stroke inside the box

  const xStep = (width - padding * 2) / (values.length - 1);
  const points = values.map((v, i) => {
    const x = padding + i * xStep;
    const y = padding + (height - padding * 2) * (1 - (v - min) / range);
    return [x, y] as const;
  });

  const path = points
    .map(([x, y], i) => `${i === 0 ? "M" : "L"}${x.toFixed(2)},${y.toFixed(2)}`)
    .join(" ");

  // Auto-detect trend if tone not given
  const detected = tone ?? (values[values.length - 1] >= values[0] ? "bid" : "ask");
  const stroke = STROKE[detected];

  // Area fill path: line + bottom-right + bottom-left back to start
  const areaPath = `${path} L${points[points.length - 1][0].toFixed(2)},${(height - padding).toFixed(2)} L${points[0][0].toFixed(2)},${(height - padding).toFixed(2)} Z`;

  const [lastX, lastY] = points[points.length - 1];
  const midY = padding + (height - padding * 2) / 2;

  return (
    <svg
      width={width}
      height={height}
      viewBox={`0 0 ${width} ${height}`}
      className={cn("inline-block overflow-visible", className)}
      aria-hidden
      {...props}
    >
      {area && (
        <>
          <defs>
            <linearGradient id={gradientId} x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor={stroke} stopOpacity={0.16} />
              <stop offset="100%" stopColor={stroke} stopOpacity={0} />
            </linearGradient>
          </defs>
          <path d={areaPath} fill={`url(#${gradientId})`} />
        </>
      )}
      {withMid && (
        <line
          x1={padding}
          y1={midY}
          x2={width - padding}
          y2={midY}
          stroke="var(--color-neutral-700)"
          strokeWidth={0.5}
          strokeDasharray="2 2"
        />
      )}
      <path
        d={path}
        fill="none"
        stroke={stroke}
        strokeWidth={1.25}
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      <circle cx={lastX} cy={lastY} r={1.5} fill={stroke} />
    </svg>
  );
}

export default Sparkline;
