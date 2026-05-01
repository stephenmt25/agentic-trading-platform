"use client";

import { useState, useEffect, useCallback } from "react";
import { ChevronDown, ChevronUp, Loader2, Pin } from "lucide-react";
import { api, type TradeDecision } from "@/lib/api/client";
import { DecisionDetail } from "./DecisionDetail";
import { InfoTooltip } from "@/components/ui/InfoTooltip";
import { useAnalysisStore } from "@/lib/stores/analysisStore";

const POLL_INTERVAL = 15_000;

export function DecisionFeed({ profileId }: { profileId?: string | null } = {}) {
    const [decisions, setDecisions] = useState<TradeDecision[]>([]);
    const [loading, setLoading] = useState(true);
    const [expandedId, setExpandedId] = useState<string | null>(null);
    const [filter, setFilter] = useState<"all" | "approved" | "blocked">("all");

    const load = useCallback(async () => {
        try {
            const outcome = filter === "approved" ? "APPROVED" : filter === "blocked" ? undefined : undefined;
            const data = await api.paperTrading.decisions({
                limit: 50,
                outcome,
                profile_id: profileId ?? undefined,
            });
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
    }, [filter, profileId]);

    useEffect(() => {
        setLoading(true);
        load();
        const interval = setInterval(load, POLL_INTERVAL);
        return () => clearInterval(interval);
    }, [load]);

    const pinDecision = useAnalysisStore((s) => s.pinDecision);
    const clearPinnedDecision = useAnalysisStore((s) => s.clearPinnedDecision);
    const pinnedId = useAnalysisStore((s) => s.pinnedDecision?.eventId ?? null);

    const toggleExpand = (id: string) => {
        setExpandedId(expandedId === id ? null : id);
    };

    const togglePin = (e: React.MouseEvent, d: TradeDecision) => {
        e.stopPropagation();
        if (pinnedId === d.event_id) {
            clearPinnedDecision();
            return;
        }
        pinDecision({
            eventId: d.event_id,
            time: Math.floor(new Date(d.created_at).getTime() / 1000),
            symbol: d.symbol,
            outcome: d.outcome,
            direction: d.strategy.direction,
        });
    };

    return (
        <div className="flex flex-col h-full min-h-0">
            {/* Header */}
            <div className="flex items-center justify-between mb-3 shrink-0">
                <h2 className="uppercase text-xs font-semibold text-muted-foreground tracking-wider flex items-center gap-1.5">
                    Decision Trace
                    <InfoTooltip text="Every signal evaluation — approved or blocked — with full gate-by-gate trace. Shows why each trade decision was made." />
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
                <div className="py-8 px-4 text-center space-y-2">
                    <p className="text-xs text-muted-foreground">
                        No decisions yet for this profile.
                    </p>
                    <p className="text-[11px] text-muted-foreground/70">
                        The engine evaluates every candle continuously. A decision lands here the
                        moment a signal matches the profile rules — approved or blocked, both with
                        the full gate trace.
                    </p>
                </div>
            ) : (
                <div className="space-y-1.5 flex-1 min-h-0 overflow-y-auto pr-1">
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

                        const isPinned = pinnedId === d.event_id;
                        return (
                            <div key={d.event_id}>
                                <button
                                    onClick={() => toggleExpand(d.event_id)}
                                    className={`w-full text-left p-2.5 border rounded-md transition-colors ${
                                        isPinned ? "border-primary/60 bg-primary/5" : "border-border hover:bg-accent"
                                    }`}
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

                                        {/* Pin to chart */}
                                        <span
                                            role="button"
                                            tabIndex={0}
                                            onClick={(e) => togglePin(e, d)}
                                            onKeyDown={(e) => {
                                                if (e.key === "Enter" || e.key === " ") togglePin(e as unknown as React.MouseEvent, d);
                                            }}
                                            title={isPinned ? "Unpin from chart" : "Pin to chart"}
                                            aria-label={isPinned ? "Unpin from chart" : "Pin to chart"}
                                            className={`shrink-0 p-0.5 rounded transition-colors cursor-pointer focus-visible:outline-2 focus-visible:outline-offset-1 focus-visible:outline-primary ${
                                                isPinned ? "text-primary" : "text-muted-foreground hover:text-foreground"
                                            }`}
                                        >
                                            <Pin size={11} className={isPinned ? "fill-primary" : ""} />
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
