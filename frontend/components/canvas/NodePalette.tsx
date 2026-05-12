"use client";

import {
  forwardRef,
  useMemo,
  useState,
  type DragEvent,
  type HTMLAttributes,
  type ReactNode,
} from "react";
import { Search, ChevronDown, ChevronRight } from "lucide-react";
import { cn } from "@/lib/utils";
import { Input } from "@/components/primitives/Input";
import { Kbd } from "@/components/primitives/Kbd";
import { AgentAvatar, type AgentKind } from "@/components/agentic/AgentAvatar";
import type { NodeKind } from "./Node";

/**
 * NodePalette per docs/design/04-component-specs/canvas.md.
 *
 * Searchable categorized list of node types (a *map of capabilities*,
 * not a personalized list — categories and within-category order are
 * fixed by the registry per spec). Drag to canvas to instantiate.
 *
 * Per spec, this is meant to live in the left rail when the Pipeline
 * Canvas is active. The component itself is layout-agnostic — caller
 * controls width.
 */

export interface NodePaletteEntry {
  id: string;
  label: string;
  kind: NodeKind;
  /** Required when kind === "agent". */
  agent?: AgentKind;
  description?: ReactNode;
}

export interface NodePaletteCategory {
  id: string;
  label: string;
  entries: NodePaletteEntry[];
}

/** Reasonable default registry — the actual registry comes from the
 *  backend's node_registry; this is what the design-system page uses. */
export const DEFAULT_NODE_REGISTRY: NodePaletteCategory[] = [
  {
    id: "agents",
    label: "AGENTS",
    entries: [
      { id: "ta", label: "ta_agent", kind: "agent", agent: "ta" },
      {
        id: "regime",
        label: "regime_hmm",
        kind: "agent",
        agent: "regime",
      },
      {
        id: "sentiment",
        label: "sentiment",
        kind: "agent",
        agent: "sentiment",
      },
      {
        id: "slm",
        label: "slm_inference",
        kind: "agent",
        agent: "slm",
      },
      { id: "debate", label: "debate", kind: "agent", agent: "debate" },
    ],
  },
  {
    id: "data-sources",
    label: "DATA SOURCES",
    entries: [
      {
        id: "ingestion",
        label: "ingestion (market data)",
        kind: "data-source",
      },
      {
        id: "archived",
        label: "archived candles",
        kind: "data-source",
      },
    ],
  },
  {
    id: "transforms",
    label: "TRANSFORMS",
    entries: [
      {
        id: "ta_indicator",
        label: "ta_indicator (sma/ema/rsi/…)",
        kind: "transform",
      },
      {
        id: "feature_engineer",
        label: "feature_engineer",
        kind: "transform",
      },
    ],
  },
  {
    id: "decisions",
    label: "DECISIONS",
    entries: [
      { id: "strategy_eval", label: "strategy_eval", kind: "decision" },
      { id: "risk_check", label: "risk_check", kind: "decision" },
    ],
  },
  {
    id: "sinks",
    label: "SINKS",
    entries: [
      { id: "execution_live", label: "execution (live)", kind: "sink" },
      { id: "paper", label: "paper", kind: "sink" },
      { id: "logger", label: "logger", kind: "sink" },
    ],
  },
];

export interface NodePaletteProps
  extends Omit<HTMLAttributes<HTMLDivElement>, "children"> {
  registry?: NodePaletteCategory[];
  /** Called when an entry is clicked (to show description in popover). */
  onEntryClick?: (entry: NodePaletteEntry) => void;
  /** Called when a drag starts — caller wires this up to React Flow's
   *  drop handler at the canvas root. */
  onEntryDragStart?: (entry: NodePaletteEntry, e: DragEvent) => void;
}

const KIND_DOT: Record<NodeKind, string> = {
  agent: "bg-accent-500",
  "data-source": "bg-neutral-400",
  decision: "bg-accent-400",
  sink: "bg-bid-500",
  transform: "bg-fg-muted",
};

export const NodePalette = forwardRef<HTMLDivElement, NodePaletteProps>(
  (
    {
      registry = DEFAULT_NODE_REGISTRY,
      onEntryClick,
      onEntryDragStart,
      className,
      ...props
    },
    ref
  ) => {
    const [query, setQuery] = useState("");
    const [collapsed, setCollapsed] = useState<Set<string>>(new Set());
    const isCollapsed = (id: string) => collapsed.has(id);
    const toggleCategory = (id: string) =>
      setCollapsed((prev) => {
        const next = new Set(prev);
        if (next.has(id)) next.delete(id);
        else next.add(id);
        return next;
      });

    const filtered = useMemo(() => {
      if (!query.trim()) return registry;
      const q = query.toLowerCase();
      return registry
        .map((cat) => ({
          ...cat,
          entries: cat.entries.filter((e) =>
            e.label.toLowerCase().includes(q)
          ),
        }))
        .filter((cat) => cat.entries.length > 0);
    }, [registry, query]);

    return (
      <div
        ref={ref}
        role="tree"
        aria-label="Node palette"
        className={cn(
          "flex flex-col bg-bg-panel border border-border-subtle rounded-md overflow-hidden",
          className
        )}
        {...props}
      >
        <div className="p-2 border-b border-border-subtle">
          <div className="relative">
            <Input
              placeholder="Search nodes"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              density="compact"
              leftAdornment={
                <Search className="w-3.5 h-3.5" strokeWidth={1.5} />
              }
              aria-label="Search nodes"
            />
            <span className="absolute right-2 top-1/2 -translate-y-1/2 pointer-events-none">
              <Kbd keys="mod+/" />
            </span>
          </div>
        </div>

        <div className="flex-1 overflow-y-auto py-1">
          {filtered.length === 0 ? (
            <p className="px-3 py-3 text-[12px] text-fg-muted">
              No nodes match &ldquo;{query}&rdquo;.
            </p>
          ) : (
            filtered.map((cat) => {
              const ic = isCollapsed(cat.id);
              return (
                <div key={cat.id} role="treeitem" aria-expanded={!ic}>
                  <button
                    type="button"
                    onClick={() => toggleCategory(cat.id)}
                    className={cn(
                      "w-full flex items-center gap-1 px-2 h-7 text-[10px] uppercase tracking-wider",
                      "text-fg-muted hover:text-fg",
                      "focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent-500"
                    )}
                  >
                    {ic ? (
                      <ChevronRight
                        className="w-3 h-3"
                        strokeWidth={1.5}
                        aria-hidden
                      />
                    ) : (
                      <ChevronDown
                        className="w-3 h-3"
                        strokeWidth={1.5}
                        aria-hidden
                      />
                    )}
                    <span className="num-tabular">{cat.label}</span>
                  </button>
                  {!ic && (
                    <ul role="group" className="flex flex-col">
                      {cat.entries.map((entry) => (
                        <li key={entry.id}>
                          <button
                            type="button"
                            draggable={!!onEntryDragStart}
                            onDragStart={(e) =>
                              onEntryDragStart?.(entry, e)
                            }
                            onClick={() => onEntryClick?.(entry)}
                            className={cn(
                              "w-full flex items-center gap-2 px-3 h-7 text-[12px] text-fg-secondary",
                              "hover:bg-bg-rowhover hover:text-fg cursor-grab",
                              "focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent-500"
                            )}
                            aria-label={`${entry.kind} node: ${entry.label}`}
                          >
                            {entry.kind === "agent" && entry.agent ? (
                              <AgentAvatar
                                kind={entry.agent}
                                size="sm"
                                className="!w-4 !h-4 ring-[1px]"
                              />
                            ) : (
                              <span
                                aria-hidden
                                className={cn(
                                  "inline-block w-2 h-2 rounded-sm",
                                  KIND_DOT[entry.kind]
                                )}
                              />
                            )}
                            <span className="truncate num-tabular">
                              {entry.label}
                            </span>
                          </button>
                        </li>
                      ))}
                    </ul>
                  )}
                </div>
              );
            })
          )}
        </div>
      </div>
    );
  }
);
NodePalette.displayName = "NodePalette";

export default NodePalette;
