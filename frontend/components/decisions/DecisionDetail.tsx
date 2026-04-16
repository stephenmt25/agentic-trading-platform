"use client";

import type { TradeDecision } from "@/lib/api/client";
import { CheckCircle2, XCircle, Minus } from "lucide-react";

// ── Helpers ──

function GateRow({ name, gate }: { name: string; gate: Record<string, unknown> & { passed: boolean } }) {
    const reason = gate.reason as string | undefined;
    const suggestedQty = gate.suggested_qty as string | undefined;
    const allocationPct = gate.allocation_pct as string | undefined;
    return (
        <div className="flex items-center gap-2 py-1 text-xs font-mono">
            {gate.passed ? (
                <CheckCircle2 size={12} className="text-emerald-500 shrink-0" />
            ) : (
                <XCircle size={12} className="text-red-500 shrink-0" />
            )}
            <span className={gate.passed ? "text-foreground" : "text-red-400"}>{name}</span>
            {reason && (
                <span className="text-muted-foreground truncate">{reason}</span>
            )}
            {suggestedQty && (
                <span className="text-muted-foreground ml-auto tabular-nums">qty: {suggestedQty}</span>
            )}
            {allocationPct !== undefined && (
                <span className="text-muted-foreground ml-auto tabular-nums">alloc: {allocationPct}</span>
            )}
        </div>
    );
}

function ConditionRow({ cond }: { cond: { indicator: string; operator: string; threshold: number; actual_value: number; passed: boolean } }) {
    return (
        <div className="flex items-center gap-2 py-0.5 text-xs font-mono">
            {cond.passed ? (
                <CheckCircle2 size={10} className="text-emerald-500 shrink-0" />
            ) : (
                <XCircle size={10} className="text-red-400 shrink-0" />
            )}
            <span className="text-muted-foreground">{cond.indicator}</span>
            <span className="text-foreground">{cond.operator}</span>
            <span className="text-muted-foreground tabular-nums">{cond.threshold}</span>
            <span className="text-slate-600">|</span>
            <span className="tabular-nums text-foreground">{cond.actual_value.toFixed(4)}</span>
        </div>
    );
}

function AgentRow({ name, data }: { name: string; data: { score: number | null; weight: number; adjustment: number } }) {
    const adj = data.adjustment;
    const barWidth = Math.min(Math.abs(adj) * 500, 100); // scale for visual
    return (
        <div className="flex items-center gap-2 py-0.5 text-xs font-mono">
            <span className="w-20 text-muted-foreground capitalize">{name}</span>
            <span className="w-14 tabular-nums text-right">{data.score !== null ? data.score.toFixed(3) : "—"}</span>
            <span className="w-10 tabular-nums text-right text-muted-foreground">{data.weight.toFixed(2)}</span>
            <span className={`w-16 tabular-nums text-right ${adj > 0 ? "text-emerald-500" : adj < 0 ? "text-red-400" : "text-muted-foreground"}`}>
                {adj > 0 ? "+" : ""}{adj.toFixed(4)}
            </span>
            <div className="flex-1 h-1.5 bg-accent rounded overflow-hidden">
                <div
                    className={`h-full rounded ${adj >= 0 ? "bg-emerald-500" : "bg-red-500"}`}
                    style={{ width: `${barWidth}%` }}
                />
            </div>
        </div>
    );
}

// ── Main Component ──

export function DecisionDetail({ decision }: { decision: TradeDecision }) {
    const d = decision;
    const isApproved = d.outcome === "APPROVED";

    return (
        <div className="space-y-4 text-xs animate-in fade-in slide-in-from-top-1 duration-150">
            {/* Indicators */}
            <div>
                <h4 className="uppercase text-[10px] font-semibold text-muted-foreground tracking-wider mb-2">Indicators</h4>
                <div className="grid grid-cols-2 md:grid-cols-4 gap-x-4 gap-y-1 font-mono tabular-nums">
                    <div>RSI <span className={`${d.indicators.rsi < 30 ? "text-emerald-500" : d.indicators.rsi > 70 ? "text-red-400" : "text-foreground"}`}>{d.indicators.rsi.toFixed(1)}</span></div>
                    <div>MACD <span className="text-foreground">{d.indicators.histogram.toFixed(2)}</span></div>
                    <div>ATR <span className="text-foreground">{d.indicators.atr.toFixed(2)}</span></div>
                    {d.indicators.adx !== null && <div>ADX <span className="text-foreground">{d.indicators.adx.toFixed(1)}</span></div>}
                    {d.indicators.bb_pct_b !== null && <div>BB%B <span className="text-foreground">{d.indicators.bb_pct_b.toFixed(3)}</span></div>}
                    {d.indicators.obv !== null && <div>OBV <span className="text-foreground">{d.indicators.obv.toFixed(0)}</span></div>}
                    {d.indicators.choppiness !== null && <div>Chop <span className="text-foreground">{d.indicators.choppiness.toFixed(1)}</span></div>}
                </div>
            </div>

            {/* Strategy Rule Match */}
            {d.strategy.conditions?.length > 0 && (
                <div>
                    <h4 className="uppercase text-[10px] font-semibold text-muted-foreground tracking-wider mb-2">
                        Strategy ({d.strategy.logic}) — {d.strategy.direction} — conf {d.strategy.base_confidence}
                    </h4>
                    <div className="border border-border rounded p-2 space-y-0.5">
                        {d.strategy.conditions.map((c, i) => (
                            <ConditionRow key={i} cond={c} />
                        ))}
                    </div>
                </div>
            )}

            {/* Regime */}
            {d.regime && (
                <div>
                    <h4 className="uppercase text-[10px] font-semibold text-muted-foreground tracking-wider mb-1">Regime</h4>
                    <div className="flex gap-4 font-mono">
                        <span>Rule: <span className="text-foreground">{d.regime.rule_based ?? "—"}</span></span>
                        <span>HMM: <span className="text-foreground">{d.regime.hmm ?? "—"}</span></span>
                        <span>Mult: <span className="text-foreground">{d.regime.confidence_multiplier}x</span></span>
                    </div>
                </div>
            )}

            {/* Agent Influence */}
            {d.agents && (
                <div>
                    <h4 className="uppercase text-[10px] font-semibold text-muted-foreground tracking-wider mb-2">
                        Agent Influence — {d.agents.confidence_before.toFixed(3)} → {d.agents.confidence_after.toFixed(3)}
                        {d.agents.confidence_before > 0 && (
                            <span className={`ml-1 ${d.agents.confidence_after >= d.agents.confidence_before ? "text-emerald-500" : "text-red-400"}`}>
                                ({d.agents.confidence_after >= d.agents.confidence_before ? "+" : ""}
                                {(((d.agents.confidence_after - d.agents.confidence_before) / d.agents.confidence_before) * 100).toFixed(1)}%)
                            </span>
                        )}
                    </h4>
                    <div className="space-y-0.5">
                        <div className="flex items-center gap-2 text-[10px] font-mono text-muted-foreground mb-1">
                            <span className="w-20">Agent</span>
                            <span className="w-14 text-right">Score</span>
                            <span className="w-10 text-right">Weight</span>
                            <span className="w-16 text-right">Adjust</span>
                        </div>
                        {d.agents.ta && <AgentRow name="TA" data={d.agents.ta} />}
                        {d.agents.sentiment && <AgentRow name="Sentiment" data={d.agents.sentiment} />}
                        {d.agents.debate && <AgentRow name="Debate" data={d.agents.debate} />}
                    </div>
                </div>
            )}

            {/* Gates Pipeline */}
            {Object.keys(d.gates).length > 0 && (
                <div>
                    <h4 className="uppercase text-[10px] font-semibold text-muted-foreground tracking-wider mb-1">Gates</h4>
                    <div className="border border-border rounded p-2">
                        {Object.entries(d.gates).map(([name, gate]) => (
                            <GateRow key={name} name={name} gate={gate} />
                        ))}
                    </div>
                </div>
            )}

            {/* Order ID for approved */}
            {isApproved && d.order_id && (
                <div className="text-[10px] font-mono text-muted-foreground">
                    Order: {d.order_id}
                </div>
            )}
        </div>
    );
}
