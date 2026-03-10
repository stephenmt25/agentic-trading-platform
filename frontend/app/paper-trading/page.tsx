'use client';

import React, { useEffect, useState } from 'react';
import { AlertCircle, FileText, CheckCircle2, TrendingUp, AlertTriangle } from 'lucide-react';

export default function PaperTradingDashboard() {
    const [daysElapsed, setDaysElapsed] = useState(1);
    const targetDays = 30;

    return (
        <div className="relative h-full flex flex-col gap-6 w-full">
            {/* 1. Header with Mandatory Disclaimer */}
            <div className="bg-amber-500/10 border-2 border-amber-500/50 p-4 rounded-xl flex items-start gap-4 shadow-[0_0_30px_rgba(245,158,11,0.2)]">
                <AlertTriangle className="text-amber-500 shrink-0 mt-1" size={24} />
                <div>
                    <h1 className="text-xl font-black text-amber-500 uppercase tracking-widest mb-1">
                        MANDATORY PAPER TRADING MODE ACTIVE
                    </h1>
                    <p className="text-sm text-slate-300 font-mono tracking-tight leading-relaxed">
                        The system is executing logical workflows against <strong>LIVE</strong> market data and routing directly to <strong>TESTNET</strong> order-books. No real capital is exposed. This mode must run uninterrupted for thirty days to satisfy core safety policies.
                    </p>
                </div>
            </div>

            <div className="flex-1 grid grid-cols-1 lg:grid-cols-3 gap-8 mt-4">

                {/* Progress Tracker */}
                <div className="bg-slate-900 border border-slate-700 rounded-xl p-6 shadow-xl col-span-2">
                    <h2 className="uppercase text-xs font-bold text-slate-500 tracking-wider mb-6">Phase 1 Exit Tracking</h2>

                    <div className="flex items-center gap-4 mb-4">
                        <div className="flex-1 bg-slate-800 rounded-full h-4 overflow-hidden shadow-inner">
                            <div
                                className="bg-gradient-to-r from-amber-500 to-indigo-500 h-full transition-all duration-1000 ease-out"
                                style={{ width: `${(daysElapsed / targetDays) * 100}%` }}
                            />
                        </div>
                        <span className="font-mono text-sm font-bold text-slate-300">
                            {daysElapsed} / {targetDays} DAYS
                        </span>
                    </div>

                    <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mt-8">
                        <MetricCard label="Uptime" value="100%" subtext="No System Crashes" status="PASS" />
                        <MetricCard label="Returns" value="Pending" subtext="Gross PNL Eval" status="EVAL" />
                        <MetricCard label="Drawdown" value="< 10%" subtext="Max Drawdown" status="PASS" />
                        <MetricCard label="Safety Nets" value="1" subtext="Caught Anomalies" status="PASS" />
                    </div>
                </div>

                {/* Sidebar Log Tracker */}
                <div className="bg-slate-900 border border-slate-700 rounded-xl p-6 shadow-xl flex flex-col">
                    <h2 className="uppercase text-xs font-bold text-slate-500 tracking-wider flex justify-between">
                        Daily System Dumps
                        <FileText size={14} />
                    </h2>

                    <div className="flex-1 mt-6 space-y-4 overflow-y-auto font-mono text-xs">
                        <div className="p-3 border border-slate-800 rounded bg-slate-950/50 flex justify-between">
                            <span className="text-slate-400">Day 1</span>
                            <span className="text-emerald-500 underline decoration-emerald-500/30 underline-offset-4 decoration-dashed cursor-pointer">
                                sys-report.pdf
                            </span>
                        </div>
                        <div className="p-3 border border-slate-800 rounded bg-slate-950/50 flex justify-between">
                            <span className="text-slate-400">Day 0</span>
                            <span className="text-slate-500 opacity-50 shrink">Initializing...</span>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    );
}

const MetricCard = ({ label, value, subtext, status }: any) => (
    <div className="bg-slate-950/50 p-4 border border-slate-800 rounded relative group overflow-hidden">
        <div className={`absolute top-0 right-0 w-8 h-8 -mr-4 -mt-4 rounded-full ${status === 'PASS' ? 'bg-emerald-500/20' : 'bg-amber-500/20'}`} />
        {status === 'PASS' && <CheckCircle2 size={12} className="absolute top-2 right-2 text-emerald-500" />}
        <div className="text-[10px] text-slate-500 uppercase font-bold tracking-wider mb-2">{label}</div>
        <div className="text-xl font-bold font-mono text-slate-200 mb-1">{value}</div>
        <div className="text-[9px] text-slate-400 opacity-70 uppercase tracking-widest">{subtext}</div>
    </div>
);
