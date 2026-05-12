"use client";

import {
  forwardRef,
  useState,
  type HTMLAttributes,
  type ReactNode,
} from "react";
import { cn } from "@/lib/utils";
import { AgentAvatar, type AgentKind } from "./AgentAvatar";
import { ChevronDown, ChevronRight, ArrowRight } from "lucide-react";

/**
 * AgentTrace per docs/design/04-component-specs/agentic.md.
 *
 * One *atomic event*: an agent received an input, produced an output,
 * and that output flowed somewhere downstream. Each section is
 * collapsible. HOT mode default: everything collapsed except output.
 * Observatory default: everything expanded.
 *
 * Per spec, agent identity color is used ONLY for the avatar ring +
 * section header underline; trace body remains neutral so multiple
 * traces coexist on screen without becoming a Christmas tree.
 */

export type AgentTraceState =
  | "streaming"
  | "complete"
  | "errored"
  | "superseded";

export type AgentTraceDensity = "compact" | "standard" | "expanded";

export interface AgentTraceDownstreamLink {
  label: string;
  href?: string;
  onClick?: () => void;
}

export interface AgentTraceProps
  extends Omit<HTMLAttributes<HTMLDivElement>, "children" | "id"> {
  agent: AgentKind;
  agentNameOverride?: string;
  /** Emission timestamp — number (epoch ms) or pre-formatted string. */
  emittedAt: number | string;
  state: AgentTraceState;
  density?: AgentTraceDensity;
  /** Section content. */
  input?: ReactNode;
  reasoning?: ReactNode;
  output?: ReactNode;
  downstream?: AgentTraceDownstreamLink[];
  /** Error message when state === "errored". */
  error?: string;
  /** Make section headers click-through to canvas/observatory. */
  linkable?: boolean;
  /** Optional anchor id for deep-linking. */
  anchorId?: string;
}

function fmtTime(time: number | string): string {
  if (typeof time === "string") return time;
  const d = new Date(time);
  const hh = String(d.getHours()).padStart(2, "0");
  const mm = String(d.getMinutes()).padStart(2, "0");
  const ss = String(d.getSeconds()).padStart(2, "0");
  const ms = String(d.getMilliseconds()).padStart(3, "0");
  return `${hh}:${mm}:${ss}.${ms}`;
}

const AGENT_LABELS: Record<AgentKind, string> = {
  ta: "ta_agent",
  regime: "regime_hmm",
  sentiment: "sentiment",
  slm: "slm_inference",
  debate: "debate",
  analyst: "analyst",
};

interface SectionProps {
  label: string;
  open: boolean;
  onToggle: () => void;
  children: ReactNode;
  defaultEmpty?: boolean;
}

function TraceSection({
  label,
  open,
  onToggle,
  children,
  defaultEmpty,
}: SectionProps) {
  return (
    <details
      open={open}
      onToggle={(e) => {
        // <details> fires onToggle when the user clicks summary; we proxy it.
        const next = (e.target as HTMLDetailsElement).open;
        if (next !== open) onToggle();
      }}
      className={cn(
        "rounded-sm border border-border-subtle bg-bg-canvas",
        defaultEmpty && "opacity-60"
      )}
    >
      <summary
        className={cn(
          "flex items-center gap-1 px-2 h-6 text-[10px] uppercase tracking-wider",
          "text-fg-muted cursor-pointer list-none select-none",
          "border-b border-transparent",
          // bottom-border in accent indicates the section header underline
          // (per spec: "section header underline" uses agent identity color)
          open && "border-b-accent-500/40 text-fg-secondary"
        )}
      >
        {open ? (
          <ChevronDown className="w-3 h-3" strokeWidth={1.5} aria-hidden />
        ) : (
          <ChevronRight className="w-3 h-3" strokeWidth={1.5} aria-hidden />
        )}
        <span className="num-tabular">{label}</span>
      </summary>
      {open && <div className="px-2 py-1.5 text-[12px] text-fg-secondary">{children}</div>}
    </details>
  );
}

export const AgentTrace = forwardRef<HTMLDivElement, AgentTraceProps>(
  (
    {
      agent,
      agentNameOverride,
      emittedAt,
      state,
      density = "standard",
      input,
      reasoning,
      output,
      downstream,
      error,
      linkable = false,
      anchorId,
      className,
      ...props
    },
    ref
  ) => {
    // Default open-state per density per spec.
    const initialOpen = (() => {
      if (density === "compact") {
        return { input: false, reasoning: false, output: !!output, downstream: false };
      }
      if (density === "expanded") {
        return { input: !!input, reasoning: !!reasoning, output: !!output, downstream: !!downstream?.length };
      }
      // standard: output on, others closed
      return { input: false, reasoning: !!reasoning && state === "streaming", output: !!output, downstream: !!downstream?.length };
    })();

    const [open, setOpen] = useState(initialOpen);

    const stateColor: string =
      state === "errored"
        ? "border-l-ask-500"
        : state === "streaming"
          ? "border-l-accent-500"
          : state === "superseded"
            ? "border-l-neutral-700"
            : "border-l-border-subtle";

    return (
      <article
        ref={ref}
        id={anchorId}
        data-state={state}
        data-agent={agent}
        data-density={density}
        aria-label={`Agent trace from ${agentNameOverride ?? AGENT_LABELS[agent]} at ${fmtTime(emittedAt)}`}
        className={cn(
          "rounded-md bg-bg-panel border border-border-subtle",
          "border-l-2",
          stateColor,
          state === "superseded" && "opacity-60",
          className
        )}
        {...props}
      >
        {/* Header */}
        <header
          className={cn(
            "flex items-center gap-2 px-3 h-9 border-b border-border-subtle"
          )}
        >
          <AgentAvatar
            kind={agent}
            size="sm"
            status={
              state === "streaming"
                ? "live"
                : state === "errored"
                  ? "errored"
                  : "idle"
            }
            nameOverride={agentNameOverride}
          />
          <span className="text-[12px] font-medium text-fg num-tabular">
            {agentNameOverride ?? AGENT_LABELS[agent]}
          </span>
          <span className="text-[10px] text-fg-muted">▸</span>
          <span className="text-[11px] text-fg-muted num-tabular font-mono">
            emitted at {fmtTime(emittedAt)}
          </span>
          <span className="flex-1" />
          {state === "streaming" && (
            <span className="text-[10px] uppercase tracking-wider text-accent-300 num-tabular">
              streaming
            </span>
          )}
          {state === "errored" && (
            <span className="text-[10px] uppercase tracking-wider text-ask-400 num-tabular">
              errored
            </span>
          )}
          {state === "superseded" && (
            <span className="text-[10px] uppercase tracking-wider text-fg-muted num-tabular">
              superseded
            </span>
          )}
        </header>

        {/* Body sections */}
        <div className="flex flex-col gap-1.5 p-3">
          {input !== undefined && (
            <TraceSection
              label="input"
              open={open.input}
              onToggle={() => setOpen((s) => ({ ...s, input: !s.input }))}
            >
              {input}
            </TraceSection>
          )}

          {reasoning !== undefined && (
            <TraceSection
              label="reasoning"
              open={open.reasoning}
              onToggle={() => setOpen((s) => ({ ...s, reasoning: !s.reasoning }))}
            >
              {reasoning}
            </TraceSection>
          )}

          {output !== undefined && (
            <TraceSection
              label={state === "errored" ? "output (failed)" : "output"}
              open={open.output}
              onToggle={() => setOpen((s) => ({ ...s, output: !s.output }))}
            >
              {state === "errored" && error ? (
                <p className="text-ask-300">{error}</p>
              ) : (
                output
              )}
            </TraceSection>
          )}

          {downstream && downstream.length > 0 && (
            <TraceSection
              label="downstream"
              open={open.downstream}
              onToggle={() =>
                setOpen((s) => ({ ...s, downstream: !s.downstream }))
              }
            >
              <ul className="flex flex-col gap-1">
                {downstream.map((d, i) => (
                  <li key={i} className="flex items-center gap-1.5 text-[12px]">
                    <ArrowRight
                      className="w-3 h-3 text-fg-muted"
                      strokeWidth={1.5}
                      aria-hidden
                    />
                    {linkable && (d.href || d.onClick) ? (
                      <a
                        href={d.href}
                        onClick={(e) => {
                          if (d.onClick) {
                            e.preventDefault();
                            d.onClick();
                          }
                        }}
                        className="text-accent-300 hover:text-accent-200"
                      >
                        {d.label}
                      </a>
                    ) : (
                      <span className="text-fg-secondary">{d.label}</span>
                    )}
                  </li>
                ))}
              </ul>
            </TraceSection>
          )}
        </div>
      </article>
    );
  }
);
AgentTrace.displayName = "AgentTrace";

export default AgentTrace;
