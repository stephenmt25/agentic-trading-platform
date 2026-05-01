"use client";

import React from "react";
import { Plus, Trash2 } from "lucide-react";

const INDICATORS = ["rsi", "atr", "macd_line", "macd_signal", "macd_histogram"] as const;
const COMPARISONS = ["above", "below", "at_or_above", "at_or_below", "equals"] as const;

type Indicator = (typeof INDICATORS)[number];
type Comparison = (typeof COMPARISONS)[number];

interface Signal {
  indicator: Indicator;
  comparison: Comparison;
  threshold: number;
}

interface StrategyEvalConfig {
  direction?: "long" | "short";
  match_mode?: "all" | "any";
  confidence?: number;
  signals?: Signal[];
}

interface Props {
  config: StrategyEvalConfig;
  onChange: (key: string, value: unknown) => void;
}

export function StrategyEvalForm({ config, onChange }: Props) {
  const direction = config.direction ?? "long";
  const matchMode = config.match_mode ?? "all";
  const confidence = config.confidence ?? 0.6;
  const signals: Signal[] = Array.isArray(config.signals) && config.signals.length > 0
    ? config.signals
    : [{ indicator: "rsi", comparison: "below", threshold: 30 }];

  const updateSignals = (next: Signal[]) => {
    onChange("signals", next);
  };

  return (
    <div className="space-y-4">
      <p className="text-[10px] text-zinc-500 leading-snug">
        These values are saved to the canvas AND compiled into the strategy rules the engine evaluates.
      </p>

      <div className="grid grid-cols-2 gap-3">
        <div>
          <label className="block text-[10px] uppercase tracking-wider text-zinc-500 font-medium mb-1">
            Direction
          </label>
          <select
            value={direction}
            onChange={(e) => onChange("direction", e.target.value)}
            className="w-full bg-zinc-800 border border-zinc-700 rounded px-2 py-1.5 text-xs text-zinc-200"
          >
            <option value="long">long</option>
            <option value="short">short</option>
          </select>
        </div>
        <div>
          <label className="block text-[10px] uppercase tracking-wider text-zinc-500 font-medium mb-1">
            Trigger when
          </label>
          <select
            value={matchMode}
            onChange={(e) => onChange("match_mode", e.target.value)}
            className="w-full bg-zinc-800 border border-zinc-700 rounded px-2 py-1.5 text-xs text-zinc-200"
          >
            <option value="all">all signals match</option>
            <option value="any">any signal matches</option>
          </select>
        </div>
      </div>

      <div>
        <label className="block text-[10px] uppercase tracking-wider text-zinc-500 font-medium mb-1">
          Confidence
        </label>
        <div className="flex items-center gap-2">
          <input
            type="range"
            min={0}
            max={1}
            step={0.05}
            value={confidence}
            onChange={(e) => onChange("confidence", parseFloat(e.target.value))}
            className="flex-1 accent-blue-500"
          />
          <span className="text-xs font-mono text-zinc-300 w-12 text-right tabular-nums">
            {confidence.toFixed(2)}
          </span>
        </div>
      </div>

      <div>
        <div className="flex items-center justify-between mb-2">
          <label className="text-[10px] uppercase tracking-wider text-zinc-500 font-medium">
            Signals
          </label>
          <button
            onClick={() => updateSignals([...signals, { indicator: "rsi", comparison: "below", threshold: 30 }])}
            className="text-[11px] text-emerald-400 hover:text-emerald-300 flex items-center gap-1"
          >
            <Plus className="w-3 h-3" /> Add
          </button>
        </div>
        <div className="space-y-2">
          {signals.map((s, idx) => (
            <div key={idx} className="flex items-center gap-1.5 p-1.5 border border-zinc-800 rounded bg-zinc-950">
              <select
                value={s.indicator}
                onChange={(e) => updateSignals(signals.map((x, i) => i === idx ? { ...x, indicator: e.target.value as Indicator } : x))}
                className="bg-zinc-800 border border-zinc-700 rounded px-1.5 py-1 text-[11px] text-zinc-200 font-mono"
              >
                {INDICATORS.map((ind) => (
                  <option key={ind} value={ind}>{ind}</option>
                ))}
              </select>
              <select
                value={s.comparison}
                onChange={(e) => updateSignals(signals.map((x, i) => i === idx ? { ...x, comparison: e.target.value as Comparison } : x))}
                className="bg-zinc-800 border border-zinc-700 rounded px-1.5 py-1 text-[11px] text-zinc-200 font-mono"
              >
                {COMPARISONS.map((c) => (
                  <option key={c} value={c}>{c.replace(/_/g, " ")}</option>
                ))}
              </select>
              <input
                type="number"
                step="0.01"
                value={s.threshold}
                onChange={(e) => updateSignals(signals.map((x, i) => i === idx ? { ...x, threshold: parseFloat(e.target.value) || 0 } : x))}
                className="flex-1 bg-zinc-800 border border-zinc-700 rounded px-1.5 py-1 text-[11px] text-zinc-200 font-mono tabular-nums w-16"
              />
              {signals.length > 1 && (
                <button
                  onClick={() => updateSignals(signals.filter((_, i) => i !== idx))}
                  className="p-1 text-zinc-500 hover:text-red-400 transition-colors"
                  aria-label="Remove signal"
                >
                  <Trash2 className="w-3 h-3" />
                </button>
              )}
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
