"use client";

import {
  forwardRef,
  useCallback,
  useRef,
  useState,
  type HTMLAttributes,
  type PointerEvent,
} from "react";
import { Maximize2, Minimize2 } from "lucide-react";
import { cn } from "@/lib/utils";
import type { NodeKind, NodeState } from "./Node";

/**
 * MiniMap per docs/design/04-component-specs/canvas.md.
 *
 * 160×120 representation of the entire canvas. Nodes as filled rects in
 * their semantic color (or running/errored hue). The viewport rectangle
 * is draggable. Per spec: NOT clickable on nodes (feature trap; users
 * misclick and lose context). Only viewport drag is interactive.
 *
 * Off-screen `running` or `errored` nodes pulse on the minimap to draw
 * attention back.
 */

export interface MiniMapNode {
  id: string;
  /** World-space position of the node's top-left corner (in canvas coords). */
  x: number;
  y: number;
  /** World-space size. */
  width: number;
  height: number;
  kind: NodeKind;
  state: NodeState;
}

export interface MiniMapViewport {
  /** World-space top-left of the visible viewport. */
  x: number;
  y: number;
  /** World-space size. */
  width: number;
  height: number;
}

export interface MiniMapProps
  extends Omit<HTMLAttributes<HTMLDivElement>, "children"> {
  nodes: MiniMapNode[];
  viewport: MiniMapViewport;
  /** Bounding box of the world we're representing. Defaults to the
   *  union of nodes + viewport with 100px padding. */
  worldBounds?: { x: number; y: number; width: number; height: number };
  /** Mini-map size — spec says 160×120 default. */
  width?: number;
  height?: number;
  /** Caller updates viewport position when user drags the rect. */
  onViewportChange?: (next: { x: number; y: number }) => void;
  /** Default-collapsed (chevron only). */
  defaultCollapsed?: boolean;
}

const KIND_FILL: Record<NodeKind, string> = {
  agent: "var(--color-accent-500)",
  "data-source": "var(--color-neutral-400)",
  decision: "var(--color-accent-400)",
  sink: "var(--color-bid-500)",
  transform: "var(--color-neutral-500)",
};

function nodeFill(node: MiniMapNode): string {
  if (node.state === "errored") return "var(--color-ask-500)";
  if (node.state === "selected") return "var(--color-accent-500)";
  if (node.state === "paused")
    return "color-mix(in oklch, " + KIND_FILL[node.kind] + " 30%, transparent)";
  return KIND_FILL[node.kind];
}

function autoBounds(
  nodes: MiniMapNode[],
  viewport: MiniMapViewport
): { x: number; y: number; width: number; height: number } {
  const xs = [
    ...nodes.map((n) => n.x),
    ...nodes.map((n) => n.x + n.width),
    viewport.x,
    viewport.x + viewport.width,
  ];
  const ys = [
    ...nodes.map((n) => n.y),
    ...nodes.map((n) => n.y + n.height),
    viewport.y,
    viewport.y + viewport.height,
  ];
  if (xs.length === 0 || ys.length === 0) {
    return { x: 0, y: 0, width: 1, height: 1 };
  }
  const pad = 100;
  const minX = Math.min(...xs) - pad;
  const minY = Math.min(...ys) - pad;
  const maxX = Math.max(...xs) + pad;
  const maxY = Math.max(...ys) + pad;
  return {
    x: minX,
    y: minY,
    width: Math.max(1, maxX - minX),
    height: Math.max(1, maxY - minY),
  };
}

export const MiniMap = forwardRef<HTMLDivElement, MiniMapProps>(
  (
    {
      nodes,
      viewport,
      worldBounds,
      width = 160,
      height = 120,
      onViewportChange,
      defaultCollapsed = false,
      className,
      ...props
    },
    ref
  ) => {
    const [collapsed, setCollapsed] = useState(defaultCollapsed);

    const bounds = worldBounds ?? autoBounds(nodes, viewport);
    const sx = width / bounds.width;
    const sy = height / bounds.height;
    const project = (x: number, y: number) => ({
      x: (x - bounds.x) * sx,
      y: (y - bounds.y) * sy,
    });

    // Determine which off-screen nodes need to pulse for attention.
    const isOffscreen = (n: MiniMapNode) =>
      n.x + n.width < viewport.x ||
      n.y + n.height < viewport.y ||
      n.x > viewport.x + viewport.width ||
      n.y > viewport.y + viewport.height;

    // Drag handling for the viewport rect.
    const dragStart = useRef<{
      px: number;
      py: number;
      vx: number;
      vy: number;
    } | null>(null);

    const onPointerDown = useCallback(
      (e: PointerEvent<SVGRectElement>) => {
        if (!onViewportChange) return;
        e.preventDefault();
        const target = e.currentTarget;
        target.setPointerCapture(e.pointerId);
        dragStart.current = {
          px: e.clientX,
          py: e.clientY,
          vx: viewport.x,
          vy: viewport.y,
        };
      },
      [onViewportChange, viewport.x, viewport.y]
    );

    const onPointerMove = useCallback(
      (e: PointerEvent<SVGRectElement>) => {
        if (!dragStart.current || !onViewportChange) return;
        const dx = (e.clientX - dragStart.current.px) / sx;
        const dy = (e.clientY - dragStart.current.py) / sy;
        onViewportChange({
          x: dragStart.current.vx + dx,
          y: dragStart.current.vy + dy,
        });
      },
      [onViewportChange, sx, sy]
    );

    const onPointerUp = useCallback(
      (e: PointerEvent<SVGRectElement>) => {
        const target = e.currentTarget;
        if (target.hasPointerCapture(e.pointerId)) {
          target.releasePointerCapture(e.pointerId);
        }
        dragStart.current = null;
      },
      []
    );

    if (collapsed) {
      return (
        <div
          ref={ref}
          className={cn(
            "inline-flex",
            className
          )}
          {...props}
        >
          <button
            type="button"
            onClick={() => setCollapsed(false)}
            aria-label="Expand minimap"
            className={cn(
              "w-6 h-6 rounded-sm border border-border-subtle bg-bg-panel",
              "flex items-center justify-center text-fg-muted hover:text-fg",
              "focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent-500"
            )}
          >
            <Maximize2 className="w-3 h-3" strokeWidth={1.5} aria-hidden />
          </button>
        </div>
      );
    }

    const vpProj = project(viewport.x, viewport.y);
    const vpProjEnd = project(
      viewport.x + viewport.width,
      viewport.y + viewport.height
    );

    return (
      <div
        ref={ref}
        role="img"
        aria-label="Canvas minimap"
        className={cn(
          "relative rounded-sm border border-border-subtle bg-bg-panel",
          className
        )}
        style={{ width, height }}
        {...props}
      >
        <button
          type="button"
          onClick={() => setCollapsed(true)}
          aria-label="Collapse minimap"
          className={cn(
            "absolute top-1 right-1 z-10 w-4 h-4 rounded-sm",
            "flex items-center justify-center text-fg-muted hover:text-fg",
            "focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent-500"
          )}
        >
          <Minimize2 className="w-2.5 h-2.5" strokeWidth={1.5} aria-hidden />
        </button>

        <svg
          width={width}
          height={height}
          viewBox={`0 0 ${width} ${height}`}
          className="block"
          aria-hidden
        >
          {/* Nodes — rendered as filled rects */}
          {nodes.map((n) => {
            const p = project(n.x, n.y);
            const w = n.width * sx;
            const h = n.height * sy;
            const offscreen = isOffscreen(n);
            const shouldPulse =
              offscreen && (n.state === "running" || n.state === "errored");
            return (
              <rect
                key={n.id}
                x={p.x}
                y={p.y}
                width={w}
                height={h}
                rx={1}
                fill={nodeFill(n)}
                opacity={n.state === "paused" ? 0.5 : 1}
                className={shouldPulse ? "animate-pulse" : undefined}
              />
            );
          })}

          {/* Viewport rect — draggable when onViewportChange is supplied */}
          <rect
            x={vpProj.x}
            y={vpProj.y}
            width={Math.max(1, vpProjEnd.x - vpProj.x)}
            height={Math.max(1, vpProjEnd.y - vpProj.y)}
            fill="var(--color-accent-500)"
            fillOpacity={0.08}
            stroke="var(--color-accent-500)"
            strokeWidth={1}
            style={{ cursor: onViewportChange ? "grab" : "default" }}
            onPointerDown={onPointerDown}
            onPointerMove={onPointerMove}
            onPointerUp={onPointerUp}
          />
        </svg>
      </div>
    );
  }
);
MiniMap.displayName = "MiniMap";

export default MiniMap;
