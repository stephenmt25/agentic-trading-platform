"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import {
  ArrowLeft,
  Loader2,
  AlertTriangle,
  Plus,
  Info,
  GitCompare,
} from "lucide-react";
import { Button, Tag } from "@/components/primitives";
import {
  Chart,
  Pill,
  Table,
  type ChartSeries,
  type ChartStrokeStyle,
  type TableColumn,
} from "@/components/data-display";
import { PnLBadge } from "@/components/trading";
import { api, type ProfileResponse } from "@/lib/api/client";

interface SimulatedTrade {
  entry_time: string;
  exit_time: string | null;
  direction: "BUY" | "SELL";
  entry_price: number;
  exit_price: number | null;
  pnl_pct: number;
}

interface BacktestPayload {
  job_id: string;
  status: string;
  symbol?: string;
  profile_id?: string | null;
  total_trades?: number;
  win_rate?: number;
  avg_return?: number;
  max_drawdown?: number;
  sharpe?: number;
  profit_factor?: number;
  equity_curve?: number[];
  trades?: SimulatedTrade[];
  start_date?: string | null;
  end_date?: string | null;
  timeframe?: string | null;
  error?: string;
}

interface RunRow {
  jobId: string;
  payload: BacktestPayload | null;
  profileName: string;
  /** "loading" | "ready" | "error" — derived from fetch state. */
  state: "loading" | "ready" | "error" | "incomplete";
  error?: string;
  roi: number | null;
}

const SERIES_PALETTE: Array<{
  tone: "accent" | "neutral";
  stroke: ChartStrokeStyle;
}> = [
  { tone: "accent", stroke: "solid" },
  { tone: "neutral", stroke: "solid" },
  { tone: "accent", stroke: "dashed" },
  { tone: "neutral", stroke: "dashed" },
  { tone: "accent", stroke: "dotted" },
  { tone: "neutral", stroke: "dotted" },
];

function toNumber(v: unknown, fallback = 0): number {
  if (typeof v === "number") return Number.isFinite(v) ? v : fallback;
  if (typeof v === "string") {
    const n = parseFloat(v);
    return Number.isFinite(n) ? n : fallback;
  }
  return fallback;
}

function shortJob(jobId: string): string {
  return jobId.slice(0, 7);
}

function parseRuns(param: string | null): string[] {
  if (!param) return [];
  return Array.from(
    new Set(
      param
        .split(",")
        .map((s) => decodeURIComponent(s.trim()))
        .filter(Boolean)
    )
  );
}

function computeRoi(equity: number[] | undefined): number | null {
  if (!equity || equity.length < 2) return null;
  const start = equity[0];
  const end = equity[equity.length - 1];
  if (!Number.isFinite(start) || start === 0) return null;
  return (end - start) / start;
}

/**
 * /backtests/compare?runs=a,b,c — side-by-side run comparison. Per surface
 * spec docs/design/05-surface-specs/04-backtesting-analytics.md §3.
 *
 * Backend gaps surfaced inline as Pending tags (matches 6.1 / 6.2a / 6.2b
 * pattern):
 *   - shared-trade fingerprinting is derived client-side as
 *     `entry_time + direction` (within a symbol/profile pair) since the
 *     backend doesn't emit a canonical "shared trade key"
 *   - Sortino, avg-R, regime breakdown, per-agent attribution remain
 *     unwired (same as 6.2b)
 */
export default function BacktestCompareePage() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const runsParam = searchParams.get("runs");
  const runIds = useMemo(() => parseRuns(runsParam), [runsParam]);

  const [rows, setRows] = useState<RunRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    if (runIds.length === 0) {
      setRows([]);
      setLoading(false);
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const [profileList, ...results] = await Promise.all([
        api.profiles.list().catch(() => [] as ProfileResponse[]),
        ...runIds.map((id) =>
          api.backtest
            .result(id)
            .then(
              (res) =>
                ({
                  ok: true,
                  payload: res as unknown as BacktestPayload,
                  jobId: id,
                }) as const
            )
            .catch((e: unknown) => ({
              ok: false,
              error: e instanceof Error ? e.message : "load failed",
              jobId: id,
            } as const))
        ),
      ]);
      const next: RunRow[] = results.map((r) => {
        if (!r.ok) {
          return {
            jobId: r.jobId,
            payload: null,
            profileName: shortJob(r.jobId),
            state: "error",
            error: r.error,
            roi: null,
          };
        }
        const payload = r.payload;
        const pid = payload.profile_id;
        const profile = pid ? profileList.find((p) => p.profile_id === pid) : undefined;
        const isCompleted = payload.status === "completed";
        return {
          jobId: r.jobId,
          payload,
          profileName: profile?.name ?? (pid ? shortJob(pid) : shortJob(r.jobId)),
          state: isCompleted ? "ready" : "incomplete",
          roi: computeRoi(payload.equity_curve),
        };
      });
      setRows(next);
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : "Failed to load comparison";
      setError(msg);
    } finally {
      setLoading(false);
    }
  }, [runIds]);

  useEffect(() => {
    load();
  }, [load]);

  const removeRun = useCallback(
    (jobId: string) => {
      const remaining = runIds.filter((id) => id !== jobId);
      if (remaining.length === 0) {
        router.push("/backtests");
        return;
      }
      const ids = remaining.map((id) => encodeURIComponent(id)).join(",");
      router.push(`/backtests/compare?runs=${ids}`);
    },
    [runIds, router]
  );

  const validRuns = runIds.length;
  const isUnderfilled = validRuns < 2;

  return (
    <div data-mode="cool" className="flex flex-col h-full bg-bg-canvas text-fg">
      <header className="flex items-start justify-between gap-4 border-b border-border-subtle px-6 py-4">
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2 text-[12px] text-fg-muted">
            <Link
              href="/backtests"
              className="inline-flex items-center gap-1 hover:text-fg transition-colors focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent-500 rounded-sm"
            >
              <ArrowLeft className="w-3 h-3" strokeWidth={1.5} />
              Backtests
            </Link>
            <span aria-hidden>/</span>
            <span className="font-mono text-fg-secondary inline-flex items-center gap-1.5">
              <GitCompare className="w-3 h-3" strokeWidth={1.5} />
              compare
            </span>
          </div>
          <h1 className="text-[18px] font-semibold tracking-tight text-fg mt-1.5 truncate">
            Compare runs
            <span className="text-fg-muted font-normal ml-2 text-[14px] num-tabular">
              ({validRuns})
            </span>
          </h1>
          <div className="mt-2 flex items-center flex-wrap gap-1.5">
            {rows.map((r, i) => {
              const intent = i === 0 ? "accent" : "neutral";
              return (
                <Pill
                  key={r.jobId}
                  as="removable"
                  intent={intent}
                  onRemove={() => removeRun(r.jobId)}
                >
                  <span className="font-mono">#{shortJob(r.jobId)}</span>
                  <span className="ml-1 text-fg-muted">{r.profileName}</span>
                </Pill>
              );
            })}
            <Button
              intent="secondary"
              size="sm"
              leftIcon={<Plus className="w-3.5 h-3.5" />}
              onClick={() => router.push("/backtests")}
              title="Pick another run from the list"
            >
              Add run
            </Button>
          </div>
        </div>
      </header>

      <div className="flex-1 min-h-0 overflow-auto">
        {loading && (
          <div className="mx-6 mt-6 rounded-md border border-border-subtle bg-bg-panel p-6 flex items-center gap-3">
            <Loader2 className="w-4 h-4 text-fg-muted animate-spin" aria-hidden />
            <span className="text-[13px] text-fg-muted">
              Loading {runIds.length} run{runIds.length === 1 ? "" : "s"}…
            </span>
          </div>
        )}

        {!loading && error && (
          <div
            role="alert"
            className="mx-6 mt-6 rounded-md border border-danger-700/40 bg-danger-700/10 p-4 flex items-start gap-3 text-[13px] text-danger-500"
          >
            <AlertTriangle className="w-4 h-4 shrink-0 mt-0.5" strokeWidth={1.5} aria-hidden />
            <div className="flex-1">
              <p className="font-medium">Could not load comparison.</p>
              <p className="text-fg-muted mt-0.5">{error}</p>
            </div>
            <Button intent="secondary" size="sm" onClick={load}>
              Retry
            </Button>
          </div>
        )}

        {!loading && !error && isUnderfilled && (
          <UnderfilledEmpty count={validRuns} />
        )}

        {!loading && !error && !isUnderfilled && rows.length > 0 && (
          <div className="px-6 py-6 flex flex-col gap-6">
            <ComparisonHeadline rows={rows} />
            <EquityComparisonSection rows={rows} />
            <SharedTradesSection rows={rows} />
          </div>
        )}
      </div>
    </div>
  );
}

/* -------------------------------------------------------------------------- */

function UnderfilledEmpty({ count }: { count: number }) {
  return (
    <div className="mx-auto mt-12 max-w-xl rounded-lg border border-border-subtle bg-bg-panel p-10 text-center">
      <h2 className="text-[16px] font-semibold text-fg">
        Select 2 or more runs to compare.
      </h2>
      <p className="text-[13px] text-fg-secondary mt-2">
        {count === 0
          ? "No runs in the URL — pick at least two from the list."
          : "One run is in the URL — pick another to start a comparison."}
      </p>
      <div className="mt-5 flex items-center justify-center gap-2">
        <Link
          href="/backtests"
          className="inline-flex items-center gap-1.5 text-[13px] text-fg-secondary hover:text-fg transition-colors px-3 py-1.5 rounded-sm border border-border-subtle bg-bg-canvas"
        >
          <ArrowLeft className="w-3.5 h-3.5" strokeWidth={1.5} />
          Back to list
        </Link>
      </div>
    </div>
  );
}

/* -------------------------------------------------------------------------- */

function ComparisonHeadline({ rows }: { rows: RunRow[] }) {
  const baseline = rows[0];
  const baseRoi = baseline.roi;
  const basePayload = baseline.payload;
  return (
    <section className="rounded-md border border-border-subtle bg-bg-panel">
      <header className="flex items-center justify-between px-4 py-2.5 border-b border-border-subtle">
        <h2 className="text-[11px] font-semibold uppercase tracking-wider text-fg-muted">
          Headline · vs <span className="text-fg-secondary">#{shortJob(baseline.jobId)}</span>
        </h2>
        <Tag intent="warn">Sortino &amp; avg R Pending</Tag>
      </header>
      <div className="overflow-auto">
        <table className="w-full text-[13px]">
          <thead className="text-[11px] uppercase tracking-wider text-fg-muted bg-bg-canvas">
            <tr>
              <th
                scope="col"
                className="text-left font-medium px-4 py-2 sticky left-0 bg-bg-canvas border-r border-border-subtle"
              >
                Run
              </th>
              <th scope="col" className="text-right font-medium px-3 py-2">ROI</th>
              <th scope="col" className="text-right font-medium px-3 py-2">Sharpe</th>
              <th scope="col" className="text-right font-medium px-3 py-2">Max DD</th>
              <th scope="col" className="text-right font-medium px-3 py-2">Trades</th>
              <th scope="col" className="text-right font-medium px-3 py-2">Win-rate</th>
              <th scope="col" className="text-right font-medium px-3 py-2">Profit factor</th>
              <th scope="col" className="text-right font-medium px-3 py-2">avg return</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((r, i) => (
              <ComparisonRow
                key={r.jobId}
                row={r}
                baseRoi={i === 0 ? null : baseRoi}
                basePayload={i === 0 ? null : basePayload}
                isBaseline={i === 0}
              />
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}

function ComparisonRow({
  row,
  baseRoi,
  basePayload,
  isBaseline,
}: {
  row: RunRow;
  baseRoi: number | null;
  basePayload: BacktestPayload | null;
  isBaseline: boolean;
}) {
  const p = row.payload;
  const isReady = row.state === "ready" && p;
  const sharpe = isReady ? toNumber(p.sharpe) : NaN;
  const maxDD = isReady ? toNumber(p.max_drawdown) : NaN;
  const profitFactor = isReady ? toNumber(p.profit_factor) : NaN;
  const avgReturn = isReady ? toNumber(p.avg_return) : NaN;
  const winRate = isReady ? toNumber(p.win_rate) : NaN;
  const trades = isReady ? p.total_trades ?? p.trades?.length ?? 0 : 0;

  const baseSharpe = basePayload ? toNumber(basePayload.sharpe) : NaN;
  const baseMaxDD = basePayload ? toNumber(basePayload.max_drawdown) : NaN;
  const basePF = basePayload ? toNumber(basePayload.profit_factor) : NaN;
  const baseAvg = basePayload ? toNumber(basePayload.avg_return) : NaN;
  const baseWin = basePayload ? toNumber(basePayload.win_rate) : NaN;
  const baseTrades = basePayload ? basePayload.total_trades ?? basePayload.trades?.length ?? 0 : 0;

  return (
    <tr className="border-t border-border-subtle align-top">
      <th
        scope="row"
        className="text-left px-4 py-3 sticky left-0 bg-bg-panel border-r border-border-subtle"
      >
        <div className="flex flex-col gap-0.5">
          <span className="inline-flex items-center gap-1.5 text-[12px] text-fg">
            <Link
              href={`/backtests/${encodeURIComponent(row.jobId)}`}
              className="font-mono hover:text-accent-300 transition-colors focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent-500 rounded-sm"
            >
              #{shortJob(row.jobId)}
            </Link>
            {isBaseline && <Tag intent="accent">baseline</Tag>}
            {row.state === "incomplete" && p && (
              <Tag intent="warn">{p.status}</Tag>
            )}
            {row.state === "error" && <Tag intent="danger">load failed</Tag>}
          </span>
          <span className="text-[11px] text-fg-muted truncate max-w-[18rem]">
            {row.profileName} {p?.symbol ? `· ${p.symbol}` : ""}
          </span>
        </div>
      </th>
      <td className="text-right px-3 py-3 num-tabular">
        {row.roi != null ? (
          <CompareCell
            value={<PnLBadge value={row.roi * 100} mode="pct" hideArrow />}
            delta={
              isBaseline || baseRoi == null || row.roi == null
                ? null
                : row.roi - baseRoi
            }
            mode="pct-points"
          />
        ) : (
          <span className="text-fg-muted">—</span>
        )}
      </td>
      <td className="text-right px-3 py-3 num-tabular">
        <CompareCell
          value={
            Number.isFinite(sharpe) ? (
              <span className="text-fg num-tabular">{sharpe.toFixed(2)}</span>
            ) : (
              <span className="text-fg-muted">—</span>
            )
          }
          delta={
            isBaseline || !Number.isFinite(sharpe) || !Number.isFinite(baseSharpe)
              ? null
              : sharpe - baseSharpe
          }
          mode="raw"
          digits={2}
        />
      </td>
      <td className="text-right px-3 py-3 num-tabular">
        <CompareCell
          value={
            Number.isFinite(maxDD) ? (
              <span className="text-ask-400 num-tabular">
                {(maxDD * 100).toFixed(1)}%
              </span>
            ) : (
              <span className="text-fg-muted">—</span>
            )
          }
          delta={
            isBaseline || !Number.isFinite(maxDD) || !Number.isFinite(baseMaxDD)
              ? null
              : maxDD - baseMaxDD
          }
          mode="pct-points"
          /* lower drawdown is better → invert delta tone */
          invertTone
        />
      </td>
      <td className="text-right px-3 py-3 num-tabular">
        <CompareCell
          value={<span className="num-tabular text-fg">{trades.toLocaleString()}</span>}
          delta={isBaseline ? null : trades - baseTrades}
          mode="int"
          /* trade-count delta is informational, not better/worse */
          neutral
        />
      </td>
      <td className="text-right px-3 py-3 num-tabular">
        <CompareCell
          value={
            Number.isFinite(winRate) ? (
              <span className="num-tabular text-fg">{(winRate * 100).toFixed(0)}%</span>
            ) : (
              <span className="text-fg-muted">—</span>
            )
          }
          delta={
            isBaseline || !Number.isFinite(winRate) || !Number.isFinite(baseWin)
              ? null
              : winRate - baseWin
          }
          mode="pct-points"
        />
      </td>
      <td className="text-right px-3 py-3 num-tabular">
        <CompareCell
          value={
            Number.isFinite(profitFactor) ? (
              <span className="num-tabular text-fg">{profitFactor.toFixed(2)}</span>
            ) : (
              <span className="text-fg-muted">—</span>
            )
          }
          delta={
            isBaseline || !Number.isFinite(profitFactor) || !Number.isFinite(basePF)
              ? null
              : profitFactor - basePF
          }
          mode="raw"
          digits={2}
        />
      </td>
      <td className="text-right px-3 py-3 num-tabular">
        <CompareCell
          value={
            Number.isFinite(avgReturn) ? (
              <span className="num-tabular text-fg">{(avgReturn * 100).toFixed(2)}%</span>
            ) : (
              <span className="text-fg-muted">—</span>
            )
          }
          delta={
            isBaseline || !Number.isFinite(avgReturn) || !Number.isFinite(baseAvg)
              ? null
              : avgReturn - baseAvg
          }
          mode="pct-points"
        />
      </td>
    </tr>
  );
}

function CompareCell({
  value,
  delta,
  mode,
  digits = 2,
  invertTone = false,
  neutral = false,
}: {
  value: React.ReactNode;
  delta: number | null;
  mode: "pct-points" | "raw" | "int";
  digits?: number;
  invertTone?: boolean;
  neutral?: boolean;
}) {
  let label: string | null = null;
  let positive: boolean | null = null;

  if (delta != null && Number.isFinite(delta)) {
    if (mode === "pct-points") {
      const pp = delta * 100;
      const sign = pp > 0 ? "+" : pp < 0 ? "−" : "";
      label = `${sign}${Math.abs(pp).toFixed(2)}pp`;
      positive = pp > 0 ? true : pp < 0 ? false : null;
    } else if (mode === "raw") {
      const sign = delta > 0 ? "+" : delta < 0 ? "−" : "";
      label = `${sign}${Math.abs(delta).toFixed(digits)}`;
      positive = delta > 0 ? true : delta < 0 ? false : null;
    } else {
      // int
      const sign = delta > 0 ? "+" : delta < 0 ? "−" : "";
      label = `${sign}${Math.abs(Math.round(delta)).toLocaleString()}`;
      positive = delta > 0 ? true : delta < 0 ? false : null;
    }
  }

  const toneClass = neutral
    ? "text-fg-muted"
    : positive == null
      ? "text-fg-muted"
      : (invertTone ? !positive : positive)
        ? "text-bid-400"
        : "text-ask-400";

  return (
    <span className="inline-flex flex-col items-end gap-0.5 leading-tight">
      <span>{value}</span>
      {label && <span className={`text-[10px] num-tabular ${toneClass}`}>{label}</span>}
    </span>
  );
}

/* -------------------------------------------------------------------------- */

function EquityComparisonSection({ rows }: { rows: RunRow[] }) {
  const series: ChartSeries[] = useMemo(() => {
    return rows
      .filter((r) => r.state === "ready" && (r.payload?.equity_curve?.length ?? 0) >= 2)
      .map((r, i) => {
        const eq = r.payload!.equity_curve!;
        const palette = SERIES_PALETTE[i % SERIES_PALETTE.length];
        // Normalize to [0, 1] x-position so different-length curves overlay
        // by relative time-in-run rather than absolute index. Equity_curve
        // is timestamp-less today (handoff §"Things to be aware of"), so
        // comparing absolute indices would punish runs with finer
        // timeframes. Relative position is the closest honest mapping.
        const denom = Math.max(1, eq.length - 1);
        return {
          id: r.jobId,
          label: `#${shortJob(r.jobId)} · ${r.profileName}`,
          shape: "line" as const,
          tone: palette.tone,
          stroke: palette.stroke,
          data: eq.map((y, idx) => ({ x: idx / denom, y })),
        };
      });
  }, [rows]);

  const renderable = series.length;
  const dropped = rows.length - renderable;

  return (
    <section className="rounded-md border border-border-subtle bg-bg-panel">
      <header className="flex items-center justify-between gap-3 px-4 py-2.5 border-b border-border-subtle">
        <h2 className="text-[11px] font-semibold uppercase tracking-wider text-fg-muted">
          Equity curves
          <span className="ml-2 text-fg-secondary normal-case tracking-normal num-tabular">
            ({renderable})
          </span>
        </h2>
        <Tag intent="warn">Per-tick timestamps pending</Tag>
      </header>
      <div className="px-4 py-5 flex flex-col gap-3">
        {renderable === 0 ? (
          <p className="text-[12px] text-fg-muted">
            No completed runs with equity curves.
          </p>
        ) : (
          <>
            <Chart
              series={series}
              xType="numeric"
              yScale="linear"
              density="comfortable"
              axes="both"
              gridLines="horizontal"
              legend="always"
              tableFallback
              downsample={1500}
              ariaLabel={`Equity curves for ${renderable} runs, normalized to relative position from start to end.`}
              formatX={(v) => {
                const t = typeof v === "number" ? v : Number(v);
                if (!Number.isFinite(t)) return "";
                return `${(t * 100).toFixed(0)}%`;
              }}
            />
            {dropped > 0 && (
              <p className="text-[11px] text-fg-muted leading-relaxed flex items-start gap-2 border-t border-border-subtle pt-3">
                <Info className="w-3.5 h-3.5 shrink-0 mt-0.5 text-warn-400" strokeWidth={1.5} aria-hidden />
                <span>
                  {dropped} run{dropped === 1 ? "" : "s"} omitted from the
                  overlay (incomplete, failed to load, or no equity samples).
                </span>
              </p>
            )}
            <p className="text-[11px] text-fg-muted leading-relaxed flex items-start gap-2 border-t border-border-subtle pt-3">
              <Info className="w-3.5 h-3.5 shrink-0 mt-0.5 text-warn-400" strokeWidth={1.5} aria-hidden />
              <span>
                Equity curves overlay by <em>relative</em> position in their
                respective ranges (0% = start, 100% = end). Per-tick
                timestamps unlock absolute time-aligned overlay when the
                backend emits paired (t, equity) tuples.
              </span>
            </p>
          </>
        )}
      </div>
    </section>
  );
}

/* -------------------------------------------------------------------------- */

interface SharedTradeBucket {
  /** entry_time + direction — coarse client-side fingerprint. */
  key: string;
  entry_time: string;
  direction: "BUY" | "SELL";
  /** Map from jobId → trade returns (pnl_pct as fraction). */
  perRun: Map<string, number | null>;
}

function fingerprintTrade(t: SimulatedTrade): string {
  // Entry timestamp + direction. Entry-price sometimes drifts by epsilon
  // between runs that share data but differ in slippage model, so the
  // fingerprint stays coarse on purpose.
  return `${t.entry_time}|${t.direction}`;
}

function SharedTradesSection({ rows }: { rows: RunRow[] }) {
  const ready = rows.filter((r) => r.state === "ready" && r.payload);

  const buckets = useMemo<SharedTradeBucket[]>(() => {
    if (ready.length < 2) return [];
    const map = new Map<string, SharedTradeBucket>();
    for (const r of ready) {
      const trades = r.payload!.trades ?? [];
      for (const t of trades) {
        const key = fingerprintTrade(t);
        let bucket = map.get(key);
        if (!bucket) {
          bucket = {
            key,
            entry_time: t.entry_time,
            direction: t.direction,
            perRun: new Map(),
          };
          map.set(key, bucket);
        }
        bucket.perRun.set(r.jobId, t.exit_price != null ? t.pnl_pct : null);
      }
    }
    // Only keep trades that appeared in ≥2 runs.
    return Array.from(map.values())
      .filter((b) => b.perRun.size >= 2)
      .sort((a, b) => a.entry_time.localeCompare(b.entry_time));
  }, [ready]);

  // Caveat: different timeframes will never line up.
  const timeframes = Array.from(
    new Set(ready.map((r) => r.payload?.timeframe).filter(Boolean))
  );
  const mixedTimeframes = timeframes.length > 1;

  const columns = useMemo<TableColumn<SharedTradeBucket>[]>(() => {
    const first: TableColumn<SharedTradeBucket> = {
      key: "entry_time",
      header: "Entry",
      render: (b) => (
        <span className="font-mono text-fg-secondary num-tabular text-[12px]">
          {b.entry_time?.replace("T", " ").slice(0, 19) ?? "—"}
        </span>
      ),
    };
    const dir: TableColumn<SharedTradeBucket> = {
      key: "direction",
      header: "Side",
      render: (b) => (
        <Tag intent={b.direction === "BUY" ? "bid" : "ask"}>{b.direction}</Tag>
      ),
    };
    const runCols: TableColumn<SharedTradeBucket>[] = ready.map((r) => ({
      key: `run-${r.jobId}`,
      header: (
        <span className="font-mono text-[11px]">#{shortJob(r.jobId)}</span>
      ),
      align: "right",
      render: (b) => {
        const pnl = b.perRun.get(r.jobId);
        if (pnl === undefined) {
          return <span className="text-fg-muted">·</span>;
        }
        if (pnl === null) {
          return <span className="text-fg-muted">open</span>;
        }
        return <PnLBadge value={pnl * 100} mode="pct" hideArrow />;
      },
    }));
    return [first, dir, ...runCols];
  }, [ready]);

  return (
    <section className="rounded-md border border-border-subtle bg-bg-panel">
      <header className="flex items-center justify-between gap-3 px-4 py-2.5 border-b border-border-subtle">
        <h2 className="text-[11px] font-semibold uppercase tracking-wider text-fg-muted">
          Shared trades
          <span className="ml-2 text-fg-secondary normal-case tracking-normal num-tabular">
            ({buckets.length})
          </span>
        </h2>
        <Tag intent="warn">Client-side fingerprint</Tag>
      </header>
      {mixedTimeframes && (
        <div className="px-4 py-2.5 border-b border-border-subtle bg-warn-700/5 text-[11px] text-fg-muted leading-relaxed flex items-start gap-2">
          <Info className="w-3.5 h-3.5 shrink-0 mt-0.5 text-warn-400" strokeWidth={1.5} aria-hidden />
          <span>
            These runs use different timeframes ({timeframes.join(", ")}). Entry
            timestamps won&apos;t align between timeframes, so the shared-trade
            list will be sparse or empty.
          </span>
        </div>
      )}
      {buckets.length === 0 ? (
        <div className="px-4 py-8 text-center text-[12px] text-fg-muted">
          {ready.length < 2
            ? "Need at least 2 completed runs."
            : "No trades shared across these runs (by entry-time + side)."}
        </div>
      ) : (
        <div className="overflow-auto">
          <Table
            data={buckets}
            columns={columns}
            rowKey={(b) => b.key}
            density="standard"
            gridLines="horizontal"
            emptyMessage="No shared trades."
          />
        </div>
      )}
      <footer className="px-4 py-2.5 border-t border-border-subtle text-[11px] text-fg-muted leading-relaxed flex items-start gap-2">
        <Info className="w-3.5 h-3.5 shrink-0 mt-0.5 text-warn-400" strokeWidth={1.5} aria-hidden />
        <span>
          Trades are matched by <code className="font-mono">entry_time</code> +{" "}
          <code className="font-mono">direction</code> — backend doesn&apos;t emit
          a canonical shared-trade key. Two runs with different slippage models
          on the same dataset will line up here; runs across different
          timeframes generally won&apos;t.
        </span>
      </footer>
    </section>
  );
}
