"use client";

import { useEffect, useState, useCallback, useMemo } from "react";
import {
  ReactFlow,
  MiniMap,
  Controls,
  Background,
  BackgroundVariant,
  useNodesState,
  useEdgesState,
  addEdge,
  type Connection,
  type Node,
  type Edge,
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";

import { api } from "@/lib/api/client";
import { usePipelineStore } from "@/lib/stores/pipelineStore";
import { usePortfolioStore } from "@/lib/stores/portfolioStore";
import { GateNode } from "@/components/pipeline/GateNode";
import { AgentInputNode } from "@/components/pipeline/AgentInputNode";
import { InputNode, OutputNode } from "@/components/pipeline/IONode";
import { NodeConfigDrawer } from "@/components/pipeline/NodeConfigDrawer";
import { Loader2, Workflow, Save, RotateCcw } from "lucide-react";
import { motion } from "framer-motion";
import { pageEnter } from "@/lib/motion";
import { toast } from "sonner";

const nodeTypes = {
  gate: GateNode,
  agent_input: AgentInputNode,
  input: InputNode,
  output: OutputNode,
};

function convertToReactFlowNodes(
  pipelineNodes: Array<{ id: string; type: string; label: string; config?: Record<string, unknown>; position: { x: number; y: number } }>
): Node[] {
  return pipelineNodes.map((n) => ({
    id: n.id,
    type: n.type,
    position: n.position,
    data: { label: n.label, config: n.config || {} },
    draggable: true,
  }));
}

function convertToReactFlowEdges(
  pipelineEdges: Array<{ id: string; source: string; target: string; condition?: string }>
): Edge[] {
  return pipelineEdges.map((e) => ({
    id: e.id,
    source: e.source,
    target: e.target,
    animated: true,
    style: { stroke: "rgba(255,255,255,0.15)", strokeWidth: 1.5 },
    label: e.condition || undefined,
    labelStyle: { fill: "#9ca3af", fontSize: 10 },
  }));
}

export default function PipelinePage() {
  const profiles = usePortfolioStore((s) => s.profiles);
  const [selectedProfile, setSelectedProfile] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [catalog, setCatalog] = useState<Record<string, unknown> | null>(null);

  const [nodes, setNodes, onNodesChange] = useNodesState<Node>([]);
  const [edges, setEdges, onEdgesChange] = useEdgesState<Edge>([]);

  const selectedNodeId = usePipelineStore((s) => s.selectedNodeId);
  const setSelectedNodeId = usePipelineStore((s) => s.setSelectedNodeId);
  const isDirty = usePipelineStore((s) => s.isDirty);
  const markDirty = usePipelineStore((s) => s.markDirty);
  const markClean = usePipelineStore((s) => s.markClean);

  // Sync nodes/edges to store for the drawer
  useEffect(() => {
    usePipelineStore.getState().setNodes(nodes);
  }, [nodes]);
  useEffect(() => {
    usePipelineStore.getState().setEdges(edges);
  }, [edges]);

  // Load catalog on mount
  useEffect(() => {
    api.agentConfig.catalog().then(setCatalog).catch(() => {});
  }, []);

  // Load profiles if not already loaded
  useEffect(() => {
    if (!profiles.length) {
      api.profiles.list().then((p) => {
        usePortfolioStore.getState().setProfiles(p as any);
        if (p.length > 0) setSelectedProfile((p[0] as any).profile_id);
      }).catch(() => {});
    } else if (!selectedProfile) {
      setSelectedProfile((profiles[0] as any).profile_id);
    }
  }, [profiles, selectedProfile]);

  // Load pipeline config when profile changes
  const loadPipeline = useCallback(async () => {
    if (!selectedProfile) return;
    setLoading(true);
    try {
      const config = await api.agentConfig.getPipeline(selectedProfile);
      setNodes(convertToReactFlowNodes(config.nodes));
      setEdges(convertToReactFlowEdges(config.edges));
      markClean();
    } catch {
      toast.error("Failed to load pipeline config");
    } finally {
      setLoading(false);
    }
  }, [selectedProfile, setNodes, setEdges, markClean]);

  useEffect(() => {
    loadPipeline();
  }, [loadPipeline]);

  const onConnect = useCallback(
    (connection: Connection) => {
      setEdges((eds) => addEdge({ ...connection, animated: true, style: { stroke: "rgba(255,255,255,0.15)", strokeWidth: 1.5 } }, eds));
      markDirty();
    },
    [setEdges, markDirty]
  );

  const onNodeClick = useCallback(
    (_: React.MouseEvent, node: Node) => {
      setSelectedNodeId(node.id);
    },
    [setSelectedNodeId]
  );

  const onPaneClick = useCallback(() => {
    setSelectedNodeId(null);
  }, [setSelectedNodeId]);

  const handleSave = async () => {
    if (!selectedProfile) return;
    setSaving(true);
    try {
      const config = {
        nodes: nodes.map((n) => ({
          id: n.id,
          type: n.type || "gate",
          label: String((n.data as any).label),
          config: (n.data as any).config || {},
          position: n.position,
        })),
        edges: edges.map((e) => ({
          id: e.id,
          source: e.source,
          target: e.target,
        })),
      };
      await api.agentConfig.savePipeline(selectedProfile, config);
      markClean();
      toast.success("Pipeline saved");
    } catch {
      toast.error("Failed to save pipeline");
    } finally {
      setSaving(false);
    }
  };

  const handleReset = async () => {
    if (!selectedProfile) return;
    try {
      await api.agentConfig.resetPipeline(selectedProfile);
      await loadPipeline();
      toast.success("Pipeline reset to default");
    } catch {
      toast.error("Failed to reset pipeline");
    }
  };

  return (
    <motion.div
      className="h-[calc(100vh-64px)] flex flex-col"
      variants={pageEnter}
      initial="hidden"
      animate="show"
    >
      {/* Toolbar */}
      <div className="flex items-center justify-between px-4 py-2 border-b border-zinc-800 bg-zinc-900/80 backdrop-blur-sm">
        <div className="flex items-center gap-3">
          <Workflow className="w-5 h-5 text-amber-400" />
          <h1 className="text-sm font-semibold text-zinc-100">Pipeline Editor</h1>
          {isDirty && (
            <span className="text-[10px] px-1.5 py-0.5 bg-amber-500/20 text-amber-400 rounded">
              Unsaved
            </span>
          )}
        </div>
        <div className="flex items-center gap-2">
          {/* Profile selector */}
          <select
            value={selectedProfile || ""}
            onChange={(e) => setSelectedProfile(e.target.value)}
            className="bg-zinc-800 border border-zinc-700 rounded px-2 py-1 text-xs text-zinc-200"
          >
            {profiles.map((p: any) => (
              <option key={p.profile_id} value={p.profile_id}>
                {p.name}
              </option>
            ))}
          </select>

          <button
            onClick={handleReset}
            className="flex items-center gap-1 px-2 py-1 rounded text-xs text-zinc-400 hover:text-zinc-200 hover:bg-zinc-800 transition-colors"
          >
            <RotateCcw className="w-3 h-3" />
            Reset
          </button>
          <button
            onClick={handleSave}
            disabled={!isDirty || saving}
            className="flex items-center gap-1 px-3 py-1 rounded text-xs font-medium bg-blue-600 text-white hover:bg-blue-500 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
          >
            {saving ? <Loader2 className="w-3 h-3 animate-spin" /> : <Save className="w-3 h-3" />}
            Save
          </button>
        </div>
      </div>

      {/* Canvas */}
      <div className="flex-1 relative">
        {loading ? (
          <div className="flex items-center justify-center h-full">
            <Loader2 className="w-6 h-6 text-amber-400 animate-spin" />
          </div>
        ) : (
          <>
            <ReactFlow
              nodes={nodes}
              edges={edges}
              onNodesChange={(changes) => { onNodesChange(changes); markDirty(); }}
              onEdgesChange={(changes) => { onEdgesChange(changes); markDirty(); }}
              onConnect={onConnect}
              onNodeClick={onNodeClick}
              onPaneClick={onPaneClick}
              nodeTypes={nodeTypes}
              fitView
              fitViewOptions={{ padding: 0.2 }}
              proOptions={{ hideAttribution: true }}
              style={{ background: "#0d1117" }}
            >
              <Controls
                showInteractive={false}
                style={{ backgroundColor: "#1f2937", borderColor: "rgba(255,255,255,0.1)" }}
              />
              <MiniMap
                nodeColor={(n) => {
                  if (n.type === "agent_input") return "#8b5cf6";
                  if (n.type === "input") return "#22c55e";
                  if (n.type === "output") return "#10b981";
                  return "#3b82f6";
                }}
                style={{ backgroundColor: "#0d1117", border: "1px solid rgba(255,255,255,0.1)" }}
              />
              <Background variant={BackgroundVariant.Dots} gap={20} size={1} color="rgba(255,255,255,0.05)" />
            </ReactFlow>

            {/* Config drawer */}
            <NodeConfigDrawer catalog={catalog as any} />
          </>
        )}
      </div>
    </motion.div>
  );
}
