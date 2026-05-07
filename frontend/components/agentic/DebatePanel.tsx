"use client";

import {
  forwardRef,
  useEffect,
  useState,
  type HTMLAttributes,
  type KeyboardEvent,
  type ReactNode,
} from "react";
import { Pause, Play, OctagonX } from "lucide-react";
import { cn } from "@/lib/utils";
import { Button } from "@/components/primitives/Button";
import { AgentAvatar, type AgentKind } from "./AgentAvatar";

/**
 * DebatePanel per docs/design/04-component-specs/agentic.md.
 *
 * A multi-agent argument visualization, custom to Praxis. Each agent
 * contribution: avatar + name + stance (for/against/neutral/synthesis)
 * + reasoning summary (one line, click to expand to full ReasoningStream).
 *
 * Per spec, agent identity color is used ONLY for the avatar ring +
 * stance label underline. Body text remains neutral. Stance labels use
 * semantic colors:
 *   for       → bid.400
 *   against   → ask.400
 *   neutral   → neutral.400
 *   synthesis → accent.300
 *
 * Critical UX rules:
 *   - The orchestrator's synthesis is reachable in a single Tab from
 *     panel focus (the user might be racing to override).
 *   - Keyboard shortcut "O" opens the override modal when panel is
 *     focused.
 *   - Auto-execute on synthesis without surfacing an override window
 *     would be wrong; the configurable `decisionDelaySec` (default 3s)
 *     gives the user time to interrupt.
 */

export type DebateStance = "for" | "against" | "neutral" | "synthesis";
export type DebateState = "live" | "paused" | "superseded";
export type DebateView = "chronological" | "byStance" | "graph";

export interface DebateContribution {
  /** Stable id used for keys and aria. */
  id: string;
  agent: AgentKind;
  agentNameOverride?: string;
  stance: DebateStance;
  /** Single-line reasoning summary; long text gets truncated. */
  summary: ReactNode;
  /** Expanded reasoning content (rendered when the row is expanded). */
  detail?: ReactNode;
  /** Confidence for that agent in [0,1]; rendered as a sliver. */
  confidence?: number;
}

export interface DebatePanelProps
  extends Omit<HTMLAttributes<HTMLDivElement>, "children"> {
  topic: ReactNode;
  /** Round number, e.g., 3 of 5. */
  round?: number;
  totalRounds?: number;
  state: DebateState;
  contributions: DebateContribution[];
  view?: DebateView;
  /** Show intervention controls. */
  interventionEnabled?: boolean;
  /** Compact card form for embedding in Hot Trading / Canvas. */
  embedded?: boolean;
  /** When superseded, link to the round that supersedes this one. */
  supersededByRound?: number;
  onSupersededFollow?: () => void;
  /** Decision delay window for the synthesis (default 3s). */
  decisionDelaySec?: number;
  onOpenRound?: () => void;
  onPause?: () => void;
  onOverride?: () => void;
}

const STANCE_COLOR: Record<DebateStance, string> = {
  for: "text-bid-400 border-bid-400",
  against: "text-ask-400 border-ask-400",
  neutral: "text-neutral-400 border-neutral-400",
  synthesis: "text-accent-300 border-accent-300",
};

const STANCE_LABEL: Record<DebateStance, string> = {
  for: "for",
  against: "against",
  neutral: "neutral",
  synthesis: "synthesis",
};

function ContributionRow({
  contribution,
  expanded,
  onToggleExpand,
  isLive,
  embedded,
}: {
  contribution: DebateContribution;
  expanded: boolean;
  onToggleExpand: () => void;
  isLive: boolean;
  embedded?: boolean;
}) {
  const { agent, agentNameOverride, stance, summary, detail, confidence } =
    contribution;
  return (
    <div
      role="listitem"
      data-stance={stance}
      data-agent={agent}
      className={cn(
        "flex flex-col gap-1 px-3 py-2",
        "border-b border-border-subtle last:border-b-0",
        isLive && stance !== "synthesis" && "animate-pulse-subtle"
      )}
    >
      <div className="flex items-baseline gap-2">
        <AgentAvatar kind={agent} size="sm" nameOverride={agentNameOverride} />
        <span className="text-[12px] font-medium text-fg num-tabular">
          {agentNameOverride ??
            (agent === "debate" ? "orchestrator" : `${agent}_agent`)}
        </span>
        <span
          className={cn(
            "text-[10px] uppercase tracking-wider px-1 border-b",
            STANCE_COLOR[stance]
          )}
        >
          {STANCE_LABEL[stance]}
        </span>
        {confidence !== undefined && (
          <span className="text-[10px] text-fg-muted num-tabular ml-auto">
            {(confidence * 100).toFixed(0)}%
          </span>
        )}
      </div>
      <div className="pl-7 flex items-start gap-1">
        <span className="text-fg-muted text-[12px] mt-px">▶</span>
        <button
          type="button"
          onClick={onToggleExpand}
          aria-expanded={expanded}
          className={cn(
            "text-left flex-1 text-[12px] text-fg-secondary",
            embedded && !expanded && "line-clamp-1",
            "hover:text-fg",
            "focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent-500 rounded-sm"
          )}
        >
          {summary}
        </button>
      </div>
      {expanded && detail !== undefined && (
        <div className="pl-7 pt-1">{detail}</div>
      )}
    </div>
  );
}

export const DebatePanel = forwardRef<HTMLDivElement, DebatePanelProps>(
  (
    {
      topic,
      round,
      totalRounds,
      state,
      contributions,
      view = "chronological",
      interventionEnabled = true,
      embedded = false,
      supersededByRound,
      onSupersededFollow,
      decisionDelaySec = 3,
      onOpenRound,
      onPause,
      onOverride,
      className,
      ...props
    },
    ref
  ) => {
    const [expandedIds, setExpandedIds] = useState<Set<string>>(new Set());
    const toggleExpand = (id: string) =>
      setExpandedIds((prev) => {
        const next = new Set(prev);
        if (next.has(id)) next.delete(id);
        else next.add(id);
        return next;
      });

    // Decision-delay countdown for the synthesis row.
    const [delayLeft, setDelayLeft] = useState<number | null>(null);
    useEffect(() => {
      if (state !== "live") return;
      const synth = contributions.find((c) => c.stance === "synthesis");
      if (!synth) return;
      setDelayLeft(decisionDelaySec);
      const id = window.setInterval(() => {
        setDelayLeft((prev) => {
          if (prev == null) return null;
          if (prev <= 1) {
            window.clearInterval(id);
            return 0;
          }
          return prev - 1;
        });
      }, 1000);
      return () => window.clearInterval(id);
    }, [state, contributions, decisionDelaySec]);

    // Order by view.
    const ordered =
      view === "byStance"
        ? [...contributions].sort((a, b) => {
            const order: Record<DebateStance, number> = {
              for: 0,
              against: 1,
              neutral: 2,
              synthesis: 3,
            };
            return order[a.stance] - order[b.stance];
          })
        : contributions;

    const onKeyDown = (e: KeyboardEvent<HTMLDivElement>) => {
      const target = e.target as HTMLElement;
      const isInput =
        target.tagName === "INPUT" || target.tagName === "TEXTAREA";
      if (isInput) return;
      if ((e.key === "o" || e.key === "O") && interventionEnabled) {
        e.preventDefault();
        onOverride?.();
      }
    };

    return (
      <div
        ref={ref}
        role="region"
        aria-label={
          typeof topic === "string"
            ? `Debate panel: ${topic}`
            : "Debate panel"
        }
        data-state={state}
        data-view={view}
        tabIndex={-1}
        onKeyDown={onKeyDown}
        className={cn(
          "flex flex-col rounded-md border border-border-subtle bg-bg-panel",
          state === "superseded" && "opacity-50",
          className
        )}
        {...props}
      >
        {/* Header: topic + round */}
        <header
          className={cn(
            "flex items-center gap-3 px-3 h-9 border-b border-border-subtle"
          )}
        >
          <span className="text-[10px] uppercase tracking-wider text-fg-muted">
            topic
          </span>
          <span className="flex-1 text-[12px] text-fg truncate">{topic}</span>
          {round !== undefined && (
            <span className="text-[11px] text-fg-muted num-tabular font-mono">
              round {round}
              {totalRounds !== undefined ? `/${totalRounds}` : ""}
            </span>
          )}
        </header>

        {state === "superseded" && supersededByRound !== undefined && (
          <button
            type="button"
            onClick={onSupersededFollow}
            className="text-[11px] text-accent-300 hover:text-accent-200 px-3 py-1.5 border-b border-border-subtle text-left"
          >
            superseded by round {supersededByRound} →
          </button>
        )}

        {/* Body */}
        {view === "graph" ? (
          <div className="px-3 py-6 text-center text-[11px] text-fg-muted">
            Graph view (force-directed) — not yet implemented in v1; showing
            chronological instead.
          </div>
        ) : null}
        <div role="list" className="flex flex-col">
          {ordered.map((c) => (
            <ContributionRow
              key={c.id}
              contribution={c}
              expanded={expandedIds.has(c.id)}
              onToggleExpand={() => toggleExpand(c.id)}
              isLive={state === "live"}
              embedded={embedded}
            />
          ))}
        </div>

        {/* Footer: controls */}
        {interventionEnabled && (
          <footer
            className={cn(
              "flex items-center gap-2 px-3 h-10 border-t border-border-subtle bg-bg-canvas/50"
            )}
          >
            {state === "live" && delayLeft !== null && delayLeft > 0 && (
              <span className="text-[11px] text-warn-500 num-tabular font-mono">
                synthesis pending — {delayLeft}s to override
              </span>
            )}
            <span className="flex-1" />
            {state === "live" && onOpenRound && (
              <Button
                size="xs"
                intent="secondary"
                leftIcon={<Play className="w-3 h-3" strokeWidth={1.5} />}
                onClick={onOpenRound}
              >
                open round
              </Button>
            )}
            {state === "live" && onPause && (
              <Button
                size="xs"
                intent="secondary"
                leftIcon={<Pause className="w-3 h-3" strokeWidth={1.5} />}
                onClick={onPause}
              >
                pause debate
              </Button>
            )}
            {onOverride && (
              <Button
                size="xs"
                intent="danger"
                leftIcon={<OctagonX className="w-3 h-3" strokeWidth={1.5} />}
                onClick={onOverride}
                data-testid="debate-override"
                aria-label="Override decision (O)"
              >
                override decision
              </Button>
            )}
          </footer>
        )}
      </div>
    );
  }
);
DebatePanel.displayName = "DebatePanel";

export default DebatePanel;
