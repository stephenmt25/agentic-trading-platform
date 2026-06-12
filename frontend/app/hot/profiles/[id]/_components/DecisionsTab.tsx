"use client";

import { useMemo, useState } from "react";
import Link from "next/link";
import { ChevronRight, RefreshCw } from "lucide-react";
import { type TradeDecision } from "@/lib/api/client";
import { useDecisions } from "@/lib/api/hooks";
import { Pill } from "@/components/data-display";
import { cn } from "@/lib/utils";
import { DetailDrawer } from "./DetailDrawer";

interface DecisionsTabProps {
  profileId: string;
  selectedId: string | null;
  onSelect: (id: string | null) => void;
}

type Filter = "all" | "approved" | "blocked";

const FILTERS: { id: Filter; label: string }[] = [
  { id: "all", label: "All" },
  { id: "approved", label: "Approved" },
  { id: "blocked", label: "Blocked" },
];

export function DecisionsTab({
  profileId,
  selectedId,
  onSelect,
}: DecisionsTabProps) {
  const [filter, setFilter] = useState<Filter>("all");

  // FE-W2.1: shared ["decisions", profile, outcome, limit] query, 15s
  // refetchInterval baked into the hook. A filter change changes the key,
  // so isPending covers the "fresh filter" loading state the old
  // setLoading(true) reset provided.
  const decisionsQuery = useDecisions({
    profileId,
    outcome: filter === "approved" ? "APPROVED" : undefined,
    limit: 100,
  });
  const rows = useMemo<TradeDecision[]>(() => {
    const data = decisionsQuery.data ?? [];
    return filter === "blocked"
      ? data.filter((d) => d.outcome !== "APPROVED")
      : data;
  }, [decisionsQuery.data, filter]);
  const loading = decisionsQuery.isPending;
  const refreshing = decisionsQuery.isFetching;
  const error = decisionsQuery.error
    ? decisionsQuery.error instanceof Error
      ? decisionsQuery.error.message
      : "Failed to load decisions"
    : null;
  const load = () => decisionsQuery.refetch();

  const selected = useMemo(
    () => rows.find((r) => r.event_id === selectedId) ?? null,
    [rows, selectedId]
  );

  return (
    <div className="flex flex-col h-full min-h-0">
      <div className="shrink-0 flex items-center justify-between gap-2 px-4 py-2.5 border-b border-border-subtle">
        <div className="flex items-center gap-1.5">
          {FILTERS.map((f) => {
            const active = filter === f.id;
            return (
              <button
                key={f.id}
                type="button"
                onClick={() => setFilter(f.id)}
                aria-pressed={active}
                className={cn(
                  "h-7 px-2.5 rounded-md text-[11px] num-tabular border",
                  "focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent-500",
                  active
                    ? "border-accent-500/40 bg-accent-500/10 text-accent-300"
                    : "border-border-subtle bg-bg-canvas text-fg-secondary hover:text-fg hover:bg-bg-raised"
                )}
              >
                {f.label}
              </button>
            );
          })}
        </div>
        <div className="flex items-center gap-2 text-[11px] text-fg-muted num-tabular">
          <span>
            {rows.length} {filter} decision{rows.length === 1 ? "" : "s"}
          </span>
          <button
            type="button"
            onClick={load}
            aria-label="Refresh"
            className="h-7 w-7 rounded-md flex items-center justify-center text-fg-muted hover:text-fg hover:bg-bg-raised"
          >
            <RefreshCw
              className={cn(
                "w-3 h-3",
                refreshing && "animate-spin will-change-transform"
              )}
              strokeWidth={1.5}
              aria-hidden
            />
          </button>
        </div>
      </div>

      <div className="flex-1 min-h-0 overflow-auto">
        {error ? (
          <ErrorBlock message={error} />
        ) : !loading && rows.length === 0 ? (
          <EmptyBlock />
        ) : (
          <table className="w-full text-[12px] num-tabular border-separate border-spacing-0">
            <thead className="sticky top-0 z-10 bg-bg-canvas">
              <tr>
                <Th align="left">Time</Th>
                <Th align="left">Symbol</Th>
                <Th align="left">Outcome</Th>
                <Th align="right">Direction</Th>
                <Th align="right">Confidence</Th>
                <Th align="right">RSI</Th>
                <Th align="right">ATR</Th>
                <Th align="right" />
              </tr>
            </thead>
            <tbody>
              {rows.map((d) => (
                <DecisionRow
                  key={d.event_id}
                  decision={d}
                  selected={selectedId === d.event_id}
                  onSelect={() =>
                    onSelect(selectedId === d.event_id ? null : d.event_id)
                  }
                />
              ))}
            </tbody>
          </table>
        )}
      </div>

      <DetailDrawer
        open={!!selected}
        onClose={() => onSelect(null)}
        kind="decision"
        title={
          selected
            ? `${selected.symbol} · ${selected.strategy.direction}`
            : "Decision"
        }
        subtitle={
          selected ? (
            <span className="flex items-center gap-1.5 font-mono">
              <span>{formatTime(selected.created_at)}</span>
              <span aria-hidden>·</span>
              <span className="truncate">{selected.event_id.slice(0, 8)}…</span>
            </span>
          ) : undefined
        }
        actions={
          selected ? (
            <Link
              href={`/hot/${encodeURIComponent(selected.symbol)}`}
              className="text-[11px] text-accent-300 hover:text-accent-200 inline-flex items-center gap-0.5 num-tabular px-1.5 py-0.5 rounded-md hover:bg-bg-raised"
            >
              open {selected.symbol}
              <ChevronRight className="w-3 h-3" strokeWidth={1.5} aria-hidden />
            </Link>
          ) : undefined
        }
      >
        {selected && <DecisionDetail decision={selected} />}
      </DetailDrawer>
    </div>
  );
}

function Th({
  children,
  align = "left",
}: {
  children?: React.ReactNode;
  align?: "left" | "right";
}) {
  return (
    <th
      className={cn(
        "px-3 h-8 text-[10px] uppercase tracking-wider font-medium text-fg-muted",
        "bg-bg-canvas border-b border-border-subtle",
        align === "right" ? "text-right" : "text-left"
      )}
    >
      {children}
    </th>
  );
}

function DecisionRow({
  decision,
  selected,
  onSelect,
}: {
  decision: TradeDecision;
  selected: boolean;
  onSelect: () => void;
}) {
  const isApproved = decision.outcome === "APPROVED";
  const confidence =
    decision.agents?.confidence_after ?? decision.strategy.base_confidence;
  return (
    <tr
      onClick={onSelect}
      className={cn(
        "cursor-pointer group",
        selected
          ? "bg-accent-500/10"
          : "bg-transparent hover:bg-bg-rowhover"
      )}
      aria-selected={selected}
    >
      <Td>
        <span
          aria-hidden
          className={cn(
            "absolute left-0 top-0 bottom-0 w-0.5",
            isApproved ? "bg-bid-500/60" : "bg-danger-500/60",
            selected && "bg-accent-500"
          )}
        />
        <span className="font-mono text-fg-secondary">
          {formatTime(decision.created_at)}
        </span>
      </Td>
      <Td>
        <span className="font-mono text-fg">{decision.symbol}</span>
      </Td>
      <Td>
        <Pill intent={isApproved ? "bid" : "danger"}>
          {decision.outcome.toLowerCase()}
        </Pill>
      </Td>
      <Td align="right">
        <span
          className={cn(
            "font-mono",
            decision.strategy.direction === "BUY"
              ? "text-bid-300"
              : decision.strategy.direction === "SELL"
                ? "text-ask-400"
                : "text-fg-muted"
          )}
        >
          {decision.strategy.direction || "—"}
        </span>
      </Td>
      <Td align="right">
        <span className="font-mono text-fg">
          {typeof confidence === "number" ? confidence.toFixed(2) : "—"}
        </span>
      </Td>
      <Td align="right">
        <span className="font-mono text-fg-secondary">
          {decision.indicators?.rsi !== undefined
            ? decision.indicators.rsi.toFixed(1)
            : "—"}
        </span>
      </Td>
      <Td align="right">
        <span className="font-mono text-fg-secondary">
          {decision.indicators?.atr !== undefined
            ? decision.indicators.atr.toFixed(2)
            : "—"}
        </span>
      </Td>
      <Td align="right">
        <ChevronRight
          className={cn(
            "w-3.5 h-3.5 transition-opacity ml-auto",
            selected
              ? "text-accent-300 opacity-100"
              : "text-fg-muted opacity-0 group-hover:opacity-100"
          )}
          strokeWidth={1.5}
          aria-hidden
        />
      </Td>
    </tr>
  );
}

function Td({
  children,
  align = "left",
}: {
  children: React.ReactNode;
  align?: "left" | "right";
}) {
  return (
    <td
      className={cn(
        "relative px-3 h-8 border-b border-border-subtle/60",
        align === "right" ? "text-right" : "text-left"
      )}
    >
      {children}
    </td>
  );
}

function DecisionDetail({ decision }: { decision: TradeDecision }) {
  const agentRows = useMemo(() => {
    const a = decision.agents;
    if (!a) return [];
    const rows: Array<{ name: string; score: number | null; weight: number }> = [];
    if (a.ta) rows.push({ name: "ta", score: a.ta.score, weight: a.ta.weight });
    if (a.sentiment)
      rows.push({
        name: "sentiment",
        score: a.sentiment.score,
        weight: a.sentiment.weight,
      });
    if (a.debate)
      rows.push({
        name: "debate",
        score: a.debate.score,
        weight: a.debate.weight,
      });
    return rows;
  }, [decision]);

  const gateEntries = Object.entries(decision.gates ?? {});
  const passedConds = decision.strategy.conditions ?? [];

  return (
    <div className="px-4 py-3 flex flex-col gap-4 text-[12px]">
      <Section label="Setup">
        <KV
          label="Strategy"
          value={decision.strategy.logic || "—"}
        />
        <KV
          label="Direction"
          value={
            <span
              className={
                decision.strategy.direction === "BUY"
                  ? "text-bid-300"
                  : decision.strategy.direction === "SELL"
                    ? "text-ask-400"
                    : "text-fg-muted"
              }
            >
              {decision.strategy.direction || "—"}
            </span>
          }
        />
        <KV
          label="Base confidence"
          value={decision.strategy.base_confidence.toFixed(2)}
        />
        {decision.agents && (
          <>
            <KV
              label="Conf. before"
              value={decision.agents.confidence_before.toFixed(2)}
            />
            <KV
              label="Conf. after"
              value={
                <span
                  className={
                    decision.agents.confidence_after >=
                    decision.agents.confidence_before
                      ? "text-bid-300"
                      : "text-warn-400"
                  }
                >
                  {decision.agents.confidence_after.toFixed(2)}
                </span>
              }
            />
          </>
        )}
        <KV label="Input price" value={`$${decision.input_price.toFixed(2)}`} />
      </Section>

      {decision.regime && (
        <Section label="Regime">
          <KV
            label="Resolved"
            value={
              <span className="font-mono">
                {decision.regime.resolved ?? "—"}
              </span>
            }
          />
          <KV
            label="Rule-based"
            value={
              <span className="font-mono">
                {decision.regime.rule_based ?? "—"}
              </span>
            }
          />
          <KV
            label="HMM"
            value={
              <span className="font-mono">{decision.regime.hmm ?? "—"}</span>
            }
          />
          <KV
            label="Multiplier"
            value={decision.regime.confidence_multiplier.toFixed(2)}
          />
        </Section>
      )}

      <Section label="Indicators">
        <KV
          label="RSI"
          value={decision.indicators?.rsi?.toFixed(2) ?? "—"}
        />
        <KV
          label="MACD"
          value={decision.indicators?.macd_line?.toFixed(3) ?? "—"}
        />
        <KV
          label="Signal"
          value={decision.indicators?.signal_line?.toFixed(3) ?? "—"}
        />
        <KV
          label="Histogram"
          value={decision.indicators?.histogram?.toFixed(3) ?? "—"}
        />
        <KV
          label="ATR"
          value={decision.indicators?.atr?.toFixed(2) ?? "—"}
        />
        <KV
          label="ADX"
          value={
            decision.indicators?.adx !== null
              ? decision.indicators.adx?.toFixed(2)
              : "—"
          }
        />
      </Section>

      {agentRows.length > 0 && (
        <Section label="Agent scores">
          <div className="col-span-2">
            <table className="w-full">
              <tbody>
                {agentRows.map((a) => (
                  <tr key={a.name}>
                    <td className="font-mono text-fg py-0.5">{a.name}</td>
                    <td
                      className={cn(
                        "text-right font-mono py-0.5",
                        (a.score ?? 0) > 0
                          ? "text-bid-300"
                          : (a.score ?? 0) < 0
                            ? "text-danger-500"
                            : "text-fg-muted"
                      )}
                    >
                      {a.score !== null ? a.score.toFixed(3) : "—"}
                    </td>
                    <td className="text-right font-mono text-fg-muted py-0.5 pl-3">
                      w{a.weight.toFixed(2)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Section>
      )}

      {gateEntries.length > 0 && (
        <Section label="Gates">
          <ul className="col-span-2 flex flex-col gap-0.5">
            {gateEntries.map(([name, gate]) => (
              <li
                key={name}
                className="flex items-center justify-between gap-2 py-0.5"
              >
                <span className="font-mono text-fg-secondary">{name}</span>
                <span
                  className={cn(
                    "text-[11px] num-tabular",
                    gate.passed ? "text-bid-300" : "text-danger-500"
                  )}
                >
                  {gate.passed
                    ? "pass"
                    : gate.reason
                      ? `block · ${gate.reason}`
                      : "block"}
                </span>
              </li>
            ))}
          </ul>
        </Section>
      )}

      {passedConds.length > 0 && (
        <Section label="Strategy conditions">
          <ul className="col-span-2 flex flex-col gap-0.5">
            {passedConds.map((c, i) => (
              <li
                key={i}
                className="flex items-center justify-between gap-2 py-0.5 text-[11px]"
              >
                <span className="font-mono text-fg-secondary truncate">
                  {c.indicator} {c.operator}{" "}
                  <span className="text-fg-muted">{c.threshold}</span>
                </span>
                <span className="font-mono">
                  <span className="text-fg-muted mr-1.5">
                    {c.actual_value?.toFixed?.(2) ?? "—"}
                  </span>
                  <span
                    className={
                      c.passed ? "text-bid-300" : "text-danger-500"
                    }
                  >
                    {c.passed ? "✓" : "✗"}
                  </span>
                </span>
              </li>
            ))}
          </ul>
        </Section>
      )}

      {decision.order_id && (
        <Section label="Resulting order">
          <KV
            label="Order ID"
            value={
              <span className="font-mono text-fg text-[11px]">
                {decision.order_id.slice(0, 12)}…
              </span>
            }
          />
        </Section>
      )}
    </div>
  );
}

function Section({
  label,
  children,
}: {
  label: string;
  children: React.ReactNode;
}) {
  return (
    <section className="flex flex-col gap-1.5">
      <h3 className="text-[10px] uppercase tracking-wider text-fg-muted">
        {label}
      </h3>
      <dl className="grid grid-cols-2 gap-x-3 gap-y-1 rounded-md border border-border-subtle bg-bg-canvas px-3 py-2">
        {children}
      </dl>
    </section>
  );
}

function KV({
  label,
  value,
}: {
  label: string;
  value: React.ReactNode;
}) {
  return (
    <>
      <dt className="text-fg-muted">{label}</dt>
      <dd className="text-right text-fg num-tabular">{value}</dd>
    </>
  );
}

function ErrorBlock({ message }: { message: string }) {
  return (
    <div className="m-4 rounded-md border border-danger-700/40 bg-danger-700/10 p-3 text-[12px] text-danger-500">
      <p className="font-medium">Couldn&rsquo;t load decisions</p>
      <p className="text-fg-muted mt-0.5">{message}</p>
    </div>
  );
}

function EmptyBlock() {
  return (
    <div className="m-4 rounded-md border border-border-subtle bg-bg-panel p-4 text-[12px] text-fg-muted text-center">
      No decisions yet for this filter. Agents may still be initializing.
    </div>
  );
}

function formatTime(iso: string): string {
  const t = Date.parse(iso);
  if (!Number.isFinite(t)) return iso;
  return new Date(t).toLocaleTimeString([], {
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  });
}
