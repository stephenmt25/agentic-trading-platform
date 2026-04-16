"use client";

import { memo } from "react";
import { Handle, Position, type NodeProps } from "@xyflow/react";
import { Zap, CheckCircle2 } from "lucide-react";

interface IONodeData {
  label: string;
  [key: string]: unknown;
}

function InputNodeComponent({ data, selected }: NodeProps) {
  const nodeData = data as IONodeData;
  return (
    <div
      className={`px-3 py-2 rounded-lg border min-w-[120px] bg-zinc-900 transition-all ${
        selected ? "border-green-500 shadow-lg shadow-green-500/20" : "border-green-500/30"
      }`}
    >
      <div className="flex items-center gap-2">
        <Zap className="w-3.5 h-3.5 text-green-400" />
        <span className="text-xs font-medium text-green-300">{String(nodeData.label)}</span>
      </div>
      <Handle type="source" position={Position.Right} className="!bg-green-500 !w-2 !h-2" />
    </div>
  );
}

function OutputNodeComponent({ data, selected }: NodeProps) {
  const nodeData = data as IONodeData;
  return (
    <div
      className={`px-3 py-2 rounded-lg border min-w-[120px] bg-zinc-900 transition-all ${
        selected ? "border-emerald-500 shadow-lg shadow-emerald-500/20" : "border-emerald-500/30"
      }`}
    >
      <Handle type="target" position={Position.Left} className="!bg-emerald-500 !w-2 !h-2" />
      <div className="flex items-center gap-2">
        <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400" />
        <span className="text-xs font-medium text-emerald-300">{String(nodeData.label)}</span>
      </div>
    </div>
  );
}

export const InputNode = memo(InputNodeComponent);
export const OutputNode = memo(OutputNodeComponent);
