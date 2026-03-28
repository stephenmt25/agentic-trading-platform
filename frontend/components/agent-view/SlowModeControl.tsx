"use client";

import { Gauge, Zap } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import {
  MIN_SLOW_MODE_RATE_MS,
  MAX_SLOW_MODE_RATE_MS,
} from "@/lib/constants/agent-view";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface SlowModeProps {
  enabled: boolean;
  rateMs: number;
  bufferedCount: number;
  toggle: () => void;
  setRate: (ms: number) => void;
  flushNow: () => void;
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function SlowModeControl({
  enabled,
  rateMs,
  bufferedCount,
  toggle,
  setRate,
  flushNow,
}: SlowModeProps) {
  return (
    <div className="flex items-center gap-2">
      {/* Toggle button */}
      <button
        type="button"
        onClick={toggle}
        className={`
          flex items-center gap-1.5 rounded px-2 py-1 text-xs font-medium
          transition-colors
          ${
            enabled
              ? "bg-amber-500/20 text-amber-400 hover:bg-amber-500/30"
              : "bg-slate-800 text-slate-400 hover:bg-slate-700 hover:text-slate-300"
          }
        `}
        aria-pressed={enabled}
        aria-label={enabled ? "Disable slow mode" : "Enable slow mode"}
      >
        <Gauge className="h-3 w-3" />
        <span>Slow Mode</span>
      </button>

      {enabled && (
        <>
          {/* Rate slider */}
          <label className="flex items-center gap-1.5 text-xs text-slate-500">
            <input
              type="range"
              min={MIN_SLOW_MODE_RATE_MS}
              max={MAX_SLOW_MODE_RATE_MS}
              step={100}
              value={rateMs}
              onChange={(e) => setRate(Number(e.target.value))}
              className="h-1 w-20 cursor-pointer appearance-none rounded-full bg-slate-700 accent-amber-500"
              aria-label="Slow mode flush interval"
            />
            <span className="font-mono text-slate-400 tabular-nums">
              {(rateMs / 1000).toFixed(1)}s
            </span>
          </label>

          {/* Buffered count badge */}
          {bufferedCount > 0 && (
            <Badge
              variant="secondary"
              className="bg-slate-700 px-1.5 text-[10px] font-mono text-slate-300"
            >
              {bufferedCount} buffered
            </Badge>
          )}

          {/* Flush button */}
          <button
            type="button"
            onClick={flushNow}
            disabled={bufferedCount === 0}
            className="flex items-center gap-1 rounded px-1.5 py-0.5 text-[10px] font-medium
              text-slate-400 transition-colors hover:bg-slate-700 hover:text-slate-200
              disabled:cursor-not-allowed disabled:opacity-40"
            aria-label="Flush buffered events now"
          >
            <Zap className="h-2.5 w-2.5" />
            Flush
          </button>
        </>
      )}
    </div>
  );
}
