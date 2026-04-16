"use client";

import { usePipelineStore } from "@/lib/stores/pipelineStore";
import { X } from "lucide-react";

interface AgentParam {
  type: string;
  default: unknown;
  description: string;
  min?: number;
  max?: number;
  step?: number;
  options?: string[];
}

interface Props {
  catalog: Record<string, {
    label: string;
    type: string;
    params: Record<string, AgentParam>;
  }> | null;
}

export function NodeConfigDrawer({ catalog }: Props) {
  const selectedNodeId = usePipelineStore((s) => s.selectedNodeId);
  const nodes = usePipelineStore((s) => s.nodes);
  const setSelectedNodeId = usePipelineStore((s) => s.setSelectedNodeId);
  const onNodesChange = usePipelineStore((s) => s.onNodesChange);

  if (!selectedNodeId) return null;

  const node = nodes.find((n) => n.id === selectedNodeId);
  if (!node) return null;

  const nodeData = node.data as Record<string, unknown>;
  const config = (nodeData.config || {}) as Record<string, unknown>;

  // Find matching catalog entry
  const catalogEntry = catalog
    ? Object.values(catalog).find((c) => c.label === nodeData.label)
    : null;

  const updateConfig = (key: string, value: unknown) => {
    const updated = nodes.map((n) =>
      n.id === selectedNodeId
        ? { ...n, data: { ...n.data, config: { ...config, [key]: value } } }
        : n
    );
    onNodesChange(updated);
  };

  return (
    <div className="absolute right-0 top-0 bottom-0 w-80 bg-zinc-900 border-l border-zinc-800 z-50 overflow-y-auto">
      <div className="flex items-center justify-between px-4 py-3 border-b border-zinc-800">
        <div>
          <h3 className="text-sm font-medium text-zinc-200">{String(nodeData.label)}</h3>
          <span className="text-xs text-zinc-500">{node.type}</span>
        </div>
        <button onClick={() => setSelectedNodeId(null)} className="p-1 hover:bg-zinc-800 rounded">
          <X className="w-4 h-4 text-zinc-400" />
        </button>
      </div>

      <div className="p-4 space-y-4">
        {catalogEntry ? (
          Object.entries(catalogEntry.params).map(([key, param]) => (
            <div key={key}>
              <label className="block text-xs font-medium text-zinc-400 mb-1">
                {key}
              </label>
              <p className="text-[10px] text-zinc-600 mb-1">{param.description}</p>
              {param.type === "float" || param.type === "integer" ? (
                <div className="flex items-center gap-2">
                  <input
                    type="range"
                    min={param.min ?? 0}
                    max={param.max ?? 1}
                    step={param.step ?? (param.type === "integer" ? 1 : 0.01)}
                    value={Number(config[key] ?? param.default)}
                    onChange={(e) => updateConfig(key, Number(e.target.value))}
                    className="flex-1 accent-blue-500"
                  />
                  <span className="text-xs font-mono text-zinc-300 w-12 text-right">
                    {Number(config[key] ?? param.default).toFixed(param.type === "integer" ? 0 : 2)}
                  </span>
                </div>
              ) : param.type === "select" && param.options ? (
                <select
                  value={String(config[key] ?? param.default)}
                  onChange={(e) => updateConfig(key, e.target.value)}
                  className="w-full bg-zinc-800 border border-zinc-700 rounded px-2 py-1 text-xs text-zinc-200"
                >
                  {param.options.map((opt) => (
                    <option key={opt} value={opt}>{opt}</option>
                  ))}
                </select>
              ) : (
                <input
                  type="text"
                  value={JSON.stringify(config[key] ?? param.default)}
                  onChange={(e) => {
                    try { updateConfig(key, JSON.parse(e.target.value)); }
                    catch { updateConfig(key, e.target.value); }
                  }}
                  className="w-full bg-zinc-800 border border-zinc-700 rounded px-2 py-1 text-xs text-zinc-200 font-mono"
                />
              )}
            </div>
          ))
        ) : (
          // Show raw config for nodes without catalog entries
          Object.entries(config).length > 0 ? (
            Object.entries(config).map(([key, value]) => (
              <div key={key}>
                <label className="block text-xs font-medium text-zinc-400 mb-1">{key}</label>
                <input
                  type="text"
                  value={JSON.stringify(value)}
                  onChange={(e) => {
                    try { updateConfig(key, JSON.parse(e.target.value)); }
                    catch { updateConfig(key, e.target.value); }
                  }}
                  className="w-full bg-zinc-800 border border-zinc-700 rounded px-2 py-1 text-xs text-zinc-200 font-mono"
                />
              </div>
            ))
          ) : (
            <p className="text-xs text-zinc-500">No configurable parameters for this node.</p>
          )
        )}
      </div>
    </div>
  );
}
