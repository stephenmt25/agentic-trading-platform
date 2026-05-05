"use client";

import React, { useState, useEffect, useCallback, useRef } from 'react';
import {
    AlertTriangle, CheckCircle2, Loader2, ChevronDown, ChevronUp,
    ShieldAlert, ShieldCheck, Power, RefreshCw, TrendingUp, TrendingDown,
    Clock,
} from 'lucide-react';
import { api, type PaperTradingStatus, type KillSwitchStatus, type TradingModeStatus } from "@/lib/api/client";
import { motion } from "framer-motion";
import { pageEnter, staggerContainer, fadeUpChild } from "@/lib/motion";
import { toast } from "sonner";
import { AgentStatusPanel } from "@/components/agents/AgentStatusPanel";
import { RiskMonitorCard } from "@/components/risk/RiskMonitorCard";
import { DecisionFeed } from "@/components/decisions/DecisionFeed";

const POLL_INTERVAL = 30_000; // 30 seconds

export default function PaperTradingDashboard() {
    const [status, setStatus] = useState<PaperTradingStatus | null>(null);
    const [isLoading, setIsLoading] = useState(true);
    const [isRefreshing, setIsRefreshing] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const [expandedReportId, setExpandedReportId] = useState<number | null>(null);

    const [killSwitch, setKillSwitch] = useState<KillSwitchStatus | null>(null);
    const [tradingMode, setTradingMode] = useState<TradingModeStatus | null>(null);
    const [killSwitchToggling, setKillSwitchToggling] = useState(false);
    const [killSwitchLogOpen, setKillSwitchLogOpen] = useState(false);

    // Today's UTC date as YYYY-MM-DD — default for the manual report picker.
    // Using UTC because the daily-report daemon and the table both key off
    // UTC dates; a local-tz default would surprise the operator near midnight.
    const todayUtcIso = new Date().toISOString().slice(0, 10);
    const [reportDate, setReportDate] = useState<string>(todayUtcIso);
    const [generatingReport, setGeneratingReport] = useState(false);

    const [lastUpdated, setLastUpdated] = useState<Date | null>(null);
    const isInitialLoad = useRef(true);

    const loadStatus = useCallback(async () => {
        // Only show full skeleton on initial load, not on refreshes
        if (isInitialLoad.current) {
            setIsLoading(true);
        } else {
            setIsRefreshing(true);
        }

        try {
            const [ptStatus, ksStatus, tmStatus] = await Promise.allSettled([
                api.paperTrading.status(),
                api.commands.killSwitchStatus(),
                api.paperTrading.mode(),
            ]);

            if (ptStatus.status === "fulfilled") {
                setStatus(ptStatus.value);
            }
            if (ksStatus.status === "fulfilled") {
                setKillSwitch(ksStatus.value);
            }
            if (tmStatus.status === "fulfilled") {
                setTradingMode(tmStatus.value);
            }

            if (ptStatus.status === "rejected") {
                const msg = ptStatus.reason?.message || "Failed to load paper trading data";
                if (!msg.includes("Unauthorized")) {
                    setError(msg);
                } else {
                    setError(null);
                }
                setStatus(null);
            } else {
                setError(null);
            }

            setLastUpdated(new Date());
        } catch (e: any) {
            setError(e.message || "Failed to load data");
        } finally {
            setIsLoading(false);
            setIsRefreshing(false);
            isInitialLoad.current = false;
        }
    }, []);

    useEffect(() => {
        loadStatus();
        const interval = setInterval(loadStatus, POLL_INTERVAL);
        return () => clearInterval(interval);
    }, [loadStatus]);

    const handleGenerateReport = async () => {
        if (!reportDate) {
            toast.error("Pick a date first");
            return;
        }
        setGeneratingReport(true);
        try {
            const result = await api.paperTrading.generateReport(reportDate);
            if (result.wrote) {
                toast.success(`Report regenerated for ${result.report_date}`);
            } else if (result.report) {
                toast.info(`No new activity on ${result.report_date} — kept existing report`);
            } else {
                toast.info(`No trades or snapshots on ${result.report_date} — nothing to report`);
            }
            // Refresh the dashboard so the new / updated row appears in the list.
            await loadStatus();
        } catch (e: any) {
            toast.error(`Failed to generate report: ${e.message ?? e}`);
        } finally {
            setGeneratingReport(false);
        }
    };

    const handleKillSwitchToggle = async () => {
        if (!killSwitch) return;
        const newState = !killSwitch.active;
        const action = newState ? "activate" : "deactivate";

        setKillSwitchToggling(true);
        try {
            await api.commands.killSwitchToggle(newState, `Manual ${action} from dashboard`);
            const updated = await api.commands.killSwitchStatus();
            setKillSwitch(updated);
            toast.success(`Kill switch ${newState ? "activated" : "deactivated"}`);
        } catch (e: any) {
            toast.error(`Failed to ${action} kill switch: ${e.message}`);
        } finally {
            setKillSwitchToggling(false);
        }
    };

    const daysElapsed = status?.days_elapsed ?? 0;
    const targetDays = status?.target_days ?? 30;
    const metrics = status?.metrics;
    const dailyReports = status?.daily_reports ?? [];

    const netPnl = metrics?.total_net_pnl ?? 0;
    const grossPnl = metrics?.total_gross_pnl ?? 0;
    const isPositive = netPnl > 0;
    const isZero = netPnl === 0;
    const pnlColor = isZero ? "text-muted-foreground" : isPositive ? "text-emerald-500" : "text-red-500";

    const toggleReport = (id: number) => {
        setExpandedReportId(expandedReportId === id ? null : id);
    };

    return (
        <motion.div variants={pageEnter} initial="initial" animate="animate" className="relative h-full flex flex-col gap-5 max-w-[1600px] mx-auto w-full">

            {/* ─── [1] Compact Status Bar ─── */}
            <div className="border border-border border-t-2 border-t-amber-500 p-3 md:p-4 rounded-md shrink-0">
                <div className="flex flex-wrap items-center gap-3 md:gap-4 justify-between">
                    {/* Left: Mode badge + title */}
                    <div className="flex items-center gap-2.5">
                        {tradingMode ? (
                            <span className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-mono font-semibold ${
                                tradingMode.effective_mode === "PAPER"
                                    ? "bg-amber-500/10 text-amber-500 border border-amber-500/30"
                                    : tradingMode.effective_mode === "TESTNET"
                                        ? "bg-blue-500/10 text-blue-500 border border-blue-500/30"
                                        : "bg-red-500/10 text-red-500 border border-red-500/30"
                            }`}>
                                {tradingMode.effective_mode}
                            </span>
                        ) : (
                            <span className="w-16 h-5 bg-accent animate-pulse rounded" />
                        )}
                        <h1 className="text-sm font-semibold text-foreground">Paper Trading</h1>
                        {tradingMode && (
                            <span className={`inline-flex items-center gap-1 text-xs font-mono ${tradingMode.trading_enabled ? "text-emerald-500" : "text-red-500"}`}>
                                <span className={`w-1.5 h-1.5 rounded-full ${tradingMode.trading_enabled ? "bg-emerald-500 animate-pulse" : "bg-red-500"}`} />
                                {tradingMode.trading_enabled ? "ENABLED" : "DISABLED"}
                            </span>
                        )}
                    </div>

                    {/* Center: Kill switch */}
                    <div className="flex items-center gap-2">
                        {killSwitch?.active ? (
                            <ShieldAlert size={14} className="text-red-500" />
                        ) : (
                            <ShieldCheck size={14} className="text-emerald-500/60" />
                        )}
                        <span className={`text-xs font-mono ${killSwitch?.active ? "text-red-500" : "text-muted-foreground"}`}>
                            {killSwitch?.active ? "HALTED" : "Operational"}
                        </span>
                        <button
                            onClick={handleKillSwitchToggle}
                            disabled={killSwitchToggling || !killSwitch}
                            className={`inline-flex items-center gap-1 px-2.5 py-1 rounded text-xs font-semibold transition-colors ${
                                killSwitch?.active
                                    ? "bg-emerald-600 hover:bg-emerald-700 text-white"
                                    : "bg-red-600 hover:bg-red-700 text-white"
                            } disabled:opacity-50 disabled:cursor-not-allowed`}
                        >
                            {killSwitchToggling ? <Loader2 size={11} className="animate-spin" /> : <Power size={11} />}
                            {killSwitch?.active ? "Resume" : "Stop"}
                        </button>
                        {killSwitch?.recent_log && killSwitch.recent_log.length > 0 && (
                            <button
                                onClick={() => setKillSwitchLogOpen(!killSwitchLogOpen)}
                                className="p-1 rounded hover:bg-accent transition-colors"
                                aria-label="Toggle kill switch log"
                            >
                                {killSwitchLogOpen ? <ChevronUp size={12} className="text-muted-foreground" /> : <ChevronDown size={12} className="text-muted-foreground" />}
                            </button>
                        )}
                    </div>

                    {/* Right: Refresh + timestamp */}
                    <div className="flex items-center gap-2">
                        {lastUpdated && (
                            <span className="text-xs text-muted-foreground font-mono tabular-nums hidden sm:inline">
                                {lastUpdated.toLocaleTimeString()}
                            </span>
                        )}
                        <button
                            onClick={loadStatus}
                            disabled={isRefreshing}
                            className="p-1.5 rounded-md hover:bg-accent transition-colors"
                            aria-label="Refresh data"
                        >
                            <RefreshCw className={`w-3.5 h-3.5 text-muted-foreground ${isRefreshing ? 'animate-spin' : ''}`} />
                        </button>
                    </div>
                </div>

                {/* Kill Switch Activity Log (expandable) */}
                {killSwitchLogOpen && killSwitch?.recent_log && killSwitch.recent_log.length > 0 && (
                    <div className="mt-3 pt-3 border-t border-border space-y-1.5 animate-in fade-in slide-in-from-top-1 duration-150">
                        {killSwitch.recent_log.slice(0, 5).map((entry, i) => (
                            <div key={i} className="flex items-center gap-2 text-xs font-mono">
                                <Clock size={10} className="text-muted-foreground shrink-0" />
                                <span className="text-muted-foreground tabular-nums">{new Date(entry.timestamp).toLocaleString()}</span>
                                <span className={entry.action === "activated" ? "text-red-500" : "text-emerald-500"}>{entry.action}</span>
                                {entry.reason && <span className="text-muted-foreground/70 truncate">{entry.reason}</span>}
                            </div>
                        ))}
                    </div>
                )}
            </div>

            {isLoading ? (
                <div className="flex-1 flex flex-col gap-4">
                    <div className="h-24 bg-accent animate-pulse rounded-md" />
                    <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                        <div className="h-20 bg-accent animate-pulse rounded-md" />
                        <div className="h-20 bg-accent animate-pulse rounded-md" />
                        <div className="h-20 bg-accent animate-pulse rounded-md" />
                        <div className="h-20 bg-accent animate-pulse rounded-md" />
                    </div>
                    <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
                        <div className="h-40 bg-accent animate-pulse rounded-md" />
                        <div className="h-40 bg-accent animate-pulse rounded-md" />
                    </div>
                </div>
            ) : error ? (
                <div className="flex-1 flex flex-col items-center justify-center gap-3 text-center">
                    <AlertTriangle className="w-5 h-5 text-amber-500/80" />
                    <div className="font-mono text-sm text-amber-500/80">BACKEND OFFLINE</div>
                    <p className="text-xs text-muted-foreground max-w-sm">
                        Could not reach the API gateway. Ensure the backend services are running and your tunnel is active.
                    </p>
                </div>
            ) : (
                <motion.div variants={staggerContainer} initial="initial" animate="animate" className="flex-1 flex flex-col gap-5 overflow-y-auto">

                    {/* ─── [2] P&L Hero ─── */}
                    <motion.section variants={fadeUpChild} className="border border-border p-4 md:p-6 rounded-md">
                        <h2 className="uppercase text-xs font-semibold text-muted-foreground tracking-wider mb-4">
                            Paper Trading Performance
                        </h2>
                        <div className="flex items-baseline gap-3 mb-5">
                            <span className={`text-2xl md:text-4xl font-mono tabular-nums font-semibold tracking-tight ${pnlColor}`}>
                                {isPositive ? "+" : ""}{netPnl === 0 ? "$0.00" : `$${netPnl.toFixed(2)}`}
                            </span>
                            <span className="text-muted-foreground font-mono text-sm">net P&L</span>
                            {netPnl !== 0 && (
                                isPositive
                                    ? <TrendingUp size={18} className="text-emerald-500" />
                                    : <TrendingDown size={18} className="text-red-500" />
                            )}
                        </div>
                        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 pt-4 border-t border-border">
                            <div className="flex flex-col space-y-1">
                                <span className="text-xs uppercase text-muted-foreground font-medium tracking-wider">Gross P&L</span>
                                <span className={`text-sm font-mono tabular-nums ${grossPnl >= 0 ? "text-foreground" : "text-red-500"}`}>
                                    {grossPnl >= 0 ? "" : ""}{`$${grossPnl.toFixed(2)}`}
                                </span>
                            </div>
                            <div className="flex flex-col space-y-1">
                                <span className="text-xs uppercase text-muted-foreground font-medium tracking-wider">Total Trades</span>
                                <span className="text-sm font-mono tabular-nums text-foreground">
                                    {metrics?.total_trades ?? 0}
                                </span>
                            </div>
                            <div className="flex flex-col space-y-1">
                                <span className="text-xs uppercase text-muted-foreground font-medium tracking-wider">Win Rate</span>
                                <span className={`text-sm font-mono tabular-nums ${(metrics?.avg_win_rate ?? 0) > 50 ? "text-emerald-500" : "text-foreground"}`}>
                                    {metrics?.avg_win_rate ?? 0}%
                                </span>
                            </div>
                            <div className="flex flex-col space-y-1">
                                <span className="text-xs uppercase text-muted-foreground font-medium tracking-wider">Max Drawdown</span>
                                <span className="text-sm font-mono tabular-nums text-amber-500">
                                    {((metrics?.max_drawdown ?? 0) * 100).toFixed(1)}%
                                </span>
                            </div>
                        </div>
                    </motion.section>

                    {/* ─── [3] Progress + Reports ─── */}
                    <div className="grid grid-cols-1 lg:grid-cols-3 gap-5">

                        {/* Progress Tracker */}
                        <motion.section variants={fadeUpChild} className="col-span-1 lg:col-span-2 flex flex-col border border-border p-4 md:p-6 rounded-md">
                            <h2 className="uppercase text-xs font-semibold text-muted-foreground tracking-wider mb-4">
                                30-Day Safety Period
                            </h2>
                            <div className="flex items-center gap-4 mb-5">
                                <div className="flex-1 bg-accent rounded-full h-2.5 overflow-hidden">
                                    <div
                                        className="bg-amber-500 h-full transition-[width] duration-1000 ease-out rounded-full"
                                        style={{ width: `${Math.min((daysElapsed / targetDays) * 100, 100)}%` }}
                                    />
                                </div>
                                <span className="font-mono tabular-nums text-sm font-medium text-foreground whitespace-nowrap">
                                    {daysElapsed} / {targetDays} days
                                </span>
                            </div>

                            <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                                <MetricCard
                                    label="Trades"
                                    value={metrics ? String(metrics.total_trades) : "0"}
                                    subtext="Total Executed"
                                    status={metrics && metrics.total_trades > 0 ? "PASS" : "EVAL"}
                                />
                                <MetricCard
                                    label="Win Rate"
                                    value={metrics ? `${metrics.avg_win_rate}%` : "N/A"}
                                    subtext="Avg Win Rate"
                                    status={metrics && metrics.avg_win_rate > 50 ? "PASS" : "EVAL"}
                                />
                                <MetricCard
                                    label="Drawdown"
                                    value={metrics ? `${(metrics.max_drawdown * 100).toFixed(1)}%` : "N/A"}
                                    subtext="Max Drawdown"
                                    status={metrics && metrics.max_drawdown < 0.1 ? "PASS" : "EVAL"}
                                />
                                <MetricCard
                                    label="Sharpe"
                                    value={metrics ? String(metrics.avg_sharpe) : "N/A"}
                                    subtext="Avg Sharpe Ratio"
                                    status={metrics && metrics.avg_sharpe > 1 ? "PASS" : "EVAL"}
                                />
                            </div>
                        </motion.section>

                        {/* Sparkline + Daily Reports */}
                        <motion.section variants={fadeUpChild} className="flex flex-col border border-border p-4 md:p-6 rounded-md overflow-hidden">
                            <div className="flex items-center justify-between gap-3 mb-3 flex-wrap">
                                <h2 className="uppercase text-xs font-semibold text-muted-foreground tracking-wider">
                                    Daily P&L
                                </h2>
                                {/* Manual report generator — same code path as the
                                    daily-report daemon (libs/reports/daily.py).
                                    Idempotent server-side, so re-running for an
                                    existing date overwrites the row. */}
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
                            </div>

                            {/* Sparkline */}
                            {dailyReports.length > 1 && (
                                <div className="mb-3">
                                    <PnlSparkline data={dailyReports.map(r => r.net_pnl).reverse()} />
                                </div>
                            )}

                            {/* Reports list */}
                            <div className="flex-1 overflow-y-auto pr-1 min-h-0">
                                <div className="space-y-1.5 font-mono text-xs">
                                    {dailyReports.length === 0 ? (
                                        <div className="p-3 border border-border rounded-md flex justify-between items-center opacity-50">
                                            <span className="text-muted-foreground">Day 0</span>
                                            <span className="text-muted-foreground">Awaiting first report...</span>
                                        </div>
                                    ) : (
                                        dailyReports.map((report) => (
                                            <div key={report.id}>
                                                <button
                                                    onClick={() => toggleReport(report.id)}
                                                    className="w-full p-2.5 border border-border rounded-md flex justify-between items-center hover:bg-accent transition-colors text-left min-h-[40px]"
                                                >
                                                    <div className="flex flex-col gap-0.5">
                                                        <span className="text-foreground font-medium">{report.report_date}</span>
                                                        <span className="text-xs text-muted-foreground tabular-nums">
                                                            {report.total_trades} trades | {report.win_rate}% win |{" "}
                                                            <span className={report.net_pnl >= 0 ? "text-emerald-500" : "text-red-500"}>
                                                                ${report.net_pnl.toFixed(2)}
                                                            </span>
                                                        </span>
                                                    </div>
                                                    {expandedReportId === report.id
                                                        ? <ChevronUp className="w-3 h-3 text-muted-foreground shrink-0" />
                                                        : <ChevronDown className="w-3 h-3 text-muted-foreground shrink-0" />
                                                    }
                                                </button>

                                                {expandedReportId === report.id && (
                                                    <div className="mt-1 p-2.5 border border-border rounded-md animate-in fade-in slide-in-from-top-1 duration-150">
                                                        <div className="grid grid-cols-2 gap-2">
                                                            <div className="p-1.5">
                                                                <div className="text-xs text-muted-foreground uppercase tracking-wider">Trades</div>
                                                                <div className="text-sm font-medium tabular-nums text-foreground">{report.total_trades}</div>
                                                            </div>
                                                            <div className="p-1.5">
                                                                <div className="text-xs text-muted-foreground uppercase tracking-wider">Win Rate</div>
                                                                <div className="text-sm font-medium tabular-nums text-emerald-500">{report.win_rate}%</div>
                                                            </div>
                                                            <div className="p-1.5">
                                                                <div className="text-xs text-muted-foreground uppercase tracking-wider">Gross</div>
                                                                <div className={`text-sm font-medium tabular-nums ${report.gross_pnl >= 0 ? 'text-emerald-500' : 'text-red-500'}`}>
                                                                    ${report.gross_pnl.toFixed(2)}
                                                                </div>
                                                            </div>
                                                            <div className="p-1.5">
                                                                <div className="text-xs text-muted-foreground uppercase tracking-wider">Net</div>
                                                                <div className={`text-sm font-medium tabular-nums ${report.net_pnl >= 0 ? 'text-emerald-500' : 'text-red-500'}`}>
                                                                    ${report.net_pnl.toFixed(2)}
                                                                </div>
                                                            </div>
                                                            <div className="p-1.5">
                                                                <div className="text-xs text-muted-foreground uppercase tracking-wider">Drawdown</div>
                                                                <div className="text-sm font-medium tabular-nums text-amber-500">{(report.max_drawdown * 100).toFixed(1)}%</div>
                                                            </div>
                                                            <div className="p-1.5">
                                                                <div className="text-xs text-muted-foreground uppercase tracking-wider">Sharpe</div>
                                                                <div className="text-sm font-medium tabular-nums text-foreground">{report.sharpe_ratio.toFixed(2)}</div>
                                                            </div>
                                                        </div>
                                                    </div>
                                                )}
                                            </div>
                                        ))
                                    )}
                                </div>
                            </div>
                        </motion.section>
                    </div>

                    {/* ─── [3.5] Decision Trace ─── */}
                    <motion.section variants={fadeUpChild} className="border border-border p-4 md:p-6 rounded-md">
                        <DecisionFeed />
                    </motion.section>

                    {/* ─── [4] Agent Scores + Risk Monitor ─── */}
                    <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
                        <motion.div variants={fadeUpChild} className="border border-border p-4 md:p-6 rounded-md">
                            <AgentStatusPanel />
                        </motion.div>
                        <motion.div variants={fadeUpChild} className="border border-border p-4 md:p-6 rounded-md">
                            <RiskMonitorCard />
                        </motion.div>
                    </div>
                </motion.div>
            )}
        </motion.div>
    );
}

/* ─── Sub-components ─── */

const MetricCard = ({ label, value, subtext, status }: { label: string; value: string; subtext: string; status: string }) => (
    <div className="p-3 border border-border rounded-md">
        <div className="flex items-center justify-between mb-1.5">
            <span className="text-xs text-muted-foreground uppercase font-medium tracking-wider">{label}</span>
            {status === 'PASS' && <CheckCircle2 size={13} className="text-emerald-500/60" />}
        </div>
        <div className="text-xl font-semibold font-mono tabular-nums text-foreground mb-0.5">{value}</div>
        <div className="text-xs text-muted-foreground">{subtext}</div>
    </div>
);

const PnlSparkline = ({ data }: { data: number[] }) => {
    if (data.length < 2) return null;

    const width = 240;
    const height = 48;
    const padding = 2;

    const min = Math.min(...data, 0);
    const max = Math.max(...data, 0);
    const range = max - min || 1;

    const points = data.map((v, i) => {
        const x = padding + (i / (data.length - 1)) * (width - padding * 2);
        const y = height - padding - ((v - min) / range) * (height - padding * 2);
        return `${x},${y}`;
    }).join(" ");

    // Zero baseline y position
    const zeroY = height - padding - ((0 - min) / range) * (height - padding * 2);
    const lastValue = data[data.length - 1];
    const lineColor = lastValue >= 0 ? "#22c55e" : "#ef4444"; // emerald-500 / red-500

    return (
        <svg viewBox={`0 0 ${width} ${height}`} className="w-full h-12" preserveAspectRatio="none">
            {/* Zero baseline */}
            <line
                x1={padding} y1={zeroY} x2={width - padding} y2={zeroY}
                stroke="currentColor" strokeWidth="0.5" strokeDasharray="3,3"
                className="text-border"
            />
            {/* P&L line */}
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
};
