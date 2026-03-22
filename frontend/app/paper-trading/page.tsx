"use client";

import React, { useState, useEffect } from 'react';
import { AlertTriangle, CheckCircle2, Loader2, ChevronDown, ChevronUp } from 'lucide-react';
import { api, type PaperTradingStatus } from "@/lib/api/client";

export default function PaperTradingDashboard() {
    const [status, setStatus] = useState<PaperTradingStatus | null>(null);
    const [isLoading, setIsLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);
    const [expandedReportId, setExpandedReportId] = useState<number | null>(null);

    useEffect(() => {
        loadStatus();
    }, []);

    const loadStatus = async () => {
        setIsLoading(true);
        try {
            const data = await api.paperTrading.status();
            setStatus(data);
            setError(null);
        } catch (e: any) {
            const msg = e.message || "Failed to load paper trading data";
            if (!msg.includes("Unauthorized")) {
                console.error("Failed to load paper trading status:", e);
                setError(msg);
            } else {
                setError(null);
            }
            setStatus(null);
        } finally {
            setIsLoading(false);
        }
    };

    const daysElapsed = status?.days_elapsed ?? 0;
    const targetDays = status?.target_days ?? 30;
    const metrics = status?.metrics;
    const dailyReports = status?.daily_reports ?? [];

    const toggleReport = (id: number) => {
        setExpandedReportId(expandedReportId === id ? null : id);
    };

    return (
        <div className="relative h-full flex flex-col gap-6 max-w-[1600px] mx-auto w-full">
            {/* Header with Mandatory Disclaimer */}
            <div className="border border-amber-500/30 p-4 md:p-6 rounded-md flex items-start gap-3 shrink-0">
                <AlertTriangle className="text-amber-500 shrink-0 mt-0.5" size={20} />
                <div className="flex flex-col">
                    <h1 className="text-lg font-semibold text-amber-500 uppercase tracking-wider mb-1">
                        Paper Trading Mode Active
                    </h1>
                    <p className="text-sm text-muted-foreground leading-relaxed">
                        The system is executing against <strong className="text-foreground">live</strong> market data routed to <strong className="text-foreground">testnet</strong> order-books. No real capital is exposed. This mode must run for thirty days to satisfy safety policies.
                    </p>
                </div>
            </div>

            {isLoading ? (
                <div className="flex-1 flex flex-col gap-4 mt-4">
                    <div className="h-10 bg-accent animate-pulse rounded-md w-full" />
                    <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                        <div className="h-24 bg-accent animate-pulse rounded-md" />
                        <div className="h-24 bg-accent animate-pulse rounded-md" />
                        <div className="h-24 bg-accent animate-pulse rounded-md" />
                        <div className="h-24 bg-accent animate-pulse rounded-md" />
                    </div>
                </div>
            ) : error ? (
                <div className="flex-1 flex flex-col items-center justify-center gap-3 text-center">
                    <AlertTriangle className="w-5 h-5 text-amber-500/80" />
                    <div className="font-mono text-sm text-amber-500/80">BACKEND OFFLINE</div>
                    <p className="text-xs text-muted-foreground max-w-sm">
                        Could not reach the API gateway. Start the backend on port 8000 to see live paper trading data.
                    </p>
                </div>
            ) : (
                <div className="flex-1 grid grid-cols-1 lg:grid-cols-3 gap-6 mt-4 overflow-hidden min-h-[500px]">

                    {/* Progress Tracker */}
                    <section className="col-span-1 lg:col-span-2 flex flex-col">
                        <h2 className="uppercase text-xs font-semibold text-muted-foreground tracking-wider mb-4">
                            Phase 1 Exit Tracking
                        </h2>
                        <div className="flex-1 flex flex-col justify-between">
                            <div className="flex items-center gap-4 mb-6">
                                <div className="flex-1 bg-accent rounded-full h-2 overflow-hidden">
                                    <div
                                        className="bg-amber-500 h-full transition-[width] duration-1000 ease-out"
                                        style={{ width: `${Math.min((daysElapsed / targetDays) * 100, 100)}%` }}
                                    />
                                </div>
                                <span className="font-mono tabular-nums text-sm font-medium text-foreground w-24">
                                    {daysElapsed} / {targetDays}
                                </span>
                            </div>

                            <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mt-auto">
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
                        </div>
                    </section>

                    {/* Sidebar Log Tracker */}
                    <section className="flex flex-col overflow-hidden border-t border-border pt-4 lg:border-t-0 lg:pt-0 lg:border-l lg:pl-6">
                        <div className="flex justify-between items-center w-full mb-4">
                            <h2 className="uppercase text-xs font-semibold text-muted-foreground tracking-wider">
                                Daily Reports
                            </h2>
                        </div>

                        <div className="flex-1 overflow-y-auto pr-1">
                            <div className="space-y-2 font-mono text-xs">
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
                                                className="w-full p-3 border border-border rounded-md flex justify-between items-center hover:bg-accent transition-colors text-left min-h-[44px]"
                                            >
                                                <div className="flex flex-col gap-0.5">
                                                    <span className="text-foreground font-medium">{report.report_date}</span>
                                                    <span className="text-xs text-muted-foreground tabular-nums">
                                                        {report.total_trades} trades | {report.win_rate}% win | ${report.net_pnl}
                                                    </span>
                                                </div>
                                                <div className="flex items-center gap-2">
                                                    {expandedReportId === report.id ? (
                                                        <ChevronUp className="w-3 h-3 text-muted-foreground" />
                                                    ) : (
                                                        <ChevronDown className="w-3 h-3 text-muted-foreground" />
                                                    )}
                                                </div>
                                            </button>

                                            {/* Expanded Detail Panel */}
                                            {expandedReportId === report.id && (
                                                <div className="mt-1 p-3 border border-border rounded-md space-y-2 animate-in fade-in slide-in-from-top-1 duration-150">
                                                    <div className="grid grid-cols-2 gap-2">
                                                        <div className="p-2">
                                                            <div className="text-xs text-muted-foreground uppercase tracking-wider">Total Trades</div>
                                                            <div className="text-sm font-medium font-mono tabular-nums text-foreground">{report.total_trades}</div>
                                                        </div>
                                                        <div className="p-2">
                                                            <div className="text-xs text-muted-foreground uppercase tracking-wider">Win Rate</div>
                                                            <div className="text-sm font-medium font-mono tabular-nums text-emerald-500">{report.win_rate}%</div>
                                                        </div>
                                                        <div className="p-2">
                                                            <div className="text-xs text-muted-foreground uppercase tracking-wider">Gross PnL</div>
                                                            <div className={`text-sm font-medium font-mono tabular-nums ${report.gross_pnl >= 0 ? 'text-emerald-500' : 'text-red-500'}`}>
                                                                ${report.gross_pnl.toFixed(2)}
                                                            </div>
                                                        </div>
                                                        <div className="p-2">
                                                            <div className="text-xs text-muted-foreground uppercase tracking-wider">Net PnL</div>
                                                            <div className={`text-sm font-medium font-mono tabular-nums ${report.net_pnl >= 0 ? 'text-emerald-500' : 'text-red-500'}`}>
                                                                ${report.net_pnl.toFixed(2)}
                                                            </div>
                                                        </div>
                                                        <div className="p-2">
                                                            <div className="text-xs text-muted-foreground uppercase tracking-wider">Max Drawdown</div>
                                                            <div className="text-sm font-medium font-mono tabular-nums text-amber-500">{(report.max_drawdown * 100).toFixed(1)}%</div>
                                                        </div>
                                                        <div className="p-2">
                                                            <div className="text-xs text-muted-foreground uppercase tracking-wider">Sharpe Ratio</div>
                                                            <div className="text-sm font-medium font-mono tabular-nums text-foreground">{report.sharpe_ratio.toFixed(2)}</div>
                                                        </div>
                                                    </div>
                                                </div>
                                            )}
                                        </div>
                                    ))
                                )}
                            </div>
                        </div>
                    </section>
                </div>
            )}
        </div>
    );
}

const MetricCard = ({ label, value, subtext, status }: { label: string; value: string; subtext: string; status: string }) => (
    <div className="p-4 border border-border rounded-md">
        <div className="flex items-center justify-between mb-2">
            <span className="text-xs text-muted-foreground uppercase font-medium tracking-wider">{label}</span>
            {status === 'PASS' && <CheckCircle2 size={14} className="text-emerald-500/60" />}
        </div>
        <div className="text-2xl font-semibold font-mono tabular-nums text-foreground mb-0.5">{value}</div>
        <div className="text-xs text-muted-foreground">{subtext}</div>
    </div>
);
