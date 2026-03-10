"use client";

import React, { useState } from 'react';
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { AlertCircle, FileText, CheckCircle2, TrendingUp, AlertTriangle } from 'lucide-react';

export default function PaperTradingDashboard() {
    const [daysElapsed] = useState(1);
    const targetDays = 30;

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
                                    style={{ width: `${(daysElapsed / targetDays) * 100}%` }}
                                />
                            </div>
                            <span className="font-mono text-sm font-bold text-slate-200 w-24">
                                {daysElapsed} / {targetDays} DAYS
                            </span>
                        </div>

                        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mt-auto">
                            <MetricCard label="Uptime" value="100%" subtext="No System Crashes" status="PASS" />
                            <MetricCard label="Returns" value="Pending" subtext="Gross PNL Eval" status="EVAL" />
                            <MetricCard label="Drawdown" value="< 10%" subtext="Max Drawdown" status="PASS" />
                            <MetricCard label="Safety Nets" value="1" subtext="Caught Anomalies" status="PASS" />
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
                            <div className="p-4 border border-border rounded-lg bg-black/20 flex justify-between items-center hover:bg-black/40 transition-colors">
                                <span className="text-slate-300 font-bold">Day 1</span>
                                <Badge variant="outline" className="text-emerald-500 border-emerald-500/30 bg-emerald-500/10 hover:bg-emerald-500/20 cursor-pointer">
                                    sys-report.pdf
                                </Badge>
                            </div>
                            <div className="p-4 border border-border rounded-lg bg-black/10 flex justify-between items-center opacity-50">
                                <span className="text-slate-400">Day 0</span>
                                <span className="text-slate-500">Initializing...</span>
                            </div>
                        </div>
                    </CardContent>
                </Card>
            </div>
        </div>
    );
}

const MetricCard = ({ label, value, subtext, status }: any) => (
    <div className="bg-black/20 p-5 border border-border rounded-lg relative overflow-hidden transition-all hover:border-slate-700">
        <div className={`absolute top-0 right-0 w-12 h-12 -mr-6 -mt-6 rounded-full ${status === 'PASS' ? 'bg-emerald-500/10' : 'bg-amber-500/10'}`} />
        {status === 'PASS' && <CheckCircle2 size={14} className="absolute top-2 right-2 text-emerald-500/50" />}
        <div className="text-[10px] text-muted-foreground uppercase font-bold tracking-wider mb-2">{label}</div>
        <div className="text-2xl font-bold font-mono text-slate-200 mb-1">{value}</div>
        <div className="text-[9px] text-slate-500 uppercase tracking-widest">{subtext}</div>
    </div>
);
