"use client";

import { useState, useEffect, useCallback } from "react";
import { ChevronDown, ChevronUp, Loader2 } from "lucide-react";
import { api, type TradeDecision } from "@/lib/api/client";
import { DecisionDetail } from "./DecisionDetail";

const POLL_INTERVAL = 15_000;

export function DecisionFeed() {
    const [decisions, setDecisions] = useState<TradeDecision[]>([]);
    const [loading, setLoading] = useState(true);
    const [expandedId, setExpandedId] = useState<string | null>(null);
    const [filter, setFilter] = useState<"all" | "approved" | "blocked">("all");

    const load = useCallback(async () => {
        try {
            const outcome = filter === "approved" ? "APPROVED" : filter === "blocked" ? undefined : undefined;
            const data = await api.paperTrading.decisions({ limit: 50, outcome });
            // If filtering blocked, filter client-side since there are multiple blocked outcomes
            if (filter === "blocked") {
                setDecisions(data.filter(d => d.outcome !== "APPROVED"));
            } else {
                setDecisions(data);
            }
        } catch {
            // Silent — don't crash the page if decisions table doesn't exist yet
        } finally {
            setLoading(false);
        }
    }, [filter]);

    useEffect(() => {
        setLoading(true);
        load();
        const interval = setInterval(load, POLL_INTERVAL);
        return () => clearInterval(interval);
    }, [load]);

    const toggleExpand = (id: string) => {
        setExpandedId(expandedId === id ? null : id);
    };

    return (
        <div>
            {/* Header */}
            <div className="flex items-center justify-between mb-3">
                <h2 className="uppercase text-xs font-semibold text-muted-foreground tracking-wider">
                    Decision Trace
                </h2>
                <div className="flex items-center gap-1">
                    {(["all", "approved", "blocked"] as const).map((f) => (
                        <button
                            key={f}
                            onClick={() => setFilter(f)}
                            className={`px-2 py-0.5 rounded text-[10px] font-mono uppercase transition-colors ${
                                filter === f
                                    ? "bg-accent text-foreground"
                                    : "text-muted-foreground hover:text-foreground"
                            }`}
                        >
                            {f}
                        </button>
                    ))}
                </div>
            </div>

            {/* Feed */}
            {loading ? (
                <div className="flex items-center justify-center py-8 text-muted-foreground">
                    <Loader2 size={16} className="animate-spin mr-2" />
                    <span className="text-xs">Loading decisions...</span>
                </div>
            ) : decisions.length === 0 ? (
                <div className="py-6 text-center text-xs text-muted-foreground font-mono">
                    No trade decisions recorded yet.
                </div>
            ) : (
                <div className="space-y-1.5 max-h-[500px] overflow-y-auto pr-1">
                    {decisions.map((d) => {
                        const isApproved = d.outcome === "APPROVED";
                        const isExpanded = expandedId === d.event_id;
                        const time = new Date(d.created_at).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" });
                        const conf = d.agents?.confidence_after ?? d.strategy.base_confidence;

                        // Build one-line summary
                        let summary: string;
                        if (isApproved && d.agents) {
                            const parts: string[] = [];
                            if (d.agents.ta && d.agents.ta.score !== null) parts.push(`TA:${d.agents.ta.adjustment > 0 ? "+" : ""}${d.agents.ta.adjustment.toFixed(3)}`);
                            if (d.agents.sentiment && d.agents.sentiment.score !== null) parts.push(`Sent:${d.agents.sentiment.adjustment > 0 ? "+" : ""}${d.agents.sentiment.adjustment.toFixed(3)}`);
                            if (d.agents.debate && d.agents.debate.score !== null) parts.push(`Dbt:${d.agents.debate.adjustment > 0 ? "+" : ""}${d.agents.debate.adjustment.toFixed(3)}`);
                            summary = parts.join("  ");
                        } else {
                            // Blocked — find the failing gate
                            const failedGate = Object.entries(d.gates).find(([, g]) => !g.passed);
                            summary = failedGate
                                ? `${failedGate[0]}${failedGate[1].reason ? `: ${failedGate[1].reason}` : ""}`
                                : d.outcome.replace("BLOCKED_", "");
                        }

                        return (
                            <div key={d.event_id}>
                                <button
                                    onClick={() => toggleExpand(d.event_id)}
                                    className="w-full text-left p-2.5 border border-border rounded-md hover:bg-accent transition-colors"
                                >
                                    <div className="flex items-center gap-2 text-xs font-mono">
                                        {/* Status dot */}
                                        <span className={`w-2 h-2 rounded-full shrink-0 ${isApproved ? "bg-emerald-500" : "bg-slate-500"}`} />

                                        {/* Symbol + direction */}
                                        <span className="font-semibold text-foreground">{d.symbol}</span>
                                        <span className={`text-[10px] font-semibold ${d.strategy.direction === "BUY" ? "text-emerald-500" : "text-red-400"}`}>
                                            {d.strategy.direction}
                                        </span>

                                        {/* Time */}
                                        <span className="text-muted-foreground tabular-nums">{time}</span>

                                        {/* Confidence */}
                                        <span className="text-muted-foreground tabular-nums">conf:{conf.toFixed(2)}</span>

                                        {/* Outcome */}
                                        <span className={`ml-auto text-[10px] font-semibold ${isApproved ? "text-emerald-500" : "text-amber-500"}`}>
                                            {isApproved ? "APPROVED" : "BLOCKED"}
                                        </span>

                                        {/* Expand */}
                                        {isExpanded
                                            ? <ChevronUp size={12} className="text-muted-foreground shrink-0" />
                                            : <ChevronDown size={12} className="text-muted-foreground shrink-0" />
                                        }
                                    </div>

                                    {/* One-line summary */}
                                    <div className="mt-1 text-[10px] text-muted-foreground font-mono truncate pl-4">
                                        {summary}
                                    </div>
                                </button>

                                {/* Expanded detail */}
                                {isExpanded && (
                                    <div className="mt-1 p-3 border border-border rounded-md">
                                        <DecisionDetail decision={d} />
                                    </div>
                                )}
                            </div>
                        );
                    })}
                </div>
            )}
        </div>
    );
}
