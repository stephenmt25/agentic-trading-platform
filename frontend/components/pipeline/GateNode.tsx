"use client";

import { memo } from "react";
import { Handle, Position, type NodeProps } from "@xyflow/react";
import { Shield, AlertTriangle, CheckCircle } from "lucide-react";

interface GateNodeData {
  label: string;
  config?: Record<string, unknown>;
  enabled?: boolean;
  [key: string]: unknown;
}

function GateNodeComponent({ data, selected }: NodeProps) {
  const nodeData = data as GateNodeData;
  const enabled = nodeData.enabled !== false;

  return (
    <div
      className={`px-3 py-2 rounded-lg border min-w-[140px] transition-all ${
        selected
          ? "border-blue-500 shadow-lg shadow-blue-500/20"
          : "border-zinc-700 hover:border-zinc-500"
      } ${enabled ? "bg-zinc-900" : "bg-zinc-900/50 opacity-60"}`}
    >
      <Handle type="target" position={Position.Left} className="!bg-zinc-500 !w-2 !h-2" />
      <div className="flex items-center gap-2">
        <Shield className="w-3.5 h-3.5 text-blue-400" />
        <span className="text-xs font-medium text-zinc-200">{String(nodeData.label)}</span>
      </div>
      {nodeData.config && Object.keys(nodeData.config).length > 0 && (
        <div className="mt-1 text-[10px] text-zinc-500">
          {Object.entries(nodeData.config).slice(0, 2).map(([k, v]) => (
            <div key={k} className="truncate">{k}: {JSON.stringify(v)}</div>
          ))}
        </div>
      )}
      <Handle type="source" position={Position.Right} className="!bg-zinc-500 !w-2 !h-2" />
    </div>
  );
}

export const GateNode = memo(GateNodeComponent);
