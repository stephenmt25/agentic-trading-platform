"use client";

import { memo } from "react";
import { Handle, Position, type NodeProps } from "@xyflow/react";
import { Brain } from "lucide-react";

const AGENT_COLORS: Record<string, string> = {
  "TA Agent": "text-blue-400 border-blue-500/30",
  "Sentiment": "text-violet-400 border-violet-500/30",
  "Debate": "text-amber-400 border-amber-500/30",
  "Regime HMM": "text-pink-400 border-pink-500/30",
};

interface AgentNodeData {
  label: string;
  config?: Record<string, unknown>;
  [key: string]: unknown;
}

function AgentInputNodeComponent({ data, selected }: NodeProps) {
  const nodeData = data as AgentNodeData;
  const label = String(nodeData.label);
  const colorClass = AGENT_COLORS[label] || "text-emerald-400 border-emerald-500/30";
  const [textColor, borderColor] = colorClass.split(" ");

  return (
    <div
      className={`px-3 py-2 rounded-lg border min-w-[130px] bg-zinc-900/80 transition-all ${
        selected
          ? "border-blue-500 shadow-lg shadow-blue-500/20"
          : borderColor + " hover:border-zinc-500"
      }`}
    >
      <div className="flex items-center gap-2">
        <Brain className={`w-3.5 h-3.5 ${textColor}`} />
        <span className="text-xs font-medium text-zinc-200">{label}</span>
      </div>
      {nodeData.config && Object.keys(nodeData.config).length > 0 && (
        <div className="mt-1 text-[10px] text-zinc-500">
          {Object.entries(nodeData.config).slice(0, 2).map(([k, v]) => (
            <div key={k} className="truncate">{k}: {JSON.stringify(v)}</div>
          ))}
        </div>
      )}
      <Handle type="source" position={Position.Bottom} className="!bg-zinc-500 !w-2 !h-2" />
    </div>
  );
}

export const AgentInputNode = memo(AgentInputNodeComponent);
