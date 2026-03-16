"use client";

import React, { useState, useEffect } from 'react';
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { AlertTriangle, FileText, CheckCircle2, Loader2, ChevronDown, ChevronUp } from 'lucide-react';
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
            <div className="bg-amber-950/30 border border-amber-500/50 p-6 rounded-xl flex items-start gap-4 shadow-[0_0_30px_rgba(245,158,11,0.1)] relative overflow-hidden shrink-0">
                <div className="absolute top-0 w-full h-1 bg-gradient-to-r from-amber-500 to-amber-600 left-0" />
                <AlertTriangle className="text-amber-500 shrink-0 mt-1" size={28} />
                <div className="flex flex-col">
                    <h1 className="text-2xl font-black text-amber-500 uppercase tracking-widest mb-2">
                        MANDATORY PAPER TRADING MODE ACTIVE
                    </h1>
                    <p className="text-sm text-slate-300 font-mono tracking-tight leading-relaxed">
                        The system is executing logical workflows against <strong className="text-white">LIVE</strong> market data and routing directly to <strong className="text-white">TESTNET</strong> order-books. No real capital is exposed. This mode must run uninterrupted for thirty days to satisfy core safety policies.
                    </p>
                </div>
            </div>

            {isLoading ? (
                <div className="flex-1 flex items-center justify-center">
                    <Loader2 className="w-8 h-8 animate-spin text-muted-foreground" />
                </div>
            ) : error ? (
                <div className="flex-1 flex flex-col items-center justify-center gap-3 text-center">
                    <div className="font-mono text-sm text-amber-500/80">BACKEND OFFLINE</div>
                    <p className="text-xs text-muted-foreground max-w-sm">
                        Could not reach the API gateway. Start the backend on port 8000 to see live paper trading data.
                    </p>
                </div>
            ) : (
                <div className="flex-1 grid grid-cols-1 lg:grid-cols-3 gap-8 mt-4 overflow-hidden min-h-[500px]">

                    {/* Progress Tracker */}
                    <Card className="border-border bg-card shadow-xl col-span-2 flex flex-col relative overflow-hidden group">
                        <CardHeader className="pb-2 shrink-0">
                            <CardTitle className="uppercase text-xs font-bold text-muted-foreground tracking-wider">
                                Phase 1 Exit Tracking
                            </CardTitle>
                        </CardHeader>
                        <CardContent className="flex-1 flex flex-col justify-between mt-4 overflow-y-auto">
                            <div className="flex items-center gap-4 mb-8">
                                <div className="flex-1 bg-slate-900 rounded-full h-4 overflow-hidden outline outline-1 outline-white/5">
                                    <div
                                        className="bg-gradient-to-r from-amber-500 to-primary h-full transition-all duration-1000 ease-out shadow-[0_0_10px_rgba(245,158,11,0.5)]"
                                        style={{ width: `${Math.min((daysElapsed / targetDays) * 100, 100)}%` }}
                                    />
                                </div>
                                <span className="font-mono text-sm font-bold text-slate-200 w-24">
                                    {daysElapsed} / {targetDays} DAYS
                                </span>
                            </div>

                            <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mt-auto">
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
                        </CardContent>
                    </Card>

                    {/* Sidebar Log Tracker */}
                    <Card className="border-border bg-card shadow-xl flex flex-col overflow-hidden">
                        <CardHeader className="pb-2 shrink-0">
                            <div className="flex justify-between items-center w-full">
                                <CardTitle className="uppercase text-xs font-bold text-muted-foreground tracking-wider">
                                    Daily System Dumps
                                </CardTitle>
                                <FileText size={14} className="text-muted-foreground" />
                            </div>
                        </CardHeader>

                        <CardContent className="flex-1 mt-4 overflow-y-auto pr-2">
                            <div className="space-y-3 font-mono text-xs">
                                {dailyReports.length === 0 ? (
                                    <div className="p-4 border border-border rounded-lg bg-black/10 flex justify-between items-center opacity-50">
                                        <span className="text-slate-400">Day 0</span>
                                        <span className="text-slate-500">Awaiting first report...</span>
                                    </div>
                                ) : (
                                    dailyReports.map((report) => (
                                        <div key={report.id}>
                                            <button
                                                onClick={() => toggleReport(report.id)}
                                                className="w-full p-4 border border-border rounded-lg bg-black/20 flex justify-between items-center hover:bg-black/40 transition-colors text-left"
                                            >
                                                <div className="flex flex-col gap-1">
                                                    <span className="text-slate-300 font-bold">{report.report_date}</span>
                                                    <span className="text-[10px] text-slate-500">
                                                        {report.total_trades} trades • {report.win_rate}% win • PnL ${report.net_pnl}
                                                    </span>
                                                </div>
                                                <div className="flex items-center gap-2">
                                                    <Badge variant="outline" className="text-emerald-500 border-emerald-500/30 bg-emerald-500/10 text-[10px]">
                                                        report
                                                    </Badge>
                                                    {expandedReportId === report.id ? (
                                                        <ChevronUp className="w-3 h-3 text-slate-500" />
                                                    ) : (
                                                        <ChevronDown className="w-3 h-3 text-slate-500" />
                                                    )}
                                                </div>
                                            </button>

                                            {/* Expanded Detail Panel */}
                                            {expandedReportId === report.id && (
                                                <div className="mt-1 p-4 border border-slate-800 rounded-lg bg-slate-950/80 space-y-3 animate-in fade-in slide-in-from-top-1 duration-150">
                                                    <div className="grid grid-cols-2 gap-3">
                                                        <div className="bg-black/30 rounded-md p-2.5">
                                                            <div className="text-[9px] text-slate-600 uppercase tracking-wider">Total Trades</div>
                                                            <div className="text-sm font-bold text-slate-200">{report.total_trades}</div>
                                                        </div>
                                                        <div className="bg-black/30 rounded-md p-2.5">
                                                            <div className="text-[9px] text-slate-600 uppercase tracking-wider">Win Rate</div>
                                                            <div className="text-sm font-bold text-emerald-400">{report.win_rate}%</div>
                                                        </div>
                                                        <div className="bg-black/30 rounded-md p-2.5">
                                                            <div className="text-[9px] text-slate-600 uppercase tracking-wider">Gross PnL</div>
                                                            <div className={`text-sm font-bold ${report.gross_pnl >= 0 ? 'text-emerald-400' : 'text-red-400'}`}>
                                                                ${report.gross_pnl.toFixed(2)}
                                                            </div>
                                                        </div>
                                                        <div className="bg-black/30 rounded-md p-2.5">
                                                            <div className="text-[9px] text-slate-600 uppercase tracking-wider">Net PnL</div>
                                                            <div className={`text-sm font-bold ${report.net_pnl >= 0 ? 'text-emerald-400' : 'text-red-400'}`}>
                                                                ${report.net_pnl.toFixed(2)}
                                                            </div>
                                                        </div>
                                                        <div className="bg-black/30 rounded-md p-2.5">
                                                            <div className="text-[9px] text-slate-600 uppercase tracking-wider">Max Drawdown</div>
                                                            <div className="text-sm font-bold text-amber-400">{(report.max_drawdown * 100).toFixed(1)}%</div>
                                                        </div>
                                                        <div className="bg-black/30 rounded-md p-2.5">
                                                            <div className="text-[9px] text-slate-600 uppercase tracking-wider">Sharpe Ratio</div>
                                                            <div className="text-sm font-bold text-slate-200">{report.sharpe_ratio.toFixed(2)}</div>
                                                        </div>
                                                    </div>
                                                </div>
                                            )}
                                        </div>
                                    ))
                                )}
                            </div>
                        </CardContent>
                    </Card>
                </div>
            )}
        </div>
    );
}

const MetricCard = ({ label, value, subtext, status }: { label: string; value: string; subtext: string; status: string }) => (
    <div className="bg-black/20 p-5 border border-border rounded-lg relative overflow-hidden transition-all hover:border-slate-700">
        <div className={`absolute top-0 right-0 w-12 h-12 -mr-6 -mt-6 rounded-full ${status === 'PASS' ? 'bg-emerald-500/10' : 'bg-amber-500/10'}`} />
        {status === 'PASS' && <CheckCircle2 size={14} className="absolute top-2 right-2 text-emerald-500/50" />}
        <div className="text-[10px] text-muted-foreground uppercase font-bold tracking-wider mb-2">{label}</div>
        <div className="text-2xl font-bold font-mono text-slate-200 mb-1">{value}</div>
        <div className="text-[9px] text-slate-500 uppercase tracking-widest">{subtext}</div>
    </div>
);
