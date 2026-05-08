"use client";

import { memo } from "react";
import { BaseEdge, getBezierPath, type EdgeProps } from "@xyflow/react";

/**
 * xyflow custom-edge adapter that draws a bezier in the redesign edge style.
 *
 * The redesign Edge component is a freestanding SVG <g/> — xyflow needs an
 * edge type that fits its renderer, so we replicate the visual contract from
 * docs/design/04-component-specs/canvas.md (1.5px stroke, neutral.500 for
 * data, accent.400 for decisions, ask.500 on errored) here.
 */

export interface CanvasEdgeData extends Record<string, unknown> {
  /** Edge kind: drives stroke color. */
  edgeKind?: "data" | "agent" | "decision";
  /** Live state. `flowing` animates a dot along the path. */
  flowing?: boolean;
  errored?: boolean;
  inactiveBranch?: boolean;
}

function strokeFor(kind: "data" | "agent" | "decision", errored: boolean): string {
  if (errored) return "var(--color-ask-500)";
  switch (kind) {
    case "agent":
      return "color-mix(in oklch, var(--color-accent-500) 60%, var(--color-neutral-500))";
    case "decision":
      return "var(--color-accent-400)";
    case "data":
    default:
      return "var(--color-neutral-500)";
  }
}

export const CanvasEdge = memo(function CanvasEdge({
  id,
  sourceX,
  sourceY,
  targetX,
  targetY,
  sourcePosition,
  targetPosition,
  selected,
  data,
}: EdgeProps) {
  const d = (data ?? {}) as CanvasEdgeData;
  const kind = d.edgeKind ?? "data";
  const errored = !!d.errored;
  const flowing = !!d.flowing;
  const inactive = !!d.inactiveBranch;

  const [path] = getBezierPath({
    sourceX,
    sourceY,
    sourcePosition,
    targetX,
    targetY,
    targetPosition,
  });

  const stroke = selected ? "var(--color-accent-500)" : strokeFor(kind, errored);
  const strokeWidth = selected ? 2.5 : 1.5;
  const opacity = inactive ? 0.3 : 1;

  // midpoint for static dot
  const mx = (sourceX + targetX) / 2;
  const my = (sourceY + targetY) / 2;

  return (
    <g style={{ opacity }} data-kind={kind}>
      <BaseEdge id={id} path={path} style={{ stroke, strokeWidth }} />
      {!errored && flowing && (
        <circle r={selected ? 3.5 : 3} fill={stroke} aria-hidden>
          <animateMotion dur="2.2s" repeatCount="indefinite" path={path} />
        </circle>
      )}
      {!errored && !flowing && (
        <circle cx={mx} cy={my} r={2.5} fill={stroke} opacity={0.6} aria-hidden />
      )}
      {errored && (
        <text
          x={mx}
          y={my}
          dy="0.35em"
          textAnchor="middle"
          fill={stroke}
          fontFamily="var(--font-mono)"
          fontSize="10"
          fontWeight={700}
          aria-hidden
        >
          ✗
        </text>
      )}
    </g>
  );
});
