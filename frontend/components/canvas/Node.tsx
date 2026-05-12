"use client";

import {
  forwardRef,
  type HTMLAttributes,
  type ReactNode,
} from "react";
import { Info, MoreVertical, Settings, Database, GitBranch, ArrowDownToLine, Wand2 } from "lucide-react";
import { cn } from "@/lib/utils";
import { AgentAvatar, type AgentKind } from "@/components/agentic/AgentAvatar";

/**
 * Node per docs/design/04-component-specs/canvas.md.
 *
 * The Pipeline Canvas card. ~220×120 minimum. Per spec: ALL nodes are
 * rectangles — kind is differentiated by icon + color accent + content,
 * never by shape. Configuration lives in the inspector drawer; the
 * node only shows what helps the user *read* the flow.
 *
 * Per ADR-012, agent-kind nodes use accent for the running border (all
 * six agents collapse to accent).
 */

export type NodeKind =
  | "agent"
  | "data-source"
  | "decision"
  | "sink"
  | "transform";

export type NodeState =
  | "idle"
  | "running"
  | "paused"
  | "errored"
  | "selected"
  | "executing-now";

export type NodeSize = "small" | "medium" | "large";

export interface NodeProps
  extends Omit<HTMLAttributes<HTMLDivElement>, "title"> {
  title: string;
  kind: NodeKind;
  /** Required when kind === "agent". */
  agent?: AgentKind;
  /** When kind === "sink", side determines the bid/ask split icon. */
  sinkSide?: "bid" | "ask" | "both";
  state?: NodeState;
  size?: NodeSize;
  /** Brief input description. e.g., "candles 1m × 240". */
  inputSummary?: ReactNode;
  /** Brief output description. e.g., "signal {long|short|hold}". */
  outputSummary?: ReactNode;
  /** Live stats line — caller formats. e.g., "running · 23ms · 1.2k qps". */
  stats?: ReactNode;
  lastError?: string;
  /** Number of input ports to render. Default 1. */
  inputPorts?: number;
  /** Number of output ports to render. Default 1. */
  outputPorts?: number;
  /** Optional embedded sparkline / chart for size === "large". */
  embeddedChart?: ReactNode;
  /** Click on info icon. */
  onInfoClick?: () => void;
  /** Click on the menu (⋮) icon. */
  onMenuClick?: () => void;
}

const KIND_ICON: Record<NodeKind, React.ElementType> = {
  agent: Settings, // overridden below by AgentAvatar
  "data-source": Database,
  decision: GitBranch,
  sink: ArrowDownToLine,
  transform: Wand2,
};

const KIND_LABEL: Record<NodeKind, string> = {
  agent: "agent",
  "data-source": "data source",
  decision: "decision",
  sink: "sink",
  transform: "transform",
};

const SIZE_DIM: Record<NodeSize, string> = {
  small: "min-w-[140px]",
  medium: "min-w-[220px]",
  large: "min-w-[260px]",
};

function stateBorder(kind: NodeKind, state: NodeState): string {
  if (state === "selected") return "border-accent-500 shadow-md";
  if (state === "errored") return "border-ask-500";
  if (state === "running") {
    if (kind === "agent" || kind === "decision") return "border-accent-500/70";
    if (kind === "data-source") return "border-neutral-400/70";
    if (kind === "sink") return "border-bid-500/70";
    return "border-fg-muted/70";
  }
  if (state === "paused") return "border-border-subtle";
  return "border-border-subtle";
}

export const Node = forwardRef<HTMLDivElement, NodeProps>(
  (
    {
      title,
      kind,
      agent,
      sinkSide,
      state = "idle",
      size = "medium",
      inputSummary,
      outputSummary,
      stats,
      lastError,
      inputPorts = 1,
      outputPorts = 1,
      embeddedChart,
      onInfoClick,
      onMenuClick,
      className,
      ...props
    },
    ref
  ) => {
    const KindIcon = KIND_ICON[kind];

    return (
      <div
        ref={ref}
        role="group"
        aria-label={`${KIND_LABEL[kind]} node: ${title}`}
        data-kind={kind}
        data-state={state}
        data-size={size}
        tabIndex={0}
        className={cn(
          "relative rounded-md bg-bg-panel border-[1.5px]",
          stateBorder(kind, state),
          SIZE_DIM[size],
          "focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent-500",
          state === "paused" && "saturate-50 opacity-80",
          state === "running" && "transition-[border-color] duration-150",
          state === "executing-now" &&
            "ring-2 ring-accent-500/30 transition-[box-shadow] duration-[180ms]",
          className
        )}
        {...props}
      >
        {/* Top-edge input ports */}
        {inputPorts > 0 && (
          <div
            aria-hidden
            className="absolute -top-1.5 left-0 right-0 flex justify-around pointer-events-none"
          >
            {Array.from({ length: inputPorts }).map((_, i) => (
              <span
                key={i}
                data-port="in"
                className="block w-2.5 h-2.5 rounded-full bg-bg-canvas border border-border-strong"
              />
            ))}
          </div>
        )}

        {/* Bottom-edge output ports */}
        {outputPorts > 0 && (
          <div
            aria-hidden
            className="absolute -bottom-1.5 left-0 right-0 flex justify-around pointer-events-none"
          >
            {Array.from({ length: outputPorts }).map((_, i) => (
              <span
                key={i}
                data-port="out"
                className={cn(
                  "block w-2.5 h-2.5 rounded-full bg-bg-canvas border",
                  state === "running"
                    ? "border-accent-400"
                    : "border-border-strong"
                )}
              />
            ))}
          </div>
        )}

        {/* Header */}
        <header
          className={cn(
            "flex items-center gap-2 px-3 h-9",
            size !== "small" && "border-b border-border-subtle"
          )}
        >
          {kind === "agent" && agent ? (
            <AgentAvatar kind={agent} size="sm" />
          ) : (
            <span
              className={cn(
                "inline-flex items-center justify-center w-6 h-6 rounded-sm",
                "bg-bg-raised text-fg",
                kind === "decision" && "text-accent-400",
                kind === "sink" &&
                  (sinkSide === "ask"
                    ? "text-ask-400"
                    : sinkSide === "bid"
                      ? "text-bid-400"
                      : "text-fg-secondary")
              )}
            >
              <KindIcon className="w-3.5 h-3.5" strokeWidth={1.5} aria-hidden />
            </span>
          )}

          <span className="text-[13px] font-medium text-fg num-tabular truncate flex-1">
            {title}
          </span>

          {state === "paused" && (
            <span className="text-[10px] uppercase tracking-wider text-fg-muted px-1 py-0.5 rounded-sm bg-bg-raised">
              paused
            </span>
          )}

          {onInfoClick && (
            <button
              type="button"
              onClick={(e) => {
                e.stopPropagation();
                onInfoClick();
              }}
              aria-label={`Open inspector for ${title}`}
              className="text-fg-muted hover:text-fg focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent-500 rounded-sm"
            >
              <Info className="w-3.5 h-3.5" strokeWidth={1.5} aria-hidden />
            </button>
          )}
          {onMenuClick && (
            <button
              type="button"
              onClick={(e) => {
                e.stopPropagation();
                onMenuClick();
              }}
              aria-label={`Open menu for ${title}`}
              className="text-fg-muted hover:text-fg focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent-500 rounded-sm"
            >
              <MoreVertical className="w-3.5 h-3.5" strokeWidth={1.5} aria-hidden />
            </button>
          )}
        </header>

        {/* Body — hidden when small */}
        {size !== "small" && (
          <div className="flex flex-col gap-1 px-3 py-2 text-[12px]">
            {inputSummary !== undefined && (
              <div className="flex items-baseline gap-1.5">
                <span className="text-[10px] uppercase tracking-wider text-fg-muted w-6 num-tabular">
                  in
                </span>
                <span className="text-fg-secondary truncate flex-1">
                  {inputSummary}
                </span>
              </div>
            )}
            {outputSummary !== undefined && (
              <div className="flex items-baseline gap-1.5">
                <span className="text-[10px] uppercase tracking-wider text-fg-muted w-6 num-tabular">
                  out
                </span>
                <span className="text-fg-secondary truncate flex-1">
                  {outputSummary}
                </span>
              </div>
            )}

            {size === "large" && embeddedChart && (
              <div className="mt-1 -mx-1">{embeddedChart}</div>
            )}
          </div>
        )}

        {/* Footer — live stats line */}
        {size !== "small" && (stats || (state === "errored" && lastError)) && (
          <footer
            className={cn(
              "px-3 py-1.5 border-t border-border-subtle text-[11px] num-tabular font-mono",
              state === "errored" ? "text-ask-300" : "text-fg-muted",
              state === "running" && "animate-pulse-subtle"
            )}
          >
            {state === "errored" && lastError ? lastError : stats}
          </footer>
        )}
      </div>
    );
  }
);
Node.displayName = "Node";

export default Node;
