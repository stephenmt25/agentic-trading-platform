"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import {
  ReactFlow,
  ReactFlowProvider,
  Background,
  BackgroundVariant,
  Controls,
  MiniMap as XYFlowMiniMap,
  addEdge,
  useEdgesState,
  useNodesState,
  type Connection,
  type Edge,
  type Node,
  type OnSelectionChangeParams,
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";

import { ArrowLeft, Loader2, AlertTriangle, RotateCcw } from "lucide-react";
import { toast } from "sonner";

import { Button, Tag } from "@/components/primitives";
import { Pill, StatusDot } from "@/components/data-display";
import {
  NodePalette,
  NodeInspector,
  RunControlBar,
  type RunActivity,
} from "@/components/canvas";
import { api, type ProfileResponse } from "@/lib/api/client";

import { CanvasNode, type CanvasNodeData } from "./_components/CanvasNode";
import { CanvasEdge, type CanvasEdgeData } from "./_components/CanvasEdge";
import {
  InspectorContent,
  type AgentCatalog,
} from "./_components/InspectorContent";

/**
 * /canvas/{profile_id} — the Pipeline Canvas surface.
 * Surface spec: docs/design/05-surface-specs/03-pipeline-canvas.md.
 *
 * Compositional only — Node, Edge, NodePalette, NodeInspector, RunControlBar,
 * MiniMap from components/canvas/. xyflow is the viewport runtime; this page
 * is the adapter that wires backend pipeline_config ↔ xyflow state.
 *
 * Save model (per CLAUDE.md §2C and surface spec §3): saving is atomic with
 * strategy_rules compilation. PUT /agent-config/{profile_id}/pipeline.
 *
 * Backend gaps surfaced inline as <Tag intent="warn">Pending</Tag> per the
 * "render the spec'd structure, never fake" pattern:
 *   - Per-node live activity (running state, latency, qps) — needs WS feed.
 *   - Run paper / Run live — execution wiring not yet exposed.
 *   - Drag-from-palette to add a node — backend-id collision rules need work.
 *   - Compare profiles, templates, comments, auto-layout (spec §6/§7/§8).
 */

const NODE_TYPES = {
  default: CanvasNode,
};
const EDGE_TYPES = {
  default: CanvasEdge,
};

export default function PipelineCanvasPage() {
  return (
    <ReactFlowProvider>
      <PipelineCanvasInner />
    </ReactFlowProvider>
  );
}

function PipelineCanvasInner() {
  const params = useParams<{ profile_id: string }>();
  const router = useRouter();
  const profileId = decodeURIComponent(params.profile_id);

  const [profile, setProfile] = useState<ProfileResponse | null>(null);
  const [profiles, setProfiles] = useState<ProfileResponse[]>([]);
  const [catalog, setCatalog] = useState<AgentCatalog | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [nodes, setNodes, onNodesChange] = useNodesState<Node>([]);
  const [edges, setEdges, onEdgesChange] = useEdgesState<Edge>([]);

  const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null);
  const [dirty, setDirty] = useState(false);
  const [savedAt, setSavedAt] = useState<number | null>(null);
  const [savedAtText, setSavedAtText] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  // Run activity stays "idle" — backend run-launching isn't wired here yet.
  const [activity] = useState<RunActivity>("idle");

  // ------- Initial load -------
  const loadPipeline = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const config = await api.agentConfig.getPipeline(profileId);
      setNodes(toReactFlowNodes(config.nodes));
      setEdges(toReactFlowEdges(config.edges));
      setDirty(false);
      setSavedAt(Date.now());
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : "Failed to load pipeline";
      setError(msg);
    } finally {
      setLoading(false);
    }
  }, [profileId, setNodes, setEdges]);

  useEffect(() => {
    loadPipeline();
  }, [loadPipeline]);

  // Profile metadata (for header) + catalog + sibling list (for selector).
  useEffect(() => {
    let cancelled = false;
    api.profiles
      .list()
      .then((all) => {
        if (cancelled) return;
        setProfiles(all);
        const found = all.find((p) => p.profile_id === profileId);
        if (found) setProfile(found);
      })
      .catch(() => {});
    api.agentConfig
      .catalog()
      .then((c) => {
        if (cancelled) return;
        setCatalog(c as AgentCatalog);
      })
      .catch(() => {});
    return () => {
      cancelled = true;
    };
  }, [profileId]);

  // "saved Xm ago" rolls forward every minute.
  useEffect(() => {
    if (!savedAt) {
      setSavedAtText(null);
      return;
    }
    const tick = () => setSavedAtText(formatRelative(savedAt));
    tick();
    const id = window.setInterval(tick, 30_000);
    return () => window.clearInterval(id);
  }, [savedAt]);

  // ------- Mutators that mark dirty -------
  const handleNodesChange = useCallback(
    (changes: Parameters<typeof onNodesChange>[0]) => {
      onNodesChange(changes);
      // Selection changes don't mark dirty; everything else does.
      const meaningful = changes.some(
        (c) => c.type !== "select" && c.type !== "dimensions"
      );
      if (meaningful) setDirty(true);
    },
    [onNodesChange]
  );

  const handleEdgesChange = useCallback(
    (changes: Parameters<typeof onEdgesChange>[0]) => {
      onEdgesChange(changes);
      const meaningful = changes.some((c) => c.type !== "select");
      if (meaningful) setDirty(true);
    },
    [onEdgesChange]
  );

  const handleConnect = useCallback(
    (connection: Connection) => {
      setEdges((eds) =>
        addEdge(
          {
            ...connection,
            type: "default",
            data: { edgeKind: "data" } satisfies CanvasEdgeData,
          },
          eds
        )
      );
      setDirty(true);
    },
    [setEdges]
  );

  const updateNodeConfig = useCallback(
    (nodeId: string, key: string, value: unknown) => {
      setNodes((prev) =>
        prev.map((n) =>
          n.id === nodeId
            ? {
                ...n,
                data: {
                  ...n.data,
                  config: {
                    ...((n.data as CanvasNodeData).config ?? {}),
                    [key]: value,
                  },
                },
              }
            : n
        )
      );
      setDirty(true);
    },
    [setNodes]
  );

  const updateNodeTitle = useCallback(
    (nodeId: string, label: string) => {
      setNodes((prev) =>
        prev.map((n) =>
          n.id === nodeId
            ? { ...n, data: { ...n.data, label } }
            : n
        )
      );
      setDirty(true);
    },
    [setNodes]
  );

  // ------- Save -------
  const handleSave = useCallback(async () => {
    if (saving) return;
    if (nodes.length === 0) {
      toast.error("Canvas is empty — load a profile first");
      return;
    }
    setSaving(true);
    try {
      const payload = {
        nodes: nodes.map((n) => {
          const d = n.data as CanvasNodeData;
          return {
            id: n.id,
            type: d.backendType,
            label: d.label,
            config: d.config ?? {},
            position: n.position,
          };
        }),
        edges: edges.map((e) => ({
          id: e.id,
          source: e.source,
          target: e.target,
        })),
      };
      const res = await api.agentConfig.savePipeline(profileId, payload);
      setDirty(false);
      setSavedAt(Date.now());
      const compiled = (res as unknown as { rules_compiled?: boolean }).rules_compiled;
      if (compiled === false) {
        toast.warning(
          "Saved, but strategy_rules did not recompile (strategy_eval is incomplete)."
        );
      } else {
        toast.success("Pipeline saved");
      }
    } catch (e) {
      const msg = e instanceof Error ? e.message : "Failed to save";
      toast.error(msg);
    } finally {
      setSaving(false);
    }
  }, [saving, nodes, edges, profileId]);

  // ------- Reset -------
  const handleReset = useCallback(async () => {
    try {
      await api.agentConfig.resetPipeline(profileId);
      await loadPipeline();
      toast.success("Pipeline reset to default");
    } catch {
      toast.error("Failed to reset pipeline");
    }
  }, [profileId, loadPipeline]);

  // ------- Cmd+S shortcut -------
  const saveRef = useRef(handleSave);
  saveRef.current = handleSave;
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "s") {
        e.preventDefault();
        void saveRef.current();
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  // ------- Selection -------
  const onSelectionChange = useCallback(
    ({ nodes: sel }: OnSelectionChangeParams) => {
      setSelectedNodeId(sel.length === 1 ? sel[0].id : null);
    },
    []
  );

  const selectedNode = useMemo(
    () => (selectedNodeId ? nodes.find((n) => n.id === selectedNodeId) ?? null : null),
    [selectedNodeId, nodes]
  );

  const profileOptions = useMemo(
    () =>
      profiles.map((p) => ({
        value: p.profile_id,
        label: p.name,
      })),
    [profiles]
  );

  // ------- Render -------
  return (
    <div data-mode="cool" className="flex flex-col h-full bg-bg-canvas text-fg">
      {/* Top breadcrumb header */}
      <header className="flex items-center justify-between gap-4 border-b border-border-subtle px-6 py-3">
        <div className="flex items-center gap-2 text-[12px] text-fg-muted min-w-0">
          <Link
            href="/canvas"
            className="inline-flex items-center gap-1 hover:text-fg transition-colors focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent-500 rounded-sm"
          >
            <ArrowLeft className="w-3 h-3" strokeWidth={1.5} />
            Pipeline Canvas
          </Link>
          <span aria-hidden>/</span>
          <span className="font-mono text-fg-secondary truncate">
            {profile?.name ?? profileId.slice(0, 8)}
          </span>
          {profile?.is_active && (
            <Pill intent="bid" icon={<StatusDot state="live" size={6} pulse />}>
              Active
            </Pill>
          )}
        </div>
        <div className="flex items-center gap-2 shrink-0">
          <Button
            intent="secondary"
            size="sm"
            leftIcon={<RotateCcw className="w-3 h-3" strokeWidth={1.5} />}
            onClick={handleReset}
          >
            Reset to default
          </Button>
        </div>
      </header>

      {error && !loading && (
        <div
          role="alert"
          className="mx-6 mt-4 rounded-md border border-danger-700/40 bg-danger-700/10 p-4 flex items-start gap-3 text-[13px] text-danger-500"
        >
          <AlertTriangle
            className="w-4 h-4 shrink-0 mt-0.5"
            strokeWidth={1.5}
            aria-hidden
          />
          <div className="flex-1">
            <p className="font-medium">Could not load pipeline.</p>
            <p className="text-fg-muted mt-0.5">{error}</p>
          </div>
          <Button intent="secondary" size="sm" onClick={loadPipeline}>
            Retry
          </Button>
          <Button
            intent="secondary"
            size="sm"
            onClick={() => router.push("/canvas")}
          >
            Back
          </Button>
        </div>
      )}

      <div className="flex-1 min-h-0 flex overflow-hidden">
        {/* Left rail: NodePalette */}
        <aside className="w-60 shrink-0 border-r border-border-subtle p-3 overflow-hidden flex flex-col gap-2">
          <div className="flex items-center gap-2">
            <h2 className="text-[10px] uppercase tracking-wider text-fg-muted num-tabular">
              palette
            </h2>
            <Tag intent="warn">Pending drag-to-add</Tag>
          </div>
          <p className="text-[10px] text-fg-muted leading-snug">
            Visual catalog of node kinds. Drag-to-add is deferred — node IDs
            are compile-significant (e.g.{" "}
            <span className="font-mono">strategy_eval</span>), so add-flows
            need backend-id reservation.
          </p>
          <div className="flex-1 min-h-0">
            <NodePalette className="h-full" />
          </div>
        </aside>

        {/* Center: RunControlBar + xyflow viewport (+ floating MiniMap) */}
        <section className="flex-1 min-w-0 flex flex-col">
          <RunControlBar
            profileOptions={profileOptions}
            activeProfileId={profileId}
            onProfileChange={(id) =>
              router.push(`/canvas/${encodeURIComponent(id)}`)
            }
            dirty={dirty}
            savedAtText={savedAtText ?? undefined}
            onSave={handleSave}
            activity={activity}
            onRunPaper={() =>
              toast.info("Run paper not yet wired in /canvas — Pending")
            }
            onRunLive={() =>
              toast.info("Run live not yet wired in /canvas — Pending")
            }
            onRunBacktest={() =>
              router.push(
                `/backtests?profile_id=${encodeURIComponent(profileId)}`
              )
            }
          />

          <div className="flex-1 min-h-0 relative">
            {loading && (
              <div className="absolute inset-0 z-10 flex items-center justify-center bg-bg-canvas/60 backdrop-blur-sm">
                <div className="flex items-center gap-2 text-[13px] text-fg-muted">
                  <Loader2 className="w-4 h-4 animate-spin" aria-hidden />
                  Loading pipeline…
                </div>
              </div>
            )}
            <ReactFlow
              nodes={nodes}
              edges={edges}
              nodeTypes={NODE_TYPES}
              edgeTypes={EDGE_TYPES}
              onNodesChange={handleNodesChange}
              onEdgesChange={handleEdgesChange}
              onConnect={handleConnect}
              onSelectionChange={onSelectionChange}
              fitView
              fitViewOptions={{ padding: 0.2 }}
              proOptions={{ hideAttribution: true }}
              defaultEdgeOptions={{ type: "default" }}
              style={{ background: "var(--color-bg-canvas)" }}
            >
              <Background
                variant={BackgroundVariant.Dots}
                gap={24}
                size={1}
                color="color-mix(in oklch, var(--color-fg) 6%, transparent)"
              />
              <Controls
                showInteractive={false}
                position="bottom-left"
                style={{
                  background: "var(--color-bg-panel)",
                  border: "1px solid var(--color-border-subtle)",
                }}
              />
              <XYFlowMiniMap
                position="bottom-right"
                pannable
                zoomable
                nodeColor={(n) => miniMapNodeColor(n)}
                maskColor="color-mix(in oklch, var(--color-bg-canvas) 70%, transparent)"
                style={{
                  background: "var(--color-bg-panel)",
                  border: "1px solid var(--color-border-subtle)",
                  borderRadius: 4,
                  width: 160,
                  height: 120,
                }}
              />
            </ReactFlow>
          </div>
        </section>

        {/* Right drawer: NodeInspector */}
        {selectedNode && (
          <NodeInspector
            open
            nodeTitle={(selectedNode.data as CanvasNodeData).label}
            nodeKind={mapKindForInspector((selectedNode.data as CanvasNodeData).backendType)}
            onClose={() => setSelectedNodeId(null)}
            onTitleChange={(next) => updateNodeTitle(selectedNode.id, next)}
            running={(selectedNode.data as CanvasNodeData).runtimeState === "running"}
            // Live runtime control isn't backend-wired; the toggle is read-only here.
            onRunningChange={undefined}
            inputs={describePorts(selectedNode, edges, "in")}
            outputs={describePorts(selectedNode, edges, "out")}
            configuration={
              <InspectorContent
                nodeId={selectedNode.id}
                nodeType={(selectedNode.data as CanvasNodeData).backendType}
                nodeLabel={(selectedNode.data as CanvasNodeData).label}
                config={(selectedNode.data as CanvasNodeData).config ?? {}}
                catalog={catalog}
                onUpdate={(k, v) => updateNodeConfig(selectedNode.id, k, v)}
              />
            }
            liveActivity={
              <div className="flex items-center gap-2">
                <Tag intent="warn">Pending</Tag>
                <span className="text-[11px] text-fg-muted">
                  Per-node activity feed not yet exposed.
                </span>
              </div>
            }
          />
        )}
      </div>
    </div>
  );
}

/* ----------------------------- Adapters ---------------------------------- */

function toReactFlowNodes(
  pipelineNodes: Array<{
    id: string;
    type: string;
    label: string;
    config?: Record<string, unknown>;
    position: { x: number; y: number };
  }>
): Node[] {
  return pipelineNodes.map((n) => ({
    id: n.id,
    type: "default",
    position: n.position,
    data: {
      label: n.label,
      backendType: n.type,
      backendId: n.id,
      config: n.config ?? {},
      runtimeState: "idle",
    } satisfies CanvasNodeData,
    draggable: true,
  }));
}

function toReactFlowEdges(
  pipelineEdges: Array<{
    id: string;
    source: string;
    target: string;
    condition?: string;
  }>
): Edge[] {
  return pipelineEdges.map((e) => ({
    id: e.id,
    source: e.source,
    target: e.target,
    type: "default",
    data: { edgeKind: edgeKindFor(e.target) } satisfies CanvasEdgeData,
    label: e.condition,
  }));
}

function edgeKindFor(targetId: string): "data" | "agent" | "decision" {
  if (
    targetId === "strategy_eval" ||
    targetId === "agent_modifier" ||
    targetId === "risk_gate" ||
    targetId === "validation"
  ) {
    return "decision";
  }
  return "data";
}

function mapKindForInspector(backendType: string) {
  switch (backendType) {
    case "input":
      return "data-source" as const;
    case "agent_input":
    case "meta":
      return "agent" as const;
    case "output":
      return "sink" as const;
    case "gate":
    default:
      return "decision" as const;
  }
}

function describePorts(node: Node, edges: Edge[], side: "in" | "out") {
  const matching =
    side === "in"
      ? edges.filter((e) => e.target === node.id)
      : edges.filter((e) => e.source === node.id);
  if (matching.length === 0) {
    return [
      {
        id: `${node.id}-${side}-empty`,
        label: side === "in" ? "input" : "output",
        connection: side === "in" ? "—" : "—",
      },
    ];
  }
  return matching.map((e, i) => ({
    id: `${node.id}-${side}-${i}`,
    label: side === "in" ? "input" : "output",
    connection: side === "in" ? `← ${e.source}` : `→ ${e.target}`,
  }));
}

function miniMapNodeColor(n: Node): string {
  const d = n.data as CanvasNodeData | undefined;
  if (!d) return "var(--color-neutral-500)";
  if (d.runtimeState === "errored") return "var(--color-ask-500)";
  switch (d.backendType) {
    case "input":
      return "var(--color-neutral-400)";
    case "agent_input":
    case "meta":
      return "var(--color-accent-500)";
    case "output":
      return "var(--color-bid-500)";
    case "gate":
    default:
      return "var(--color-accent-400)";
  }
}

function formatRelative(ms: number): string {
  const diff = Math.max(0, Date.now() - ms);
  const sec = Math.floor(diff / 1000);
  if (sec < 5) return "saved just now";
  if (sec < 60) return `saved ${sec}s ago`;
  const min = Math.floor(sec / 60);
  if (min < 60) return `saved ${min}m ago`;
  const hr = Math.floor(min / 60);
  if (hr < 24) return `saved ${hr}h ago`;
  return `saved ${Math.floor(hr / 24)}d ago`;
}
