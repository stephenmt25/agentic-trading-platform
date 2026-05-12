"use client";

import { memo } from "react";
import { Handle, Position, type NodeProps } from "@xyflow/react";
import { Node as DesignNode, type NodeKind, type NodeState } from "@/components/canvas";
import type { AgentKind } from "@/components/agentic/AgentAvatar";

/**
 * xyflow custom-node adapter wrapping the redesign Node component.
 *
 * The redesign Node renders ports as decorative DOM dots (not interactive).
 * xyflow needs <Handle/> elements to make connections drag-routable, so we
 * mount Handles on the four edges and let the wrapping Node draw the visual
 * dots on top of the same edge.
 *
 * Backend node taxonomy (`type`: input | gate | agent_input | meta | output)
 * is mapped here to the redesign Node's visual `kind` (data-source | decision
 * | agent | sink | transform).
 */

export interface CanvasNodeData extends Record<string, unknown> {
  label: string;
  /** Backend node type — drives the visual kind mapping. */
  backendType: string;
  /** Backend node id — used to resolve the agent identity for `agent_input`. */
  backendId: string;
  config?: Record<string, unknown>;
  /** Live runtime state (running/errored/etc.). Pending until backend wires
   *  up per-node activity; default `idle`. */
  runtimeState?: NodeState;
  /** Last-error string for the footer when state === "errored". */
  lastError?: string;
}

const AGENT_BY_ID: Record<string, AgentKind> = {
  ta_agent: "ta",
  sentiment_agent: "sentiment",
  debate_agent: "debate",
  regime_hmm: "regime",
  slm_inference: "slm",
  analyst: "analyst",
};

function mapKind(backendType: string, backendId: string): {
  kind: NodeKind;
  agent?: AgentKind;
  sinkSide?: "bid" | "ask" | "both";
} {
  switch (backendType) {
    case "input":
      return { kind: "data-source" };
    case "agent_input":
      return { kind: "agent", agent: AGENT_BY_ID[backendId] ?? "ta" };
    case "meta":
      return { kind: "agent", agent: AGENT_BY_ID[backendId] ?? "analyst" };
    case "output":
      return { kind: "sink", sinkSide: "both" };
    case "gate":
    default:
      return { kind: "decision" };
  }
}

export const CanvasNode = memo(function CanvasNode({
  data,
  selected,
}: NodeProps) {
  const d = data as CanvasNodeData;
  const { kind, agent, sinkSide } = mapKind(d.backendType, d.backendId);
  const runtime = d.runtimeState ?? "idle";
  const state: NodeState = selected ? "selected" : runtime;

  return (
    <div className="relative">
      {/* xyflow handles: top = input, bottom = output. The redesign Node draws
          its own decorative dots in the same positions. */}
      <Handle
        type="target"
        position={Position.Top}
        className="!w-2.5 !h-2.5 !bg-transparent !border-0"
        style={{ top: -6 }}
      />
      <DesignNode
        title={d.label}
        kind={kind}
        agent={agent}
        sinkSide={sinkSide}
        state={state}
        size="medium"
        inputSummary={kind === "data-source" ? undefined : describeInputs(d)}
        outputSummary={kind === "sink" ? undefined : describeOutputs(d)}
        stats={runtime === "running" ? "running" : undefined}
        lastError={d.lastError}
      />
      <Handle
        type="source"
        position={Position.Bottom}
        className="!w-2.5 !h-2.5 !bg-transparent !border-0"
        style={{ bottom: -6 }}
      />
    </div>
  );
});

function describeInputs(d: CanvasNodeData): string | undefined {
  // Until backend exposes declared port summaries we synthesize from id.
  if (d.backendId === "strategy_eval") return "indicators · regime";
  if (d.backendId === "agent_modifier") return "agent scores";
  if (d.backendType === "agent_input") return "candles · features";
  if (d.backendType === "gate") return "decision";
  return undefined;
}

function describeOutputs(d: CanvasNodeData): string | undefined {
  if (d.backendId === "strategy_eval") return "{long|short|hold}";
  if (d.backendType === "agent_input") return "score · confidence";
  if (d.backendType === "gate") return "passed | blocked";
  if (d.backendType === "input") return "ticks · candles";
  return undefined;
}
