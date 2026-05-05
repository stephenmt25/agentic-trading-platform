"use client";

import { useEffect, useState, useCallback, useRef } from "react";
import dynamic from "next/dynamic";
import {
  TrendingUp, ShieldAlert, ShieldCheck,
  Loader2, ChevronDown, ChevronUp, FlaskConical, Activity, Beaker, AlertTriangle, RefreshCw,
  X, BarChart3,
} from "lucide-react";
import { motion, AnimatePresence } from "framer-motion";
import { pageEnter } from "@/lib/motion";
import { toast } from "sonner";
import {
  api, type ProfileResponse, type PaperTradingStatus,
  type KillSwitchStatus, type TradingModeStatus,
} from "@/lib/api/client";
import { DecisionFeed } from "@/components/decisions/DecisionFeed";
import { DailyReportDetail } from "@/components/performance/DailyReportDetail";
import { RiskMonitorCard } from "@/components/risk/RiskMonitorCard";
import { PositionsPanel } from "@/components/trade/PositionsPanel";
import AnalysisContent from "../analytics/AnalysisContent";
import PerformanceContent from "../analytics/PerformanceContent";

const ApprovalQueue = dynamic(() => import("../approval/page"), {
  ssr: false,
  loading: () => <Loader2 className="w-5 h-5 animate-spin text-muted-foreground mx-auto mt-12" />,
});

const POLL_INTERVAL = 30_000;

// ─────────────────────────────────────────────────────────────
// Subcomponents
// ─────────────────────────────────────────────────────────────

function ModeBadge({ mode }: { mode: TradingModeStatus | null }) {
  if (!mode) return <span className="w-16 h-6 bg-accent animate-pulse rounded" />;
  const m = mode.effective_mode;
  const config = {
    PAPER: { Icon: FlaskConical, cls: "bg-amber-500/15 text-amber-400 border-amber-500/30" },
    TESTNET: { Icon: Beaker, cls: "bg-blue-500/15 text-blue-400 border-blue-500/30" },
    LIVE: { Icon: Activity, cls: "bg-emerald-500/15 text-emerald-400 border-emerald-500/30" },
  } as const;
  const { Icon, cls } = config[m];
  return (
    <span className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-md text-[11px] font-mono font-semibold uppercase tracking-wider border ${cls}`}>
      <Icon className="w-3 h-3" />
      {m}
    </span>
  );
}

function KillSwitchControl({ status, onToggle, busy }: {
  status: KillSwitchStatus | null;
  onToggle: () => void;
  busy: boolean;
}) {
  const active = status?.active ?? false;
  return (
    <button
      onClick={onToggle}
      disabled={busy}
      className={`flex items-center gap-1.5 px-3 py-1.5 rounded-md text-xs font-medium border transition-colors min-h-[36px] disabled:opacity-50 ${
        active
          ? "bg-red-500/15 text-red-400 border-red-500/40 hover:bg-red-500/25"
          : "bg-card text-muted-foreground border-border hover:text-foreground hover:bg-accent"
      }`}
    >
      {busy ? (
        <Loader2 className="w-3.5 h-3.5 animate-spin" />
      ) : active ? (
        <ShieldAlert className="w-3.5 h-3.5" />
      ) : (
        <ShieldCheck className="w-3.5 h-3.5" />
      )}
      {active ? "Kill Switch ACTIVE" : "Kill Switch"}
    </button>
  );
}

function StatCell({ label, value, suffix, color }: {
  label: string;
  value: string | number;
  suffix?: string;
  color?: "neutral" | "positive" | "negative";
}) {
  const colorCls =
    color === "positive" ? "text-emerald-500" :
    color === "negative" ? "text-red-500" :
    "text-foreground";
  return (
    <div className="flex items-baseline gap-1.5 min-w-0">
      <span className="text-[10px] uppercase tracking-wider text-muted-foreground font-medium shrink-0">
        {label}
      </span>
      <span className={`font-mono tabular-nums text-sm font-semibold truncate ${colorCls}`}>
        {value}{suffix && <span className="text-xs text-muted-foreground ml-0.5">{suffix}</span>}
      </span>
    </div>
  );
}

function PnlSparkline({ data }: { data: number[] }) {
  if (data.length < 2) return null;
  const width = 240;
  const height = 48;
  const padding = 2;
  const min = Math.min(...data, 0);
  const max = Math.max(...data, 0);
  const range = max - min || 1;
  const points = data
    .map((v, i) => {
      const x = padding + (i / (data.length - 1)) * (width - padding * 2);
      const y = height - padding - ((v - min) / range) * (height - padding * 2);
      return `${x},${y}`;
    })
    .join(" ");
  const zeroY = height - padding - ((0 - min) / range) * (height - padding * 2);
  const lastValue = data[data.length - 1];
  const lineColor = lastValue >= 0 ? "#22c55e" : "#ef4444";
  return (
    <svg viewBox={`0 0 ${width} ${height}`} className="w-full h-12" preserveAspectRatio="none">
      <line
        x1={padding} y1={zeroY} x2={width - padding} y2={zeroY}
        stroke="currentColor" strokeWidth="0.5" strokeDasharray="3,3"
        className="text-border"
      />
      <polyline
        points={points}
        fill="none"
        stroke={lineColor}
        strokeWidth="1.5"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}

function CollapsibleSection({
  title, subtitle, defaultOpen = false, children,
}: { title: string; subtitle?: string; defaultOpen?: boolean; children: React.ReactNode }) {
  const [open, setOpen] = useState(defaultOpen);
  return (
    <section className="border border-border rounded-md overflow-hidden">
      <button
        onClick={() => setOpen((v) => !v)}
        className="w-full flex items-center justify-between px-4 py-3 bg-card hover:bg-accent/30 transition-colors"
      >
        <div className="text-left">
          <h2 className="text-xs font-semibold tracking-wider uppercase text-foreground">{title}</h2>
          {subtitle && <p className="text-[11px] text-muted-foreground mt-0.5">{subtitle}</p>}
        </div>
        {open ? <ChevronUp className="w-4 h-4 text-muted-foreground" /> : <ChevronDown className="w-4 h-4 text-muted-foreground" />}
      </button>
      {open && <div className="border-t border-border p-4 bg-background">{children}</div>}
    </section>
  );
}

type Scope = "profile" | "system" | "symbol";

function ScopeBadge({ scope }: { scope: Scope }) {
  const config = {
    profile: { label: "PROFILE", cls: "bg-primary/10 text-primary border-primary/30" },
    system:  { label: "SYSTEM",  cls: "bg-muted/40 text-muted-foreground border-border" },
    symbol:  { label: "SYMBOL",  cls: "bg-muted/40 text-muted-foreground border-border" },
  } as const;
  const { label, cls } = config[scope];
  return (
    <span
      title={
        scope === "profile" ? "Reflects the active profile selected above"
        : scope === "system" ? "Reflects the entire engine, not just this profile"
        : "Reflects the selected chart symbol"
      }
      className={`inline-flex items-center px-1.5 py-0.5 rounded text-[9px] font-mono font-semibold tracking-wider border ${cls}`}
    >
      {label}
    </span>
  );
}

function PanelHeader({ title, subtitle, scope, action }: {
  title: string;
  subtitle?: string;
  scope?: Scope;
  action?: React.ReactNode;
}) {
  return (
    <div className="flex items-start justify-between gap-3 px-4 py-2.5 border-b border-border bg-card/40">
      <div className="min-w-0">
        <div className="flex items-center gap-2">
          <h3 className="text-xs font-semibold tracking-wider uppercase text-foreground">{title}</h3>
          {scope && <ScopeBadge scope={scope} />}
        </div>
        {subtitle && <p className="text-[11px] text-muted-foreground mt-0.5 truncate">{subtitle}</p>}
      </div>
      {action}
    </div>
  );
}

// ─────────────────────────────────────────────────────────────
// Main page
// ─────────────────────────────────────────────────────────────

export default function TradePage() {
  // Profile + scope
  const [profiles, setProfiles] = useState<ProfileResponse[]>([]);
  const [profileId, setProfileId] = useState<string | null>(null);

  // Live state
  const [mode, setMode] = useState<TradingModeStatus | null>(null);
  const [status, setStatus] = useState<PaperTradingStatus | null>(null);
  const [killSwitch, setKillSwitch] = useState<KillSwitchStatus | null>(null);
  const [killSwitchBusy, setKillSwitchBusy] = useState(false);
  const [refreshing, setRefreshing] = useState(false);
  const [lastUpdated, setLastUpdated] = useState<Date | null>(null);
  const [reviewOpen, setReviewOpen] = useState(false);
  const isInitial = useRef(true);

  // Daily P&L card — picker + drawer-open. Today's UTC date as YYYY-MM-DD
  // is the picker default; reports key off UTC dates so a local-tz default
  // would surprise the operator near midnight. openReportDate drives the
  // side drawer that opens when a report row is clicked.
  const todayUtcIso = new Date().toISOString().slice(0, 10);
  const [reportDate, setReportDate] = useState<string>(todayUtcIso);
  const [generatingReport, setGeneratingReport] = useState(false);
  const [openReportDate, setOpenReportDate] = useState<string | null>(null);

  const profileNamesById = profiles.reduce<Record<string, string>>((acc, p) => {
    acc[p.profile_id] = p.name;
    return acc;
  }, {});
  const activeProfileName = profileId ? profileNamesById[profileId] ?? null : null;

  // Profiles (one-time)
  useEffect(() => {
    api.profiles.list()
      .then((p) => {
        const active = p.filter((x) => !x.deleted_at);
        setProfiles(active);
        const firstActive = active.find((x) => x.is_active) ?? active[0];
        if (firstActive) setProfileId(firstActive.profile_id);
      })
      .catch(() => {});
  }, []);

  // Live status loop
  const loadLive = useCallback(async () => {
    if (!isInitial.current) setRefreshing(true);
    try {
      const [s, k, m] = await Promise.allSettled([
        api.paperTrading.status(),
        api.commands.killSwitchStatus(),
        api.paperTrading.mode(),
      ]);
      if (s.status === "fulfilled") setStatus(s.value);
      if (k.status === "fulfilled") setKillSwitch(k.value);
      if (m.status === "fulfilled") setMode(m.value);
      setLastUpdated(new Date());
    } finally {
      isInitial.current = false;
      setRefreshing(false);
    }
  }, []);

  useEffect(() => {
    loadLive();
    const t = setInterval(loadLive, POLL_INTERVAL);
    return () => clearInterval(t);
  }, [loadLive]);

  const handleGenerateReport = async () => {
    if (!reportDate) {
      toast.error("Pick a date first");
      return;
    }
    setGeneratingReport(true);
    try {
      const result = await api.paperTrading.generateReport(reportDate);
      await loadLive();
      if (result.report) {
        const r = result.report;
        const summary =
          `${r.total_trades} trade${r.total_trades === 1 ? "" : "s"} · ` +
          `${(r.win_rate * 100).toFixed(1)}% win · ` +
          `${r.net_pnl >= 0 ? "+" : ""}$${r.net_pnl.toFixed(2)} net`;
        if (result.wrote) {
          toast.success(`Report for ${result.report_date}`, { description: summary });
        } else {
          toast.info(`No change on ${result.report_date}`, { description: summary });
        }
        // Open the side drawer with the full transparency report rather
        // than a toast that disappears in 4 seconds.
        setOpenReportDate(result.report_date);
      } else {
        toast.info(`No trades or snapshots on ${result.report_date}`, {
          description: "Nothing to report for that day.",
        });
      }
    } catch (e: any) {
      toast.error(`Failed to generate report: ${e.message ?? e}`);
    } finally {
      setGeneratingReport(false);
    }
  };

  const toggleKillSwitch = useCallback(async () => {
    if (!killSwitch) return;
    setKillSwitchBusy(true);
    const next = !killSwitch.active;
    try {
      await api.commands.killSwitchToggle(next, next ? "Manual from dashboard" : undefined);
      const updated = await api.commands.killSwitchStatus();
      setKillSwitch(updated);
      toast.success(`Kill switch ${next ? "activated" : "deactivated"}`);
    } catch (e: any) {
      toast.error(`Kill switch failed: ${e.message}`);
    } finally {
      setKillSwitchBusy(false);
    }
  }, [killSwitch]);

  // Derived
  const m = status?.metrics;
  const dailyReports = status?.daily_reports ?? [];
  const netPnl = m?.total_net_pnl ?? 0;
  const grossPnl = m?.total_gross_pnl ?? 0;
  const winRate = m?.avg_win_rate ?? 0;
  const drawdown = m?.max_drawdown ?? 0;
  const totalTrades = m?.total_trades ?? 0;
  const sharpe = m?.avg_sharpe ?? 0;

  const tradingEnabled = mode?.trading_enabled ?? false;
  const offlineReason = killSwitch?.active ? "Kill switch active" : !tradingEnabled ? "Trading disabled" : null;

  return (
    <motion.div
      className="p-3 md:p-6 max-w-[1600px] mx-auto space-y-5"
      variants={pageEnter}
      initial="hidden"
      animate="show"
    >
      {/* ─── HEADER ─── */}
      <header className="flex flex-col gap-3">
        <div className="flex items-start justify-between gap-3 flex-wrap">
          <div className="flex items-center gap-3 flex-wrap">
            <TrendingUp className="w-5 h-5 text-primary" />
            <h1 className="text-xl font-semibold tracking-tight text-foreground">Trade</h1>
            <ModeBadge mode={mode} />
          </div>
          <div className="flex items-center gap-2">
            {lastUpdated && (
              <span className="text-[10px] text-muted-foreground font-mono tabular-nums hidden sm:inline">
                {refreshing ? "refreshing…" : `updated ${Math.floor((Date.now() - lastUpdated.getTime()) / 1000)}s ago`}
              </span>
            )}
            <button
              onClick={loadLive}
              disabled={refreshing}
              className="p-2 rounded-md text-muted-foreground hover:text-foreground hover:bg-accent transition-colors disabled:opacity-50"
              aria-label="Refresh"
            >
              <RefreshCw className={`w-3.5 h-3.5 ${refreshing ? "animate-spin" : ""}`} />
            </button>
            <KillSwitchControl status={killSwitch} onToggle={toggleKillSwitch} busy={killSwitchBusy} />
          </div>
        </div>

        {/* Profile scope */}
        <div className="flex items-center gap-3 flex-wrap">
          <span className="text-[10px] uppercase tracking-wider text-muted-foreground font-medium">Profile</span>
          <select
            value={profileId ?? ""}
            onChange={(e) => setProfileId(e.target.value || null)}
            className="bg-card border border-border rounded-md px-3 py-1.5 text-sm text-foreground min-h-[36px] focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary"
          >
            {profiles.length === 0 && <option value="">No profiles</option>}
            {profiles.map((p) => (
              <option key={p.profile_id} value={p.profile_id}>
                {p.name}{p.is_active ? "" : " (inactive)"}
              </option>
            ))}
          </select>
          {offlineReason && (
            <span className="inline-flex items-center gap-1.5 px-2 py-1 rounded-md bg-red-500/10 border border-red-500/30 text-[11px] text-red-400">
              <AlertTriangle className="w-3 h-3" />
              {offlineReason}
            </span>
          )}
        </div>
        <p className="text-[11px] text-muted-foreground">
          Each panel below is tagged{" "}
          <ScopeBadge scope="profile" />{" "}reflects the selected profile,{" "}
          <ScopeBadge scope="system" />{" "}reflects the engine as a whole,{" "}
          <ScopeBadge scope="symbol" />{" "}reflects the chart symbol.
        </p>
      </header>

      {/* ─── 1. ENGINE TOTALS + DAILY P&L ─── 7:3 width on xl screens ─── */}
      <div className="grid grid-cols-1 xl:grid-cols-10 gap-4">
      <section className="xl:col-span-7 self-start border border-border rounded-md overflow-hidden">
        <PanelHeader
          title="Engine totals"
          subtitle="Aggregate performance across all profiles since boot"
          scope="system"
        />
        <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-x-4 gap-y-2 px-4 py-2 bg-card">
          <StatCell
            label="Net P&L"
            value={`${netPnl >= 0 ? "+" : ""}$${netPnl.toFixed(2)}`}
            color={netPnl > 0 ? "positive" : netPnl < 0 ? "negative" : "neutral"}
          />
          <StatCell
            label="Gross P&L"
            value={`${grossPnl >= 0 ? "+" : ""}$${grossPnl.toFixed(2)}`}
            color={grossPnl > 0 ? "positive" : grossPnl < 0 ? "negative" : "neutral"}
          />
          <StatCell label="Trades" value={totalTrades.toLocaleString()} />
          <StatCell
            label="Win rate"
            value={`${(winRate * 100).toFixed(1)}`}
            suffix="%"
            color={winRate >= 0.5 ? "positive" : winRate > 0 ? "negative" : "neutral"}
          />
          <StatCell
            label="Max DD"
            value={`${(drawdown * 100).toFixed(1)}`}
            suffix="%"
            color={drawdown > 0 ? "negative" : "neutral"}
          />
          <StatCell
            label="Sharpe"
            value={sharpe.toFixed(2)}
            color={sharpe >= 1 ? "positive" : sharpe < 0 ? "negative" : "neutral"}
          />
        </div>
      </section>

      {/* ─── 2. DAILY P&L ─── per-day report list with on-demand generator ─── */}
      <section className="xl:col-span-3 border border-border rounded-md overflow-hidden flex flex-col">
        <PanelHeader
          title="Daily P&L"
          subtitle="Per-day reports — sparkline + drill-down"
          scope="system"
          action={
            <div className="flex items-center gap-2 text-xs">
              <input
                type="date"
                value={reportDate}
                max={todayUtcIso}
                onChange={(e) => setReportDate(e.target.value)}
                disabled={generatingReport}
                className="bg-background border border-border rounded px-2 py-1 font-mono text-xs focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary disabled:opacity-50"
                aria-label="Report date (UTC)"
              />
              <button
                onClick={handleGenerateReport}
                disabled={generatingReport || !reportDate}
                className="px-3 py-1 rounded border border-border bg-accent hover:bg-accent/80 transition-colors uppercase tracking-wider font-mono disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-1.5 min-h-[28px]"
              >
                {generatingReport && <Loader2 className="w-3 h-3 animate-spin" />}
                {generatingReport ? "Generating…" : "Create Report"}
              </button>
            </div>
          }
        />
        <div className="p-4 flex flex-col gap-3">
          {dailyReports.length > 1 && (
            <PnlSparkline data={dailyReports.map((r) => r.net_pnl).reverse()} />
          )}

          <div className="max-h-[280px] overflow-y-auto pr-1">
            <div className="space-y-1.5 font-mono text-xs">
              {dailyReports.length === 0 ? (
                <div className="p-3 border border-border rounded-md flex justify-between items-center opacity-50">
                  <span className="text-muted-foreground">Day 0</span>
                  <span className="text-muted-foreground">Awaiting first report…</span>
                </div>
              ) : (
                dailyReports.map((report) => (
                  <button
                    key={report.id}
                    id={`report-row-${report.id}`}
                    onClick={() => setOpenReportDate(report.report_date)}
                    className="w-full p-2.5 border border-border rounded-md flex justify-between items-center hover:bg-accent transition-colors text-left min-h-[40px]"
                    title="Open full transparency report"
                  >
                    <div className="flex flex-col gap-0.5">
                      <span className="text-foreground font-medium">{report.report_date}</span>
                      <span className="text-xs text-muted-foreground tabular-nums">
                        {report.total_trades} trades | {(report.win_rate * 100).toFixed(1)}% win |{" "}
                        <span className={report.net_pnl >= 0 ? "text-emerald-500" : "text-red-500"}>
                          ${report.net_pnl.toFixed(2)}
                        </span>
                      </span>
                    </div>
                    <span className="text-[10px] uppercase tracking-wider font-mono text-muted-foreground">→</span>
                  </button>
                ))
              )}
            </div>
          </div>
        </div>
      </section>
      </div>

      {/* ─── 3. LIVE ACTIVITY ─── what is the engine doing right now ─── */}
      <div className="flex items-center justify-between gap-3">
        <div className="min-w-0">
          <h2 className="text-xs font-semibold tracking-wider uppercase text-foreground">Live activity</h2>
          <p className="text-[11px] text-muted-foreground mt-0.5">
            Decisions and price stream — what the engine is doing right now.
          </p>
        </div>
        <button
          onClick={() => setReviewOpen(true)}
          className="inline-flex items-center gap-2 px-3 py-1.5 rounded-md text-xs font-medium border border-border bg-card hover:bg-accent/40 transition-colors min-h-[36px] shrink-0"
          title="Gate efficacy, weight evolution, and trade attribution"
        >
          <BarChart3 className="w-3.5 h-3.5 text-primary" />
          <span className="text-foreground">Performance review</span>
          <ScopeBadge scope="profile" />
          <span className="text-[10px] uppercase tracking-wider font-mono text-muted-foreground">→</span>
        </button>
      </div>

      <div className="grid grid-cols-1 xl:grid-cols-5 gap-4">
        <section className="xl:col-span-2 border border-border rounded-md overflow-hidden flex flex-col h-[760px]">
          <PanelHeader
            title="Decision Feed"
            subtitle="Live signals as the engine evaluates them — approvals, blocks, and reasons"
            scope="profile"
          />
          <div className="flex-1 min-h-0 overflow-hidden p-3">
            <DecisionFeed profileId={profileId} />
          </div>
        </section>

        <section className="xl:col-span-3 border border-border rounded-md overflow-hidden flex flex-col h-[760px]">
          <PanelHeader
            title="Price · Agent overlays"
            subtitle="Symbol price with agent score overlays"
            scope="symbol"
          />
          <div className="flex-1 overflow-hidden p-3">
            <AnalysisContent />
          </div>
        </section>
      </div>

      {/* ─── 2. CURRENT EXPOSURE ─── what did those decisions commit us to ─── */}
      <section className="border border-border rounded-md overflow-hidden flex flex-col">
        <PanelHeader
          title="Open positions"
          subtitle="Live positions for the selected profile · refreshes every 15s"
          scope="profile"
        />
        <div className="px-2 pb-2 max-h-[360px] overflow-y-auto">
          <PositionsPanel profileId={profileId} />
        </div>
      </section>

      {/* ─── 3. CONSTRAINTS ─── why the engine can or can't do more ─── */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <section className="border border-border rounded-md overflow-hidden">
          <PanelHeader
            title="Risk monitor"
            subtitle="Live drawdown, allocation, and exposure"
            scope="profile"
          />
          <div className="p-4">
            <RiskMonitorCard
              profileIds={profileId ? [profileId] : undefined}
              profileNamesById={profileNamesById}
            />
          </div>
        </section>

        <section className="border border-border rounded-md overflow-hidden">
          <PanelHeader
            title="Approvals"
            subtitle="Trades held by the HITL gate awaiting decision · all profiles"
            scope="system"
          />
          <div className="p-2">
            <ApprovalQueue />
          </div>
        </section>
      </div>

      {/* Performance review drawer is triggered from the live-activity header above. */}
      <PerformanceReviewDrawer
        open={reviewOpen}
        onClose={() => setReviewOpen(false)}
        profileId={profileId}
        profileName={activeProfileName}
      />

      {/* Daily report drawer — opened by clicking a report row or the
          Create Report button. Pulls the full /paper-trading/reports/{date}/detail
          payload (summary + trades w/ decision lineage + blocked decisions). */}
      <DailyReportDrawer
        date={openReportDate}
        onClose={() => setOpenReportDate(null)}
      />
    </motion.div>
  );
}

function DailyReportDrawer({ date, onClose }: {
  date: string | null;
  onClose: () => void;
}) {
  const open = date != null;

  // Lock body scroll while open
  useEffect(() => {
    if (!open) return;
    const prev = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => { document.body.style.overflow = prev; };
  }, [open]);

  // Close on Escape
  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => { if (e.key === "Escape") onClose(); };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, onClose]);

  return (
    <AnimatePresence>
      {open && date && (
        <>
          <motion.div
            key="report-backdrop"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.15 }}
            onClick={onClose}
            className="fixed inset-0 z-40 bg-black/40 backdrop-blur-sm"
            aria-hidden
          />
          <motion.aside
            key="report-drawer"
            role="dialog"
            aria-modal="true"
            aria-label={`Daily report ${date}`}
            initial={{ x: "100%" }}
            animate={{ x: 0 }}
            exit={{ x: "100%" }}
            transition={{ type: "tween", ease: [0.32, 0.72, 0, 1], duration: 0.25 }}
            className="fixed top-0 right-0 bottom-0 z-50 w-full sm:w-[640px] lg:w-[920px] xl:w-[1100px] bg-background border-l border-border shadow-xl flex flex-col"
          >
            <header className="flex items-center justify-between gap-3 px-5 py-3 border-b border-border bg-card/40 shrink-0">
              <div className="min-w-0">
                <div className="flex items-center gap-2">
                  <BarChart3 className="w-4 h-4 text-primary" />
                  <h2 className="text-sm font-semibold tracking-tight text-foreground">
                    Daily transparency report
                  </h2>
                  <ScopeBadge scope="system" />
                </div>
                <p className="text-[11px] text-muted-foreground mt-0.5 truncate">
                  {date} · summary, every closed trade with full decision lineage, and blocked attempts
                </p>
              </div>
              <button
                onClick={onClose}
                className="p-2 rounded-md text-muted-foreground hover:text-foreground hover:bg-accent transition-colors"
                aria-label="Close"
              >
                <X className="w-4 h-4" />
              </button>
            </header>
            <div className="flex-1 min-h-0 overflow-y-auto p-5">
              <DailyReportDetail date={date} />
            </div>
          </motion.aside>
        </>
      )}
    </AnimatePresence>
  );
}

function PerformanceReviewDrawer({
  open, onClose, profileId, profileName,
}: {
  open: boolean;
  onClose: () => void;
  profileId: string | null;
  profileName: string | null;
}) {
  // Lock body scroll while open
  useEffect(() => {
    if (!open) return;
    const prev = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => { document.body.style.overflow = prev; };
  }, [open]);

  // Close on Escape
  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => { if (e.key === "Escape") onClose(); };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, onClose]);

  return (
    <AnimatePresence>
      {open && (
        <>
          <motion.div
            key="backdrop"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.15 }}
            onClick={onClose}
            className="fixed inset-0 z-40 bg-black/40 backdrop-blur-sm"
            aria-hidden
          />
          <motion.aside
            key="drawer"
            role="dialog"
            aria-modal="true"
            aria-label="Performance review"
            initial={{ x: "100%" }}
            animate={{ x: 0 }}
            exit={{ x: "100%" }}
            transition={{ type: "tween", ease: [0.32, 0.72, 0, 1], duration: 0.25 }}
            className="fixed top-0 right-0 bottom-0 z-50 w-full sm:w-[640px] lg:w-[820px] xl:w-[960px] bg-background border-l border-border shadow-xl flex flex-col"
          >
            <header className="flex items-center justify-between gap-3 px-5 py-3 border-b border-border bg-card/40 shrink-0">
              <div className="min-w-0">
                <div className="flex items-center gap-2">
                  <BarChart3 className="w-4 h-4 text-primary" />
                  <h2 className="text-sm font-semibold tracking-tight text-foreground">
                    Performance review
                  </h2>
                  <ScopeBadge scope="profile" />
                </div>
                <p className="text-[11px] text-muted-foreground mt-0.5 truncate">
                  Gate-block analytics, agent weights, and trade attribution
                  {profileName ? ` · ${profileName}` : ""}
                </p>
              </div>
              <button
                onClick={onClose}
                className="p-2 rounded-md text-muted-foreground hover:text-foreground hover:bg-accent transition-colors"
                aria-label="Close"
              >
                <X className="w-4 h-4" />
              </button>
            </header>
            <div className="flex-1 min-h-0 overflow-y-auto p-5">
              <PerformanceContent profileId={profileId} />
            </div>
          </motion.aside>
        </>
      )}
    </AnimatePresence>
  );
}
