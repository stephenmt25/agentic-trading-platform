"use client";

import { useId, type SVGAttributes } from "react";
import { cn } from "@/lib/utils";

/**
 * Edge per docs/design/04-component-specs/canvas.md.
 *
 * Bezier curve from output port → input port. Stroke 1.5px. Source-kind
 * tints the stroke (agent identity at 30% saturation per ADR-012 = accent
 * tone, neutral for data flows, accent for decision flows). When data
 * is actively flowing through, a small dot animates along the path
 * via CSS offset-path. Paused mode shows a static dot at the midpoint.
 *
 * Per spec: Beziers ONLY (no orthogonal). Direct source → target (no
 * auto-routing through other nodes — if it's ugly, the layout is wrong).
 */

export type EdgeKind = "agent" | "data" | "decision";
export type EdgeState =
  | "default"
  | "hover"
  | "selected"
  | "errored"
  | "inactive-branch";

export interface EdgePoint {
  x: number;
  y: number;
}

export interface EdgeProps
  extends Omit<SVGAttributes<SVGGElement>, "from" | "to" | "target"> {
  source: EdgePoint;
  target: EdgePoint;
  kind?: EdgeKind;
  state?: EdgeState;
  /** When true, animate a dot traveling along the curve. Implies live mode. */
  flowing?: boolean;
  /** Override animation duration (default --duration-ease = 220ms × 10 = 2.2s). */
  flowDurationMs?: number;
  /** Custom port handle radius for control-point spread. */
  control?: number;
}

/**
 * Build a cubic bezier path from src → tgt with control points that
 * produce a vertical-flow look (top→bottom canvas convention).
 */
function bezierPath(s: EdgePoint, t: EdgePoint, control: number): string {
  const dy = t.y - s.y;
  // pull control points away vertically so the curve has the
  // characteristic n8n / Figma "S" shape between top-edge output and
  // bottom-edge input ports.
  const offset = Math.max(40, Math.abs(dy) * 0.5, control);
  const c1x = s.x;
  const c1y = s.y + offset;
  const c2x = t.x;
  const c2y = t.y - offset;
  return `M ${s.x},${s.y} C ${c1x},${c1y} ${c2x},${c2y} ${t.x},${t.y}`;
}

function strokeFor(kind: EdgeKind, state: EdgeState): string {
  if (state === "selected") return "var(--color-accent-500)";
  if (state === "errored") return "var(--color-ask-500)";
  switch (kind) {
    case "agent":
      // ADR-012: agent identity collapses to accent at 30% sat
      return "color-mix(in oklch, var(--color-accent-500) 60%, var(--color-neutral-500))";
    case "decision":
      return "var(--color-accent-400)";
    case "data":
    default:
      return "var(--color-neutral-500)";
  }
}

export function Edge({
  source,
  target,
  kind = "data",
  state = "default",
  flowing = false,
  flowDurationMs,
  control = 60,
  className,
  ...props
}: EdgeProps) {
  const id = useId();
  const path = bezierPath(source, target, control);
  const stroke = strokeFor(kind, state);
  const strokeWidth =
    state === "selected" ? 2.5 : state === "hover" ? 2 : 1.5;
  const opacity = state === "inactive-branch" ? 0.3 : 1;

  // Midpoint for the static "paused" dot.
  const mid = {
    x: (source.x + target.x) / 2,
    y: (source.y + target.y) / 2,
  };

  return (
    <g
      data-state={state}
      data-kind={kind}
      style={{ opacity }}
      className={className}
      {...props}
    >
      <path
        id={`edge-path-${id}`}
        d={path}
        fill="none"
        stroke={stroke}
        strokeWidth={strokeWidth}
        strokeLinecap="round"
      />
      {state !== "errored" && flowing && (
        // Animated dot traveling along the path. We use SVG <animateMotion>
        // since CSS offset-path doesn't apply to SVG circles in all
        // browsers; animateMotion is the well-supported equivalent here.
        <circle
          r={state === "selected" ? 3.5 : 3}
          fill={stroke}
          aria-hidden
        >
          <animateMotion
            dur={`${(flowDurationMs ?? 2200) / 1000}s`}
            repeatCount="indefinite"
            rotate="auto"
            path={path}
          />
        </circle>
      )}
      {state !== "errored" && !flowing && (
        // Static dot at midpoint — reads as "paused" mode in the canvas.
        <circle
          cx={mid.x}
          cy={mid.y}
          r={2.5}
          fill={stroke}
          opacity={0.6}
          aria-hidden
        />
      )}
      {state === "errored" && (
        <text
          x={mid.x}
          y={mid.y}
          dy="0.35em"
          textAnchor="middle"
          fill={stroke}
          fontFamily="var(--font-mono)"
          fontSize="10"
          fontWeight="700"
          aria-hidden
        >
          ✗
        </text>
      )}
    </g>
  );
}

export default Edge;
