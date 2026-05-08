"use client";

import { Tag } from "@/components/primitives";
import { ConfidenceBar, type ConfidenceSegment } from "@/components/agentic";
import { AgentTrace } from "@/components/agentic";
import { Sparkline } from "@/components/data-display";
import type { AgentInfo, AgentTelemetryEvent } from "@/lib/types/telemetry";
import type { AgentKind } from "@/components/agentic/AgentAvatar";
import { backendIdToKind } from "./eventHelpers";

/**
 * Right-column focus panel (460px) per surface spec §4 (selected) and §5
 * (default summary dashboard).
 *
 * Selected: full trace detail (input/reasoning/output/downstream).
 * Default: per-agent state cards (regime probabilities, sentiment, ta, health).
 */

interface FocusPanelProps {
  selectedEvent: AgentTelemetryEvent | null;
  agents: Record<string, AgentInfo>;
  recentEvents: AgentTelemetryEvent[];
}

export function FocusPanel({
  selectedEvent,
  agents,
  recentEvents,
}: FocusPanelProps) {
  return (
    <aside
      className="w-[460px] shrink-0 border-l border-border-subtle bg-bg-panel flex flex-col overflow-hidden"
      aria-label="Focus panel"
    >
      <header className="flex items-center gap-2 px-4 h-9 border-b border-border-subtle">
        <span className="text-[10px] uppercase tracking-wider text-fg-muted num-tabular">
          {selectedEvent ? "focus — trace" : "focus — summary"}
        </span>
      </header>
      <div className="flex-1 overflow-y-auto p-4 flex flex-col gap-4">
        {selectedEvent ? (
          <SelectedTrace event={selectedEvent} />
        ) : (
          <SummaryDashboard agents={agents} recentEvents={recentEvents} />
        )}
      </div>
    </aside>
  );
}

/* -------------------------- Selected trace -------------------------------- */

function SelectedTrace({ event }: { event: AgentTelemetryEvent }) {
  const kind = backendIdToKind(event.agent_id);
  if (!kind) {
    return (
      <pre className="text-[11px] font-mono text-fg-secondary bg-bg-canvas border border-border-subtle rounded-sm p-2 overflow-x-auto">
        {JSON.stringify(event, null, 2)}
      </pre>
    );
  }

  const payload = event.payload ?? {};
  const inputs = payload.inputs as Record<string, unknown> | undefined;
  const output = payload.output as Record<string, unknown> | undefined;
  const reasoning = payload.reasoning as string | undefined;
  const logicPath = payload.logic_path as string[] | undefined;

  return (
    <div className="flex flex-col gap-3">
      <AgentTrace
        agent={kind}
        emittedAt={new Date(event.timestamp).getTime()}
        state={event.event_type === "error" ? "errored" : "complete"}
        density="expanded"
        input={
          inputs ? (
            <pre className="font-mono text-[11px] text-fg-secondary whitespace-pre-wrap break-words">
              {JSON.stringify(inputs, null, 2)}
            </pre>
          ) : (
            <span className="text-fg-muted">no input recorded</span>
          )
        }
        reasoning={
          reasoning ? (
            <p className="text-[12px] text-fg-secondary whitespace-pre-wrap">
              {reasoning}
            </p>
          ) : logicPath && logicPath.length > 0 ? (
            <ol className="text-[12px] text-fg-secondary list-decimal pl-4 flex flex-col gap-0.5">
              {logicPath.map((step, i) => (
                <li key={i} className="font-mono">
                  {step}
                </li>
              ))}
            </ol>
          ) : (
            <span className="text-fg-muted">no reasoning recorded</span>
          )
        }
        output={
          output ? (
            <pre className="font-mono text-[11px] text-fg-secondary whitespace-pre-wrap break-words">
              {JSON.stringify(output, null, 2)}
            </pre>
          ) : (
            <span className="text-fg-muted">no output recorded</span>
          )
        }
        error={(payload.error as string | undefined) ?? undefined}
      />

      <div className="flex flex-col gap-1.5">
        <span className="text-[10px] uppercase tracking-wider text-fg-muted num-tabular">
          downstream
        </span>
        <div className="flex items-center gap-2">
          <Tag intent="warn">Pending</Tag>
          <span className="text-[11px] text-fg-muted">
            Downstream consumer wiring isn&apos;t exposed in telemetry yet.
          </span>
        </div>
      </div>

      <div className="flex flex-col gap-1.5">
        <span className="text-[10px] uppercase tracking-wider text-fg-muted num-tabular">
          actions
        </span>
        <div className="flex items-center gap-2">
          <Tag intent="warn">Pending</Tag>
          <span className="text-[11px] text-fg-muted">
            Override / silence / replay actions land with the intervention API.
          </span>
        </div>
      </div>
    </div>
  );
}

/* -------------------------- Summary dashboard ----------------------------- */

function SummaryDashboard({
  agents,
  recentEvents,
}: {
  agents: Record<string, AgentInfo>;
  recentEvents: AgentTelemetryEvent[];
}) {
  const regime = lastDecisionFor(recentEvents, "regime_hmm");
  const sentiment = lastDecisionFor(recentEvents, "sentiment");
  const ta = lastDecisionFor(recentEvents, "ta_agent");

  const sentimentSeries = recentSeries(recentEvents, "sentiment", "score");

  // Health rollup across the 6 agentic agents.
  const watched = ["ta_agent", "regime_hmm", "sentiment", "debate", "analyst"];
  let live = 0,
    idle = 0,
    errored = 0;
  for (const id of watched) {
    const info = agents[id];
    if (!info) continue;
    if (info.health === "error" || info.health === "offline") errored++;
    else if (info.health === "degraded") idle++;
    else live++;
  }

  return (
    <div className="flex flex-col gap-4">
      <SummaryCard title="REGIME (regime_hmm)">
        {regime ? (
          <RegimeReadout output={regime.output} />
        ) : (
          <EmptyHint label="No regime emission in this window." />
        )}
      </SummaryCard>

      <SummaryCard title="SENTIMENT (sentiment)">
        {sentiment ? (
          <SentimentReadout
            output={sentiment.output}
            series={sentimentSeries}
          />
        ) : (
          <EmptyHint label="No sentiment emission in this window." />
        )}
      </SummaryCard>

      <SummaryCard title="TA SIGNAL (ta_agent)">
        {ta ? (
          <TAReadout output={ta.output} />
        ) : (
          <EmptyHint label="No TA emission in this window." />
        )}
      </SummaryCard>

      <SummaryCard title="ACTIVE DEBATE">
        <div className="flex items-center gap-2">
          <Tag intent="warn">Pending</Tag>
          <span className="text-[11px] text-fg-muted">
            Debate events not yet emitted as a structured telemetry type.
          </span>
        </div>
      </SummaryCard>

      <SummaryCard title="AGENT HEALTH">
        <div className="flex items-center gap-3 text-[12px] text-fg-secondary">
          <span className="num-tabular">
            <span className="text-bid-300">{live}</span> live
          </span>
          <span className="num-tabular">
            <span className="text-fg-muted">{idle}</span> idle
          </span>
          <span className="num-tabular">
            <span className="text-ask-300">{errored}</span> errored
          </span>
        </div>
      </SummaryCard>
    </div>
  );
}

function SummaryCard({
  title,
  children,
}: {
  title: string;
  children: React.ReactNode;
}) {
  return (
    <section className="rounded-md border border-border-subtle bg-bg-canvas">
      <header className="flex items-center px-3 h-7 border-b border-border-subtle">
        <span className="text-[10px] uppercase tracking-wider text-fg-muted num-tabular">
          {title}
        </span>
      </header>
      <div className="px-3 py-2.5">{children}</div>
    </section>
  );
}

function EmptyHint({ label }: { label: string }) {
  return <p className="text-[11px] text-fg-muted">{label}</p>;
}

/* -------------------------- Readouts -------------------------------------- */

function RegimeReadout({ output }: { output: Record<string, unknown> }) {
  // Common regime payload shapes: { regime: "choppy", probabilities: {...} } or
  // { trending: 0.18, choppy: 0.71, reversal: 0.11 }.
  const probs =
    (output.probabilities as Record<string, number> | undefined) ??
    onlyNumberFields(output);

  const segments: ConfidenceSegment[] = Object.entries(probs).map(
    ([label, p], i) => ({
      label,
      probability: clamp01(p),
      tone:
        i === 0
          ? "accent-strong"
          : i === 1
            ? "accent"
            : "accent-weak",
    })
  );

  if (segments.length === 0) {
    return (
      <pre className="font-mono text-[11px] text-fg-secondary whitespace-pre-wrap break-words">
        {JSON.stringify(output, null, 2)}
      </pre>
    );
  }

  return <ConfidenceBar segments={segments} density="compact" />;
}

function SentimentReadout({
  output,
  series,
}: {
  output: Record<string, unknown>;
  series: number[];
}) {
  const score = pickNumber(output, ["score", "sentiment", "value"]);
  const conf = pickNumber(output, ["confidence", "conf"]);
  return (
    <div className="flex flex-col gap-1.5">
      <div className="flex items-baseline gap-3 text-[12px] num-tabular">
        <span className="text-fg">
          score:{" "}
          <span className={score !== null && score < 0 ? "text-ask-300" : "text-bid-300"}>
            {score !== null ? score.toFixed(2) : "—"}
          </span>
        </span>
        {conf !== null && (
          <span className="text-fg-muted">
            confidence: {(conf * 100).toFixed(0)}%
          </span>
        )}
      </div>
      {series.length > 1 && (
        <Sparkline
          values={series}
          height={28}
          width={200}
          tone={
            series[series.length - 1] >= series[0] ? "bid" : "ask"
          }
        />
      )}
    </div>
  );
}

function TAReadout({ output }: { output: Record<string, unknown> }) {
  const direction =
    (output.direction as string | undefined) ??
    (output.signal as string | undefined) ??
    "—";
  const strength =
    (output.strength as string | undefined) ??
    (output.confidence_label as string | undefined) ??
    null;
  return (
    <div className="text-[12px] text-fg num-tabular">
      <span
        className={
          direction.toLowerCase().includes("long")
            ? "text-bid-300"
            : direction.toLowerCase().includes("short")
              ? "text-ask-300"
              : "text-fg-secondary"
        }
      >
        {direction}
        {strength ? ` (${strength})` : ""}
      </span>
    </div>
  );
}

/* -------------------------- Helpers --------------------------------------- */

function lastDecisionFor(
  events: AgentTelemetryEvent[],
  agentId: string
): { output: Record<string, unknown>; ts: string } | null {
  for (let i = events.length - 1; i >= 0; i--) {
    const e = events[i];
    if (e.agent_id !== agentId) continue;
    const payload = e.payload ?? {};
    const out =
      (payload.output as Record<string, unknown> | undefined) ??
      (e.event_type === "decision_trace" ? payload : undefined);
    if (out && typeof out === "object") {
      return { output: out, ts: e.timestamp };
    }
  }
  return null;
}

function recentSeries(
  events: AgentTelemetryEvent[],
  agentId: string,
  field: string
): number[] {
  const out: number[] = [];
  for (const e of events) {
    if (e.agent_id !== agentId) continue;
    const payload = e.payload ?? {};
    const direct = payload[field];
    const nested =
      typeof payload.output === "object" && payload.output
        ? (payload.output as Record<string, unknown>)[field]
        : undefined;
    const v = typeof direct === "number" ? direct : typeof nested === "number" ? nested : null;
    if (v !== null && Number.isFinite(v)) out.push(v);
  }
  return out.slice(-60);
}

function onlyNumberFields(obj: Record<string, unknown>): Record<string, number> {
  const out: Record<string, number> = {};
  for (const [k, v] of Object.entries(obj)) {
    if (typeof v === "number" && Number.isFinite(v)) out[k] = v;
  }
  return out;
}

function pickNumber(obj: Record<string, unknown>, keys: string[]): number | null {
  for (const k of keys) {
    const v = obj[k];
    if (typeof v === "number" && Number.isFinite(v)) return v;
  }
  return null;
}

function clamp01(n: number): number {
  if (!Number.isFinite(n)) return 0;
  return Math.max(0, Math.min(1, n));
}

// silence unused-import warning by re-exporting AgentKind for callers that need it
export type { AgentKind };
