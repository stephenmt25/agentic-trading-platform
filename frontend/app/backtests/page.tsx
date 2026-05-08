"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import {
  Plus,
  Search,
  Loader2,
  AlertTriangle,
  Trash2,
  Archive,
  GitCompare,
  RotateCcw,
} from "lucide-react";
import { toast } from "sonner";
import {
  Button,
  Input,
  Select,
  type SelectOption,
} from "@/components/primitives";
import {
  Pill,
  StatusDot,
  type SortDirection,
  type TableColumn,
  Table,
} from "@/components/data-display";
import { PnLBadge } from "@/components/trading";
import { cn } from "@/lib/utils";
import { api, type ProfileResponse } from "@/lib/api/client";
import { NewBacktestDialog } from "./_components/NewBacktestDialog";

type RunStatus = "queued" | "running" | "completed" | "failed";

interface RunRow {
  jobId: string;
  profileId: string | null;
  profileName: string;
  symbol: string;
  startDate: string | null;
  endDate: string | null;
  timeframe: string | null;
  totalTrades: number;
  winRate: number;
  avgReturn: number;
  maxDrawdown: number;
  sharpe: number;
  profitFactor: number;
  createdAt: string;
  status: RunStatus;
  errorDetail?: string;
  /** Live runs only — current poll generation for cleanup. */
  pollKey?: number;
}

const STATUS_OPTIONS: SelectOption[] = [
  { value: "all", label: "All statuses" },
  { value: "completed", label: "Completed" },
  { value: "running", label: "Running" },
  { value: "queued", label: "Queued" },
  { value: "failed", label: "Failed" },
];

const DENSITY_OPTIONS: SelectOption[] = [
  { value: "compact", label: "Compact" },
  { value: "standard", label: "Standard" },
  { value: "comfortable", label: "Comfortable" },
];

function toNumber(v: string | number | null | undefined, fallback = 0): number {
  if (typeof v === "number") return Number.isFinite(v) ? v : fallback;
  if (typeof v === "string") {
    const n = parseFloat(v);
    return Number.isFinite(n) ? n : fallback;
  }
  return fallback;
}

function shortJob(jobId: string): string {
  // History returns full UUIDs; show first 7 chars in monospace.
  return jobId.slice(0, 7);
}

function formatRange(start: string | null, end: string | null): string {
  if (!start && !end) return "—";
  const s = (start ?? "").slice(0, 10);
  const e = (end ?? "").slice(0, 10);
  if (!s) return e;
  if (!e) return s;
  return `${s} → ${e}`;
}

function formatDays(start: string | null, end: string | null): string {
  if (!start || !end) return "";
  const ms = Date.parse(end) - Date.parse(start);
  if (!Number.isFinite(ms) || ms <= 0) return "";
  const days = Math.round(ms / (1000 * 60 * 60 * 24));
  return `${days}d`;
}

function statusPill(status: RunStatus, errorDetail?: string) {
  if (status === "completed") {
    return (
      <Pill intent="bid" icon={<StatusDot state="live" size={6} />}>
        Done
      </Pill>
    );
  }
  if (status === "running") {
    return (
      <Pill intent="accent" icon={<StatusDot state="live" size={6} pulse />}>
        Running
      </Pill>
    );
  }
  if (status === "queued") {
    return (
      <Pill intent="neutral" icon={<StatusDot state="idle" size={6} />}>
        Queued
      </Pill>
    );
  }
  return (
    <Pill intent="ask" icon={<StatusDot state="error" size={6} />}>
      {errorDetail ? "Failed" : "Failed"}
    </Pill>
  );
}

const POLL_MS = 2500;

/**
 * /backtests — run list. Per surface spec
 * docs/design/05-surface-specs/04-backtesting-analytics.md §1.
 *
 * Composes Table + filter bar + selection action bar + new-backtest
 * modal. Live (queued/running) runs are tracked in local state and
 * merged into the same table.
 */
export default function BacktestsListPage() {
  const router = useRouter();

  const [runs, setRuns] = useState<RunRow[]>([]);
  const [liveRuns, setLiveRuns] = useState<RunRow[]>([]);
  const [profiles, setProfiles] = useState<ProfileResponse[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [filterProfile, setFilterProfile] = useState<string>("all");
  const [filterStatus, setFilterStatus] = useState<string>("all");
  const [search, setSearch] = useState("");
  const [filterFrom, setFilterFrom] = useState("");
  const [filterTo, setFilterTo] = useState("");

  const [density, setDensity] = useState<"compact" | "standard" | "comfortable">(
    "standard"
  );

  const [sortKey, setSortKey] = useState<string>("createdAt");
  const [sortDir, setSortDir] = useState<SortDirection>("desc");

  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());
  const [showNewDialog, setShowNewDialog] = useState(false);

  const profileNameFor = useCallback(
    (id: string | null) => {
      if (!id) return "—";
      const p = profiles.find((x) => x.profile_id === id);
      return p?.name || id.slice(0, 7);
    },
    [profiles]
  );

  const loadHistory = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [profilesData, history] = await Promise.all([
        api.profiles.list().catch(() => [] as ProfileResponse[]),
        api.backtest.history({ limit: 100 }),
      ]);
      setProfiles(profilesData);
      const items: RunRow[] = history.items.map((r) => ({
        jobId: r.job_id,
        profileId: r.profile_id,
        profileName: profilesData.find((p) => p.profile_id === r.profile_id)?.name ?? (r.profile_id?.slice(0, 7) ?? "—"),
        symbol: r.symbol,
        startDate: r.start_date,
        endDate: r.end_date,
        timeframe: r.timeframe,
        totalTrades: r.total_trades,
        winRate: toNumber(r.win_rate),
        avgReturn: toNumber(r.avg_return),
        maxDrawdown: toNumber(r.max_drawdown),
        sharpe: toNumber(r.sharpe),
        profitFactor: toNumber(r.profit_factor),
        createdAt: r.created_at,
        status: "completed",
      }));
      setRuns(items);
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : "Failed to load backtests";
      if (!msg.includes("Unauthorized")) setError(msg);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadHistory();
  }, [loadHistory]);

  // Backfill profile names if profiles list arrives after history.
  useEffect(() => {
    if (profiles.length === 0) return;
    setRuns((prev) =>
      prev.map((r) => ({
        ...r,
        profileName: profileNameFor(r.profileId),
      }))
    );
  }, [profiles, profileNameFor]);

  // Poll live runs.
  const pollGenRef = useRef(0);
  useEffect(() => {
    if (liveRuns.length === 0) return;
    const gen = ++pollGenRef.current;
    let cancelled = false;
    const tick = async () => {
      const inflight = liveRuns.filter(
        (r) => r.status === "queued" || r.status === "running"
      );
      if (inflight.length === 0) return;
      await Promise.all(
        inflight.map(async (r) => {
          try {
            const res = await api.backtest.result(r.jobId);
            if (cancelled || gen !== pollGenRef.current) return;
            const status = res.status as RunStatus;
            if (status === "completed") {
              const payload = res as unknown as Record<string, unknown>;
              const equityFinal = toNumber(payload.equity_final as number | string);
              const equityInitial = toNumber(payload.equity_initial as number | string, 1);
              const avgReturn = equityInitial > 0 ? equityFinal / equityInitial - 1 : 0;
              setLiveRuns((prev) => prev.filter((x) => x.jobId !== r.jobId));
              setRuns((prev) => [
                {
                  ...r,
                  status: "completed",
                  totalTrades: toNumber(payload.total_trades as number | string),
                  winRate: toNumber(payload.win_rate as number | string),
                  avgReturn,
                  maxDrawdown: toNumber(payload.max_drawdown as number | string),
                  sharpe: toNumber(payload.sharpe as number | string),
                  profitFactor: toNumber(payload.profit_factor as number | string),
                  createdAt: new Date().toISOString(),
                },
                ...prev,
              ]);
              toast.success(`Backtest ${shortJob(r.jobId)} complete.`);
            } else if (status === "failed") {
              const detail = (res as { error?: string }).error;
              setLiveRuns((prev) =>
                prev.map((x) =>
                  x.jobId === r.jobId ? { ...x, status: "failed", errorDetail: detail } : x
                )
              );
              toast.error(`Backtest ${shortJob(r.jobId)} failed${detail ? `: ${detail}` : "."}`);
            } else if (status === "running" || status === "queued") {
              setLiveRuns((prev) =>
                prev.map((x) =>
                  x.jobId === r.jobId ? { ...x, status } : x
                )
              );
            }
          } catch {
            // transient — keep polling next tick
          }
        })
      );
    };
    const id = window.setInterval(tick, POLL_MS);
    void tick();
    return () => {
      cancelled = true;
      window.clearInterval(id);
    };
  }, [liveRuns]);

  const profileOptions: SelectOption[] = useMemo(
    () => [
      { value: "all", label: "All profiles" },
      ...profiles.map((p) => ({ value: p.profile_id, label: p.name || p.profile_id })),
    ],
    [profiles]
  );

  const allRuns = useMemo<RunRow[]>(
    () => [...liveRuns, ...runs],
    [liveRuns, runs]
  );

  const filtered = useMemo(() => {
    const q = search.trim().toLowerCase();
    return allRuns.filter((r) => {
      if (filterProfile !== "all" && r.profileId !== filterProfile) return false;
      if (filterStatus !== "all" && r.status !== filterStatus) return false;
      if (filterFrom && r.startDate && r.startDate.slice(0, 10) < filterFrom) return false;
      if (filterTo && r.endDate && r.endDate.slice(0, 10) > filterTo) return false;
      if (q) {
        const hay = `${r.jobId} ${r.profileName} ${r.symbol}`.toLowerCase();
        if (!hay.includes(q)) return false;
      }
      return true;
    });
  }, [allRuns, search, filterProfile, filterStatus, filterFrom, filterTo]);

  const sorted = useMemo(() => {
    const copy = [...filtered];
    copy.sort((a, b) => {
      const av = (a as unknown as Record<string, unknown>)[sortKey];
      const bv = (b as unknown as Record<string, unknown>)[sortKey];
      let cmp = 0;
      if (typeof av === "number" && typeof bv === "number") {
        cmp = av - bv;
      } else if (typeof av === "string" && typeof bv === "string") {
        cmp = av.localeCompare(bv);
      } else {
        cmp = String(av ?? "").localeCompare(String(bv ?? ""));
      }
      return sortDir === "asc" ? cmp : -cmp;
    });
    return copy;
  }, [filtered, sortKey, sortDir]);

  const toggleSelect = (jobId: string) => {
    setSelectedIds((prev) => {
      const next = new Set(prev);
      if (next.has(jobId)) next.delete(jobId);
      else next.add(jobId);
      return next;
    });
  };

  const clearSelection = () => setSelectedIds(new Set());

  const selectedRows = sorted.filter((r) => selectedIds.has(r.jobId));

  const columns: TableColumn<RunRow>[] = useMemo(
    () => [
      {
        key: "select",
        header: "",
        width: "32px",
        render: (row) => (
          <input
            type="checkbox"
            checked={selectedIds.has(row.jobId)}
            onChange={(e) => {
              e.stopPropagation();
              toggleSelect(row.jobId);
            }}
            onClick={(e) => e.stopPropagation()}
            aria-label={`Select run ${shortJob(row.jobId)}`}
            className="accent-accent-500 cursor-pointer"
          />
        ),
      },
      {
        key: "jobId",
        header: "Run",
        sortable: true,
        render: (row) => (
          <span className="font-mono text-fg num-tabular">#{shortJob(row.jobId)}</span>
        ),
      },
      {
        key: "profileName",
        header: "Profile",
        sortable: true,
        render: (row) => (
          <span className="text-fg truncate" title={row.profileName}>
            {row.profileName}
          </span>
        ),
      },
      {
        key: "symbol",
        header: "Symbol",
        sortable: true,
        render: (row) => (
          <span className="font-mono text-fg-secondary num-tabular">{row.symbol}</span>
        ),
      },
      {
        key: "startDate",
        header: "Range",
        sortable: true,
        render: (row) => {
          const days = formatDays(row.startDate, row.endDate);
          return (
            <span className="font-mono text-fg-secondary num-tabular">
              {formatRange(row.startDate, row.endDate)}
              {days && <span className="text-fg-muted ml-1.5">· {days}</span>}
            </span>
          );
        },
      },
      {
        key: "totalTrades",
        header: "Trades",
        numeric: true,
        sortable: true,
        render: (row) =>
          row.status === "completed" ? row.totalTrades.toLocaleString() : "—",
      },
      {
        key: "winRate",
        header: "Win",
        numeric: true,
        sortable: true,
        render: (row) =>
          row.status === "completed"
            ? `${(row.winRate * 100).toFixed(0)}%`
            : "—",
      },
      {
        key: "avgReturn",
        header: "Avg",
        numeric: true,
        sortable: true,
        render: (row) =>
          row.status === "completed" ? (
            <PnLBadge value={row.avgReturn * 100} mode="pct" hideArrow />
          ) : (
            <span className="text-fg-muted">—</span>
          ),
      },
      {
        key: "sharpe",
        header: "Sharpe",
        numeric: true,
        sortable: true,
        render: (row) =>
          row.status === "completed" ? row.sharpe.toFixed(2) : "—",
      },
      {
        key: "maxDrawdown",
        header: "Max DD",
        numeric: true,
        sortable: true,
        render: (row) =>
          row.status === "completed" ? (
            <span className="text-ask-400 num-tabular">
              {(row.maxDrawdown * 100).toFixed(1)}%
            </span>
          ) : (
            <span className="text-fg-muted">—</span>
          ),
      },
      {
        key: "status",
        header: "Status",
        align: "right",
        render: (row) => statusPill(row.status, row.errorDetail),
      },
    ],
    [selectedIds]
  );

  const totalCount = allRuns.length;
  const hasFilters =
    filterProfile !== "all" ||
    filterStatus !== "all" ||
    !!filterFrom ||
    !!filterTo ||
    !!search.trim();

  return (
    <div data-mode="cool" className="flex flex-col h-full bg-bg-canvas text-fg">
      <header className="flex items-center justify-between gap-3 border-b border-border-subtle px-6 py-4">
        <div>
          <h1 className="text-[18px] font-semibold tracking-tight text-fg">
            Backtesting
          </h1>
          <p className="text-[12px] text-fg-muted mt-0.5">
            Evaluate profiles against historical data without risking capital.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Button
            intent="secondary"
            size="md"
            leftIcon={<RotateCcw className="w-3.5 h-3.5" />}
            onClick={loadHistory}
            disabled={loading}
          >
            Refresh
          </Button>
          <Button
            intent="primary"
            size="md"
            leftIcon={<Plus className="w-4 h-4" />}
            onClick={() => setShowNewDialog(true)}
          >
            New backtest
          </Button>
        </div>
      </header>

      <div className="px-6 py-4 border-b border-border-subtle flex flex-wrap items-end gap-3">
        <Select
          label="Profile"
          options={profileOptions}
          value={filterProfile}
          onValueChange={setFilterProfile}
          density="standard"
          searchable
          className="min-w-[180px]"
        />
        <Select
          label="Status"
          options={STATUS_OPTIONS}
          value={filterStatus}
          onValueChange={setFilterStatus}
          density="standard"
          className="min-w-[150px]"
        />
        <Input
          label="From"
          type="date"
          density="standard"
          value={filterFrom}
          onChange={(e) => setFilterFrom(e.target.value)}
          className="max-w-[160px]"
        />
        <Input
          label="To"
          type="date"
          density="standard"
          value={filterTo}
          onChange={(e) => setFilterTo(e.target.value)}
          className="max-w-[160px]"
        />
        <Input
          label="Search"
          density="standard"
          placeholder="Run ID, profile, symbol…"
          leftAdornment={<Search className="w-3.5 h-3.5" strokeWidth={1.5} />}
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          className="flex-1 min-w-[200px]"
        />
        <Select
          label="Density"
          options={DENSITY_OPTIONS}
          value={density}
          onValueChange={(v) =>
            setDensity(v as "compact" | "standard" | "comfortable")
          }
          density="standard"
          className="min-w-[140px]"
        />
        {hasFilters && (
          <Button
            intent="secondary"
            size="md"
            onClick={() => {
              setFilterProfile("all");
              setFilterStatus("all");
              setFilterFrom("");
              setFilterTo("");
              setSearch("");
            }}
          >
            Clear
          </Button>
        )}
      </div>

      <div className="flex-1 min-h-0 overflow-auto">
        {error && (
          <div
            role="alert"
            className="mx-6 mt-4 rounded-md border border-danger-700/40 bg-danger-700/10 p-4 flex items-start gap-3 text-[13px] text-danger-500"
          >
            <AlertTriangle className="w-4 h-4 shrink-0 mt-0.5" strokeWidth={1.5} aria-hidden />
            <div className="flex-1">
              <p className="font-medium">Could not load backtests.</p>
              <p className="text-fg-muted mt-0.5">{error}</p>
            </div>
            <Button intent="secondary" size="sm" onClick={loadHistory}>
              Retry
            </Button>
          </div>
        )}

        {loading && !error && (
          <div className="mx-6 mt-4 rounded-md border border-border-subtle bg-bg-panel p-6 flex items-center gap-3">
            <Loader2 className="w-4 h-4 text-fg-muted animate-spin" aria-hidden />
            <span className="text-[13px] text-fg-muted">Loading backtests…</span>
          </div>
        )}

        {!loading && !error && totalCount === 0 && (
          <EmptyState onCreate={() => setShowNewDialog(true)} />
        )}

        {!loading && !error && totalCount > 0 && sorted.length === 0 && (
          <div className="mx-6 mt-8 rounded-md border border-border-subtle bg-bg-panel/60 p-8 text-center">
            <p className="text-fg">No runs match your filters.</p>
            <p className="text-[13px] text-fg-muted mt-1">
              Adjust filters or clear them to see all runs.
            </p>
          </div>
        )}

        {!loading && !error && sorted.length > 0 && (
          <div className="px-6 py-4">
            <Table
              data={sorted}
              columns={columns}
              rowKey={(r) => r.jobId}
              density={density}
              gridLines="horizontal"
              striping={density === "compact" ? "none" : "every-other"}
              selectable="single"
              selectedRowKey={null}
              onRowClick={(row) => {
                if (row.status === "completed") {
                  router.push(`/backtests/${encodeURIComponent(row.jobId)}`);
                } else if (row.status === "failed" && row.errorDetail) {
                  toast.error(row.errorDetail);
                }
              }}
              sortKey={sortKey}
              sortDirection={sortDir}
              onSortChange={(key, dir) => {
                setSortKey(key);
                setSortDir(dir);
              }}
              emptyMessage="No runs."
            />
          </div>
        )}
      </div>

      {selectedRows.length > 0 && (
        <SelectionBar
          count={selectedRows.length}
          canCompare={selectedRows.length >= 2}
          onCompare={() => {
            const ids = selectedRows.map((r) => encodeURIComponent(r.jobId)).join(",");
            router.push(`/backtests/compare?runs=${ids}`);
          }}
          onArchive={() =>
            toast.error(
              "Archive endpoint not wired yet — backtests are immutable for auditability."
            )
          }
          onDelete={() =>
            toast.error(
              "Delete endpoint not wired yet — backtests are immutable for auditability."
            )
          }
          onClear={clearSelection}
        />
      )}

      {showNewDialog && (
        <NewBacktestDialog
          profiles={profiles}
          onCancel={() => setShowNewDialog(false)}
          onSubmit={(submitted) => {
            setShowNewDialog(false);
            // Optimistic row in `liveRuns` to surface the in-flight backtest.
            setLiveRuns((prev) => [
              {
                jobId: submitted.jobId,
                profileId: submitted.profileId,
                profileName: profileNameFor(submitted.profileId),
                symbol: submitted.symbol,
                startDate: submitted.startDate,
                endDate: submitted.endDate,
                timeframe: submitted.timeframe,
                totalTrades: 0,
                winRate: 0,
                avgReturn: 0,
                maxDrawdown: 0,
                sharpe: 0,
                profitFactor: 0,
                createdAt: new Date().toISOString(),
                status: submitted.status,
              },
              ...prev,
            ]);
            toast.success(`Backtest ${shortJob(submitted.jobId)} queued.`);
          }}
        />
      )}
    </div>
  );
}

function EmptyState({ onCreate }: { onCreate: () => void }) {
  return (
    <div className="mx-6 mt-12 max-w-xl mx-auto rounded-lg border border-border-subtle bg-bg-panel p-10 text-center">
      <h2 className="text-[16px] font-semibold text-fg">No backtests yet.</h2>
      <p className="text-[13px] text-fg-secondary mt-2">
        Backtests let you evaluate a profile against historical data without
        risking capital. Each run is immutable and reproducible — including a
        snapshot of the canvas at run time.
      </p>
      <div className="mt-5">
        <Button
          intent="primary"
          size="lg"
          leftIcon={<Plus className="w-4 h-4" />}
          onClick={onCreate}
        >
          Run your first backtest
        </Button>
      </div>
    </div>
  );
}

function SelectionBar({
  count,
  canCompare,
  onCompare,
  onArchive,
  onDelete,
  onClear,
}: {
  count: number;
  canCompare: boolean;
  onCompare: () => void;
  onArchive: () => void;
  onDelete: () => void;
  onClear: () => void;
}) {
  return (
    <div
      className={cn(
        "shrink-0 border-t border-border-subtle bg-bg-panel/95 backdrop-blur",
        "px-6 py-3 flex items-center justify-between gap-3"
      )}
    >
      <p className="text-[13px] text-fg-secondary">
        Selected: <span className="text-fg num-tabular font-semibold">{count}</span>{" "}
        {count === 1 ? "run" : "runs"}
      </p>
      <div className="flex items-center gap-2">
        <Button
          intent="secondary"
          size="md"
          leftIcon={<GitCompare className="w-3.5 h-3.5" />}
          onClick={onCompare}
          disabled={!canCompare}
          title={!canCompare ? "Select 2 or more runs to compare" : undefined}
        >
          Compare
        </Button>
        <Button
          intent="secondary"
          size="md"
          leftIcon={<Archive className="w-3.5 h-3.5" />}
          onClick={onArchive}
        >
          Archive
        </Button>
        <Button
          intent="secondary"
          size="md"
          leftIcon={<Trash2 className="w-3.5 h-3.5" />}
          onClick={onDelete}
        >
          Delete
        </Button>
        <Button intent="secondary" size="md" onClick={onClear}>
          Clear
        </Button>
      </div>
    </div>
  );
}
