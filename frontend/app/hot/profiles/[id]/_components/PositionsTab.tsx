"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { ChevronRight, RefreshCw } from "lucide-react";
import { api } from "@/lib/api/client";
import { Pill } from "@/components/data-display";
import { cn } from "@/lib/utils";
import { DetailDrawer } from "./DetailDrawer";

interface Position {
  position_id: string;
  profile_id: string;
  symbol: string;
  side: "BUY" | "SELL";
  entry_price: string;
  quantity: string;
  opened_at: string;
  status: string;
  decision_event_id?: string | null;
  unrealized_net_pnl?: number | null;
  unrealized_pct_return?: number | null;
  notional?: string | null;
  profile_notional?: string | null;
  allocation_used_pct?: number | null;
  mark_price?: string | null;
  stop_loss_price?: string | null;
  stop_loss_pct?: string | null;
  take_profit_price?: string | null;
  take_profit_pct?: string | null;
}

interface ChainData {
  decision: Record<string, unknown> | null;
  order: Record<string, unknown> | null;
  position: Record<string, unknown> | null;
  closed_trade: Record<string, unknown> | null;
}

const POLL_INTERVAL_MS = 5_000;

interface PositionsTabProps {
  profileId: string;
  selectedId: string | null;
  onSelect: (id: string | null) => void;
}

export function PositionsTab({
  profileId,
  selectedId,
  onSelect,
}: PositionsTabProps) {
  const [rows, setRows] = useState<Position[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      const data = await api.positions.list({ status: "open", profileId });
      setRows(data as Position[]);
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load positions");
    } finally {
      setLoading(false);
    }
  }, [profileId]);

  useEffect(() => {
    setLoading(true);
    load();
    const id = window.setInterval(load, POLL_INTERVAL_MS);
    return () => window.clearInterval(id);
  }, [load]);

  const selected = useMemo(
    () => rows.find((r) => r.position_id === selectedId) ?? null,
    [rows, selectedId]
  );

  return (
    <div className="flex flex-col h-full min-h-0">
      <div className="shrink-0 flex items-center justify-between gap-2 px-4 py-2.5 border-b border-border-subtle">
        <div className="flex items-baseline gap-3 text-[11px] num-tabular">
          <span className="text-fg-muted">
            {rows.length} open position{rows.length === 1 ? "" : "s"}
          </span>
          <span className="text-fg-muted">·</span>
          <span className="text-fg-muted">cross-symbol</span>
        </div>
        <button
          type="button"
          onClick={load}
          aria-label="Refresh"
          className="h-7 w-7 rounded-md flex items-center justify-center text-fg-muted hover:text-fg hover:bg-bg-raised"
        >
          <RefreshCw
            className={cn("w-3 h-3", loading && "animate-spin")}
            strokeWidth={1.5}
            aria-hidden
          />
        </button>
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
                <Th align="left">Symbol</Th>
                <Th align="left">Side</Th>
                <Th align="right">Qty</Th>
                <Th align="right">Entry</Th>
                <Th align="right">Mark</Th>
                <Th align="right">Unreal.</Th>
                <Th align="right">%</Th>
                <Th align="right">Age</Th>
                <Th align="right" />
              </tr>
            </thead>
            <tbody>
              {rows.map((p) => (
                <PositionRow
                  key={p.position_id}
                  position={p}
                  selected={selectedId === p.position_id}
                  onSelect={() =>
                    onSelect(
                      selectedId === p.position_id ? null : p.position_id
                    )
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
        kind="position"
        title={
          selected
            ? `${selected.symbol} · ${selected.side === "BUY" ? "long" : "short"}`
            : "Position"
        }
        subtitle={
          selected ? (
            <span className="font-mono">
              opened {formatRelative(selected.opened_at)}
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
        {selected && <PositionDetail position={selected} />}
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

function PositionRow({
  position,
  selected,
  onSelect,
}: {
  position: Position;
  selected: boolean;
  onSelect: () => void;
}) {
  const isLong = position.side === "BUY";
  const net = position.unrealized_net_pnl;
  const pct = position.unrealized_pct_return;
  const pnlTone =
    net === null || net === undefined
      ? "neutral"
      : net > 0
        ? "ok"
        : net < 0
          ? "danger"
          : "neutral";

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
            isLong ? "bg-bid-500/60" : "bg-ask-500/60",
            selected && "bg-accent-500"
          )}
        />
        <span className="font-mono text-fg">{position.symbol}</span>
      </Td>
      <Td>
        <Pill intent={isLong ? "bid" : "ask"}>
          {isLong ? "long" : "short"}
        </Pill>
      </Td>
      <Td align="right">
        <span className="font-mono text-fg-secondary">
          {fmt(position.quantity, 4)}
        </span>
      </Td>
      <Td align="right">
        <span className="font-mono text-fg-secondary">
          ${fmt(position.entry_price)}
        </span>
      </Td>
      <Td align="right">
        <span className="font-mono text-fg-secondary">
          {position.mark_price ? `$${fmt(position.mark_price)}` : "—"}
        </span>
      </Td>
      <Td align="right">
        <span
          className={cn(
            "font-mono",
            pnlTone === "ok" && "text-bid-300",
            pnlTone === "danger" && "text-danger-500",
            pnlTone === "neutral" && "text-fg-muted"
          )}
        >
          {fmtUsdSigned(net)}
        </span>
      </Td>
      <Td align="right">
        <span
          className={cn(
            "font-mono",
            pnlTone === "ok" && "text-bid-300",
            pnlTone === "danger" && "text-danger-500",
            pnlTone === "neutral" && "text-fg-muted"
          )}
        >
          {fmtPct(pct)}
        </span>
      </Td>
      <Td align="right">
        <span className="font-mono text-fg-muted">
          {ageLabel(position.opened_at)}
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

function PositionDetail({ position }: { position: Position }) {
  const [chain, setChain] = useState<ChainData | null>(null);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState<string | null>(null);
  const [closing, setClosing] = useState(false);
  const [closeError, setCloseError] = useState<string | null>(null);

  useEffect(() => {
    if (!position.decision_event_id) {
      setLoading(false);
      return;
    }
    let cancelled = false;
    setLoading(true);
    api.audit
      .chain(position.decision_event_id)
      .then((c) => {
        if (!cancelled) setChain(c);
      })
      .catch((e: unknown) => {
        if (!cancelled)
          setErr(e instanceof Error ? e.message : "lookup failed");
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [position.decision_event_id]);

  const decision = (chain?.decision ?? {}) as Record<string, unknown>;
  const regime = decision.regime as
    | { state?: string; resolved?: string }
    | string
    | undefined;
  const regimeLabel =
    typeof regime === "string" ? regime : regime?.resolved ?? regime?.state ?? "—";
  const agents = decision.agents as
    | Record<string, { score?: number; weight?: number }>
    | undefined;
  const gates = decision.gates as
    | Record<string, { passed?: boolean; reason?: string }>
    | undefined;
  const rationale = decision.rationale as string | undefined;
  const finalScore = decision.final_score as number | undefined;

  const handleClose = async () => {
    if (!window.confirm("Close this position at market?")) return;
    setClosing(true);
    setCloseError(null);
    try {
      await api.positions.close(position.position_id);
      setClosing(false);
    } catch (e) {
      setCloseError(e instanceof Error ? e.message : "Close failed");
      setClosing(false);
    }
  };

  return (
    <div className="px-4 py-3 flex flex-col gap-4 text-[12px]">
      <Section label="Live state">
        <KV label="Symbol" value={<span className="font-mono">{position.symbol}</span>} />
        <KV
          label="Side / Qty"
          value={
            <span
              className={`font-mono ${position.side === "BUY" ? "text-bid-300" : "text-ask-400"}`}
            >
              {position.side === "BUY" ? "long" : "short"}{" "}
              {fmt(position.quantity, 4)}
            </span>
          }
        />
        <KV label="Entry" value={`$${fmt(position.entry_price)}`} />
        <KV
          label="Mark"
          value={position.mark_price ? `$${fmt(position.mark_price)}` : "—"}
        />
        <KV
          label="Unrealized"
          value={
            <span
              className={
                position.unrealized_net_pnl !== undefined &&
                position.unrealized_net_pnl !== null &&
                position.unrealized_net_pnl >= 0
                  ? "text-bid-300"
                  : "text-danger-500"
              }
            >
              {fmtUsdSigned(position.unrealized_net_pnl)}{" "}
              <span className="text-fg-muted">
                ({fmtPct(position.unrealized_pct_return)})
              </span>
            </span>
          }
        />
        <KV
          label="Notional"
          value={position.notional ? `$${fmt(position.notional, 0)}` : "—"}
        />
        {position.stop_loss_price && (
          <KV
            label="Stop"
            value={
              <span className="text-danger-500">
                ${fmt(position.stop_loss_price)}
              </span>
            }
          />
        )}
        {position.take_profit_price && (
          <KV
            label="Target"
            value={
              <span className="text-bid-300">
                ${fmt(position.take_profit_price)}
              </span>
            }
          />
        )}
        <KV label="Age" value={ageLabel(position.opened_at)} />
      </Section>

      {!position.decision_event_id ? (
        <Section label="Decision lineage">
          <p className="col-span-2 text-fg-muted">
            No decision event linked (manual or legacy fill).
          </p>
        </Section>
      ) : loading ? (
        <Section label="Decision lineage">
          <p className="col-span-2 text-fg-muted">
            Loading decision lineage…
          </p>
        </Section>
      ) : err ? (
        <Section label="Decision lineage">
          <p className="col-span-2 text-warn-400">Could not load: {err}</p>
        </Section>
      ) : (
        <>
          <Section label="Why we entered">
            <KV
              label="Regime"
              value={<span className="font-mono">{regimeLabel}</span>}
            />
            {typeof finalScore === "number" && (
              <KV
                label="Final score"
                value={finalScore.toFixed(3)}
              />
            )}
            {rationale && (
              <p className="col-span-2 text-fg-muted italic text-[11px] mt-1.5">
                &ldquo;{rationale}&rdquo;
              </p>
            )}
          </Section>

          {agents && Object.keys(agents).length > 0 && (
            <Section label="Agent scores">
              <ul className="col-span-2 flex flex-col gap-0.5">
                {Object.entries(agents)
                  .map(([name, v]) => ({
                    name,
                    score: typeof v?.score === "number" ? v.score : null,
                    weight: typeof v?.weight === "number" ? v.weight : null,
                  }))
                  .sort((a, b) => Math.abs(b.score ?? 0) - Math.abs(a.score ?? 0))
                  .slice(0, 6)
                  .map((a) => (
                    <li
                      key={a.name}
                      className="flex items-center justify-between gap-2 py-0.5"
                    >
                      <span className="font-mono text-fg">{a.name}</span>
                      <span className="flex items-center gap-2 num-tabular">
                        <span
                          className={cn(
                            "font-mono",
                            (a.score ?? 0) > 0
                              ? "text-bid-300"
                              : (a.score ?? 0) < 0
                                ? "text-danger-500"
                                : "text-fg-muted"
                          )}
                        >
                          {a.score !== null ? a.score.toFixed(3) : "—"}
                        </span>
                        <span className="text-fg-muted font-mono text-[11px]">
                          {a.weight !== null ? `w${a.weight.toFixed(2)}` : ""}
                        </span>
                      </span>
                    </li>
                  ))}
              </ul>
            </Section>
          )}

          {gates && Object.keys(gates).length > 0 && (
            <Section label="Gates">
              <ul className="col-span-2 flex flex-col gap-0.5">
                {Object.entries(gates).map(([name, g]) => (
                  <li
                    key={name}
                    className="flex items-center justify-between gap-2 py-0.5"
                  >
                    <span className="font-mono text-fg-secondary">{name}</span>
                    <span
                      className={cn(
                        "text-[11px] num-tabular",
                        g?.passed ? "text-bid-300" : "text-danger-500"
                      )}
                    >
                      {g?.passed
                        ? "pass"
                        : g?.reason
                          ? `block · ${g.reason}`
                          : "block"}
                    </span>
                  </li>
                ))}
              </ul>
            </Section>
          )}

          {position.decision_event_id && (
            <Section label="Refs">
              <KV
                label="Decision"
                value={
                  <span className="font-mono text-[11px]">
                    {position.decision_event_id.slice(0, 12)}…
                  </span>
                }
              />
              <KV
                label="Position"
                value={
                  <span className="font-mono text-[11px]">
                    {position.position_id.slice(0, 12)}…
                  </span>
                }
              />
            </Section>
          )}
        </>
      )}

      <div className="border-t border-border-subtle pt-3 flex flex-col gap-2">
        <button
          type="button"
          onClick={handleClose}
          disabled={closing}
          className={cn(
            "h-8 rounded-md text-[12px] num-tabular border",
            "border-danger-700/50 bg-danger-700/10 text-danger-500",
            "hover:bg-danger-700/20 disabled:opacity-50 disabled:cursor-not-allowed",
            "focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent-500"
          )}
        >
          {closing ? "Closing…" : "Close at market"}
        </button>
        {closeError && (
          <p className="text-[11px] text-danger-500">{closeError}</p>
        )}
      </div>
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
      <p className="font-medium">Couldn&rsquo;t load positions</p>
      <p className="text-fg-muted mt-0.5">{message}</p>
    </div>
  );
}

function EmptyBlock() {
  return (
    <div className="m-4 rounded-md border border-border-subtle bg-bg-panel p-4 text-[12px] text-fg-muted text-center">
      This profile has no open positions. The Decisions tab shows what the
      engine is evaluating.
    </div>
  );
}

function fmt(
  s: string | number | null | undefined,
  digits = 2
): string {
  if (s === null || s === undefined) return "—";
  const n = typeof s === "number" ? s : parseFloat(s);
  return Number.isFinite(n) ? n.toFixed(digits) : "—";
}

function fmtUsdSigned(n: number | null | undefined): string {
  if (n === null || n === undefined || !Number.isFinite(n)) return "—";
  const sign = n > 0 ? "+" : "";
  return `${sign}$${n.toFixed(2)}`;
}

function fmtPct(p: number | null | undefined): string {
  if (typeof p !== "number" || !Number.isFinite(p)) return "—";
  return `${p > 0 ? "+" : ""}${(p * 100).toFixed(2)}%`;
}

function ageLabel(iso: string): string {
  const min = Math.floor((Date.now() - new Date(iso).getTime()) / 60_000);
  if (min < 60) return `${min}m`;
  const h = min / 60;
  if (h < 24) return `${h.toFixed(1)}h`;
  return `${(h / 24).toFixed(1)}d`;
}

function formatRelative(iso: string): string {
  const min = Math.floor((Date.now() - new Date(iso).getTime()) / 60_000);
  if (min < 60) return `${min}m ago`;
  const h = min / 60;
  if (h < 24) return `${h.toFixed(1)}h ago`;
  return `${(h / 24).toFixed(1)}d ago`;
}
