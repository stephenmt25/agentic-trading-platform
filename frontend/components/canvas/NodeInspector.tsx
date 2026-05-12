"use client";

import {
  forwardRef,
  useState,
  type HTMLAttributes,
  type ReactNode,
} from "react";
import { ChevronDown, ChevronRight, X, ExternalLink } from "lucide-react";
import { cn } from "@/lib/utils";
import { Button } from "@/components/primitives/Button";
import { Input } from "@/components/primitives/Input";
import { Toggle } from "@/components/primitives/Toggle";
import type { NodeKind } from "./Node";

/**
 * NodeInspector per docs/design/04-component-specs/canvas.md.
 *
 * 380px right drawer. NOT a modal — the user must keep canvas in view
 * while editing. Sections:
 *   1. Header — node title (editable), kind, running/paused toggle
 *   2. Inputs — declared input ports + their current upstream
 *   3. Configuration — typed form for the node's parameters
 *   4. Outputs — declared output ports + their downstream consumers
 *   5. Live activity — small chart of last 100 emissions + trace link
 *   6. Tests — per-node sample-input runner with diff against last result
 *
 * The inspector shape is consistent across node kinds; the *content*
 * of section 3 (Configuration) varies by kind.
 */

export interface NodeInspectorPort {
  id: string;
  label: string;
  /** Description of upstream/downstream node and field. */
  connection?: string;
}

export interface NodeInspectorProps
  extends Omit<HTMLAttributes<HTMLDivElement>, "title"> {
  open: boolean;
  onClose?: () => void;
  /** Node identity */
  nodeTitle: string;
  nodeKind: NodeKind;
  onTitleChange?: (next: string) => void;
  /** Running/paused state */
  running: boolean;
  onRunningChange?: (next: boolean) => void;
  inputs?: NodeInspectorPort[];
  outputs?: NodeInspectorPort[];
  /** Configuration form — caller composes with Input/Select/Toggle. */
  configuration?: ReactNode;
  /** Live activity slot — caller passes a sparkline / KeyValue grid. */
  liveActivity?: ReactNode;
  /** Tests slot — caller passes a sample runner. */
  tests?: ReactNode;
  /** Click "trace ▸" link — opens Observatory for this node. */
  onOpenObservatory?: () => void;
  /** Optional drawer width override (default 380). */
  width?: number;
}

interface SectionProps {
  title: string;
  defaultOpen?: boolean;
  children: ReactNode;
}

function InspectorSection({
  title,
  defaultOpen = true,
  children,
}: SectionProps) {
  const [open, setOpen] = useState(defaultOpen);
  return (
    <section className="border-b border-border-subtle">
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        aria-expanded={open}
        className={cn(
          "w-full flex items-center gap-1 px-3 h-8 text-[10px] uppercase tracking-wider",
          "text-fg-muted hover:text-fg-secondary",
          "focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent-500"
        )}
      >
        {open ? (
          <ChevronDown className="w-3 h-3" strokeWidth={1.5} aria-hidden />
        ) : (
          <ChevronRight className="w-3 h-3" strokeWidth={1.5} aria-hidden />
        )}
        <span className="num-tabular">{title}</span>
      </button>
      {open && <div className="px-3 pb-3">{children}</div>}
    </section>
  );
}

const KIND_LABEL: Record<NodeKind, string> = {
  agent: "agent",
  "data-source": "data source",
  decision: "decision",
  sink: "sink",
  transform: "transform",
};

export const NodeInspector = forwardRef<HTMLDivElement, NodeInspectorProps>(
  (
    {
      open,
      onClose,
      nodeTitle,
      nodeKind,
      onTitleChange,
      running,
      onRunningChange,
      inputs,
      outputs,
      configuration,
      liveActivity,
      tests,
      onOpenObservatory,
      width = 380,
      className,
      ...props
    },
    ref
  ) => {
    const [titleEditing, setTitleEditing] = useState(false);
    const [titleDraft, setTitleDraft] = useState(nodeTitle);

    if (!open) return null;

    const commitTitle = () => {
      setTitleEditing(false);
      if (titleDraft.trim() && titleDraft !== nodeTitle) {
        onTitleChange?.(titleDraft.trim());
      } else {
        setTitleDraft(nodeTitle);
      }
    };

    return (
      <aside
        ref={ref}
        role="complementary"
        aria-label={`Inspector for ${nodeTitle}`}
        data-kind={nodeKind}
        className={cn(
          "flex flex-col bg-bg-panel border-l border-border-subtle h-full",
          className
        )}
        style={{ width }}
        {...props}
      >
        {/* 1. Header */}
        <header className="flex items-start gap-2 p-3 border-b border-border-subtle">
          <div className="flex-1 min-w-0">
            {titleEditing ? (
              <Input
                value={titleDraft}
                onChange={(e) => setTitleDraft(e.target.value)}
                onBlur={commitTitle}
                onKeyDown={(e) => {
                  if (e.key === "Enter") commitTitle();
                  if (e.key === "Escape") {
                    setTitleDraft(nodeTitle);
                    setTitleEditing(false);
                  }
                }}
                density="compact"
                aria-label="Node title"
                autoFocus
              />
            ) : (
              <button
                type="button"
                onClick={() => onTitleChange && setTitleEditing(true)}
                className={cn(
                  "text-left text-[14px] font-semibold text-fg num-tabular truncate w-full",
                  onTitleChange && "hover:text-accent-300 cursor-text"
                )}
                aria-label="Edit node title"
              >
                {nodeTitle}
              </button>
            )}
            <p className="text-[10px] uppercase tracking-wider text-fg-muted mt-0.5 num-tabular">
              {KIND_LABEL[nodeKind]}
            </p>
          </div>

          <span className="inline-flex items-center gap-1.5">
            <Toggle
              checked={running}
              onCheckedChange={(v) => onRunningChange?.(v)}
              size="sm"
              tone="bid"
              label={running ? "Pause node" : "Resume node"}
            />
            <span className="text-[11px] text-fg-secondary">
              {running ? "running" : "paused"}
            </span>
          </span>

          {onClose && (
            <button
              type="button"
              onClick={onClose}
              aria-label="Close inspector"
              className="text-fg-muted hover:text-fg focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent-500 rounded-sm ml-1"
            >
              <X className="w-4 h-4" strokeWidth={1.5} aria-hidden />
            </button>
          )}
        </header>

        <div className="flex-1 overflow-y-auto">
          {/* 2. Inputs */}
          {inputs && inputs.length > 0 && (
            <InspectorSection title="inputs">
              <ul className="flex flex-col gap-1.5">
                {inputs.map((p) => (
                  <li
                    key={p.id}
                    className="flex items-baseline justify-between gap-2 text-[12px]"
                  >
                    <span className="text-fg-secondary num-tabular">
                      {p.label}
                    </span>
                    <span className="text-fg-muted truncate font-mono text-[11px]">
                      {p.connection ?? "—"}
                    </span>
                  </li>
                ))}
              </ul>
            </InspectorSection>
          )}

          {/* 3. Configuration — kind-specific content */}
          {configuration !== undefined && (
            <InspectorSection title="configuration">
              <div className="flex flex-col gap-3">{configuration}</div>
            </InspectorSection>
          )}

          {/* 4. Outputs */}
          {outputs && outputs.length > 0 && (
            <InspectorSection title="outputs">
              <ul className="flex flex-col gap-1.5">
                {outputs.map((p) => (
                  <li
                    key={p.id}
                    className="flex items-baseline justify-between gap-2 text-[12px]"
                  >
                    <span className="text-fg-secondary num-tabular">
                      {p.label}
                    </span>
                    <span className="text-fg-muted truncate font-mono text-[11px]">
                      {p.connection ?? "—"}
                    </span>
                  </li>
                ))}
              </ul>
            </InspectorSection>
          )}

          {/* 5. Live activity */}
          {liveActivity !== undefined && (
            <InspectorSection title="live activity">
              <div className="flex flex-col gap-2">
                {liveActivity}
                {onOpenObservatory && (
                  <button
                    type="button"
                    onClick={onOpenObservatory}
                    className="self-start inline-flex items-center gap-0.5 text-[11px] text-accent-300 hover:text-accent-200"
                  >
                    trace
                    <ExternalLink className="w-3 h-3" strokeWidth={1.5} aria-hidden />
                  </button>
                )}
              </div>
            </InspectorSection>
          )}

          {/* 6. Tests */}
          {tests !== undefined && (
            <InspectorSection title="tests" defaultOpen={false}>
              {tests}
            </InspectorSection>
          )}
        </div>

        {/* Footer — quick action */}
        {onClose && (
          <footer className="border-t border-border-subtle p-2 flex items-center justify-end gap-2">
            <Button size="xs" intent="secondary" onClick={onClose}>
              close
            </Button>
          </footer>
        )}
      </aside>
    );
  }
);
NodeInspector.displayName = "NodeInspector";

export default NodeInspector;
