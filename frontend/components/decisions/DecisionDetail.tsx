"use client";

import { useEffect, useRef, useState } from "react";
import type { TradeDecision } from "@/lib/api/client";
import { api } from "@/lib/api/client";
import { CheckCircle2, XCircle, Minus } from "lucide-react";
import {
  createChart,
  createSeriesMarkers,
  CandlestickSeries,
  ColorType,
  type IChartApi,
  type ISeriesApi,
  type Time,
} from "lightweight-charts";

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

// ── Inline mini-chart: ~20 candles of 1m context around the decision ──

function DecisionContextChart({ decision }: { decision: TradeDecision }) {
    const containerRef = useRef<HTMLDivElement>(null);
    const chartRef = useRef<IChartApi | null>(null);
    const seriesRef = useRef<ISeriesApi<"Candlestick"> | null>(null);
    const [loading, setLoading] = useState(true);
    const [empty, setEmpty] = useState(false);

    const decisionEpoch = Math.floor(new Date(decision.created_at).getTime() / 1000);

    useEffect(() => {
        if (!containerRef.current) return;
        const chart = createChart(containerRef.current, {
            height: 120,
            layout: {
                background: { type: ColorType.Solid, color: "transparent" },
                textColor: "#9ca3af",
                fontFamily: "'IBM Plex Mono', monospace",
                fontSize: 10,
            },
            grid: {
                vertLines: { color: "rgba(255,255,255,0.04)" },
                horzLines: { color: "rgba(255,255,255,0.04)" },
            },
            rightPriceScale: { borderColor: "rgba(255,255,255,0.1)" },
            timeScale: { borderColor: "rgba(255,255,255,0.1)", timeVisible: true, secondsVisible: false },
            handleScroll: false,
            handleScale: false,
        });
        const series = chart.addSeries(CandlestickSeries, {
            upColor: "#22c55e", downColor: "#ef4444",
            borderUpColor: "#22c55e", borderDownColor: "#ef4444",
            wickUpColor: "#22c55e", wickDownColor: "#ef4444",
        });
        chartRef.current = chart;
        seriesRef.current = series;

        const observer = new ResizeObserver((entries) => {
            for (const e of entries) chart.applyOptions({ width: e.contentRect.width });
        });
        observer.observe(containerRef.current);

        return () => {
            observer.disconnect();
            chart.remove();
            chartRef.current = null;
            seriesRef.current = null;
        };
    }, []);

    useEffect(() => {
        let cancelled = false;
        async function load() {
            if (!seriesRef.current || !chartRef.current) return;
            setLoading(true);
            const span = 60 * 15; // 15 minutes either side at 1m
            try {
                const candles = await api.marketData.candles(
                    decision.symbol,
                    "1m",
                    500,
                    { start: decisionEpoch - span, end: decisionEpoch + span },
                );
                if (cancelled || !seriesRef.current) return;
                if (!candles.length) {
                    setEmpty(true);
                    return;
                }
                seriesRef.current.setData(
                    candles.map((c) => ({
                        time: c.time as Time,
                        open: c.open, high: c.high, low: c.low, close: c.close,
                    })),
                );
                const isApproved = decision.outcome === "APPROVED";
                createSeriesMarkers(seriesRef.current, [{
                    time: decisionEpoch as Time,
                    position: decision.strategy.direction === "BUY" ? "belowBar" : "aboveBar",
                    color: isApproved ? "#22c55e" : "#f59e0b",
                    shape: decision.strategy.direction === "BUY" ? "arrowUp" : "arrowDown",
                    text: isApproved ? "APPROVED" : "BLOCKED",
                }]);
                chartRef.current.timeScale().fitContent();
                setEmpty(false);
            } catch {
                setEmpty(true);
            } finally {
                if (!cancelled) setLoading(false);
            }
        }
        load();
        return () => { cancelled = true; };
    }, [decision.event_id, decision.symbol, decisionEpoch]);

    return (
        <div className="relative">
            <div ref={containerRef} className="w-full" />
            {loading && (
                <div className="absolute inset-0 flex items-center justify-center text-[10px] text-muted-foreground font-mono">
                    loading 1m context…
                </div>
            )}
            {!loading && empty && (
                <div className="absolute inset-0 flex items-center justify-center text-[10px] text-muted-foreground font-mono">
                    no candles for this window
                </div>
            )}
        </div>
    );
}

// ── Main Component ──

export function DecisionDetail({ decision }: { decision: TradeDecision }) {
    const d = decision;
    const isApproved = d.outcome === "APPROVED";

    return (
        <div className="space-y-4 text-xs animate-in fade-in slide-in-from-top-1 duration-150">
            {/* Mini chart context */}
            <div>
                <h4 className="uppercase text-[10px] font-semibold text-muted-foreground tracking-wider mb-2">
                    Market context — {d.symbol} · 1m
                </h4>
                <div className="border border-border rounded p-2">
                    <DecisionContextChart decision={d} />
                </div>
            </div>

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
