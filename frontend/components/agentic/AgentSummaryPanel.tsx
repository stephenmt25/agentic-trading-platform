"use client";

import {
  forwardRef,
  type HTMLAttributes,
  type ReactNode,
} from "react";
import { ArrowUpRight } from "lucide-react";
import { cn } from "@/lib/utils";
import { AgentTrace, type AgentTraceProps } from "./AgentTrace";
import { DebatePanel, type DebatePanelProps } from "./DebatePanel";

/**
 * AgentSummaryPanel per docs/design/04-component-specs/agentic.md.
 *
 * A composite, surface-level affordance for Hot Trading — NOT a generic
 * primitive. Header + up to 3 compact AgentTrace cards + up to 1 active
 * embedded DebatePanel.
 *
 * Constraints (per spec):
 *   - max-height ≤300px (Hot Trading doesn't have more vertical budget)
 *   - read-only — intervention controls live on Observatory
 *   - snap-replace oldest on new emissions; no auto-scroll
 *   - "see all in Observatory ▸" link present
 */

export type AgentSummaryState =
  | "default"
  | "empty"
  | "agents-paused"
  | "service-degraded";

export interface AgentSummaryPanelProps
  extends Omit<HTMLAttributes<HTMLDivElement>, "children" | "title"> {
  /** Recent traces, newest-first. Component will cap to maxItems. */
  traces: AgentTraceProps[];
  /** Optional active debate, embedded form. */
  debate?: DebatePanelProps;
  state?: AgentSummaryState;
  /** Cap on traces displayed. Default 3 with debate, 4 without. */
  maxItems?: number;
  /** Click handler for "see all" link. */
  onSeeAll?: () => void;
  /** Optional href for the see-all link (renders an anchor instead). */
  seeAllHref?: string;
  /** Header label. Default "AGENTS — recent". */
  title?: ReactNode;
  /** Cached-output age string for service-degraded state. */
  degradedSinceText?: string;
}

export const AgentSummaryPanel = forwardRef<
  HTMLDivElement,
  AgentSummaryPanelProps
>(
  (
    {
      traces,
      debate,
      state = "default",
      maxItems,
      onSeeAll,
      seeAllHref,
      title = "AGENTS — recent",
      degradedSinceText,
      className,
      ...props
    },
    ref
  ) => {
    const cap = maxItems ?? (debate ? 3 : 4);
    const visible = traces.slice(0, cap);

    return (
      <section
        ref={ref}
        aria-label="Agent summary"
        data-state={state}
        className={cn(
          "flex flex-col rounded-md border border-border-subtle bg-bg-panel",
          // Spec cap: ≤300px tall in Hot Trading
          "max-h-[300px]",
          className
        )}
        {...props}
      >
        <header className="flex items-center gap-2 px-3 h-7 border-b border-border-subtle">
          <span className="text-[10px] uppercase tracking-wider text-fg-muted num-tabular">
            {title}
          </span>
          <span className="flex-1" />
          {(onSeeAll || seeAllHref) &&
            (seeAllHref ? (
              <a
                href={seeAllHref}
                onClick={(e) => {
                  if (onSeeAll) {
                    e.preventDefault();
                    onSeeAll();
                  }
                }}
                className="inline-flex items-center gap-0.5 text-[11px] text-accent-300 hover:text-accent-200"
              >
                see all
                <ArrowUpRight className="w-3 h-3" strokeWidth={1.5} aria-hidden />
              </a>
            ) : (
              <button
                type="button"
                onClick={onSeeAll}
                className="inline-flex items-center gap-0.5 text-[11px] text-accent-300 hover:text-accent-200"
              >
                see all
                <ArrowUpRight className="w-3 h-3" strokeWidth={1.5} aria-hidden />
              </button>
            ))}
        </header>

        {state === "empty" && (
          <p className="px-3 py-3 text-[12px] text-fg-muted">
            No agent emissions for this symbol in the last 5 minutes.
          </p>
        )}
        {state === "agents-paused" && (
          <p className="px-3 py-3 text-[12px] text-fg-muted">
            Agents are paused for this profile. Resume in Pipeline Canvas.
          </p>
        )}
        {state === "service-degraded" && (
          <p className="px-3 py-3 text-[12px] text-warn-500">
            Agent feed degraded — showing last cached output
            {degradedSinceText ? ` (${degradedSinceText})` : ""}.
          </p>
        )}

        {state === "default" && (
          <div className="overflow-y-auto flex flex-col">
            {debate && (
              <div className="border-b border-border-subtle p-2">
                <DebatePanel {...debate} embedded />
              </div>
            )}
            <ul className="flex flex-col">
              {visible.map((t, i) => (
                <li
                  key={i}
                  className="border-b last:border-b-0 border-border-subtle p-2"
                >
                  <AgentTrace {...t} density="compact" />
                </li>
              ))}
              {visible.length === 0 && !debate && (
                <li className="px-3 py-3 text-[12px] text-fg-muted">
                  No recent emissions.
                </li>
              )}
            </ul>
          </div>
        )}
      </section>
    );
  }
);
AgentSummaryPanel.displayName = "AgentSummaryPanel";

export default AgentSummaryPanel;
