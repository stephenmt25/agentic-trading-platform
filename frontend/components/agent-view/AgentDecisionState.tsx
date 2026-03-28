"use client";

import { useEffect, useRef, useState } from "react";
import { Brain, ChevronDown, ChevronRight, Settings2, Workflow } from "lucide-react";
import { useAgentViewStore } from "@/lib/stores/agentViewStore";
import type { DecisionTrace } from "@/lib/types/telemetry";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function formatValue(value: unknown): string {
  if (value === null || value === undefined) return "\u2014";
  if (typeof value === "object") return JSON.stringify(value);
  return String(value);
}

// ---------------------------------------------------------------------------
// Sub-components
// ---------------------------------------------------------------------------

interface KeyValueRowProps {
  label: string;
  value: unknown;
  highlight?: boolean;
}

function KeyValueRow({ label, value, highlight }: KeyValueRowProps) {
  return (
    <div
      className={`
        flex items-baseline justify-between gap-3 px-3 py-1 text-xs
        transition-colors duration-300
        ${highlight ? "bg-amber-500/10" : ""}
      `}
    >
      <span className="shrink-0 text-slate-400">{label}</span>
      <span className="min-w-0 truncate font-mono text-slate-200 text-right">
        {formatValue(value)}
      </span>
    </div>
  );
}

interface StateVariablesSectionProps {
  stateVars: Record<string, unknown>;
}

function StateVariablesSection({ stateVars }: StateVariablesSectionProps) {
  const prevVarsRef = useRef<Record<string, unknown>>({});
  const [changedKeys, setChangedKeys] = useState<Set<string>>(new Set());

  useEffect(() => {
    const changed = new Set<string>();
    for (const key of Object.keys(stateVars)) {
      const prev = prevVarsRef.current[key];
      const curr = stateVars[key];
      if (JSON.stringify(prev) !== JSON.stringify(curr)) {
        changed.add(key);
      }
    }
    prevVarsRef.current = { ...stateVars };

    if (changed.size > 0) {
      setChangedKeys(changed);
      const timer = setTimeout(() => setChangedKeys(new Set()), 500);
      return () => clearTimeout(timer);
    }
  }, [stateVars]);

  const entries = Object.entries(stateVars);

  return (
    <div>
      <div className="flex items-center gap-2 border-b border-slate-800 px-3 py-2">
        <Brain className="h-3.5 w-3.5 text-violet-400" />
        <span className="text-xs font-semibold text-slate-200">
          State Variables
        </span>
      </div>

      {entries.length === 0 ? (
        <div className="px-3 py-4 text-xs text-slate-500">
          No state variables exposed
        </div>
      ) : (
        <div className="divide-y divide-slate-800/30">
          {entries.map(([key, value]) => (
            <KeyValueRow
              key={key}
              label={key}
              value={value}
              highlight={changedKeys.has(key)}
            />
          ))}
        </div>
      )}
    </div>
  );
}

interface DecisionTraceSectionProps {
  decision: DecisionTrace;
}

function DecisionTraceSection({ decision }: DecisionTraceSectionProps) {
  const inputEntries = Object.entries(decision.inputs);
  const outputEntries = Object.entries(decision.output);

  return (
    <div>
      <div className="flex items-center justify-between border-b border-slate-800 px-3 py-2">
        <div className="flex items-center gap-2">
          <Workflow className="h-3.5 w-3.5 text-amber-400" />
          <span className="text-xs font-semibold text-slate-200">
            Last Decision Trace
          </span>
        </div>
        <span className="rounded bg-slate-800 px-1.5 py-0.5 font-mono text-[10px] text-slate-300">
          {decision.duration_ms.toFixed(1)}ms
        </span>
      </div>

      <div className="space-y-3 p-3">
        {/* Inputs */}
        <div>
          <span className="text-[10px] font-semibold uppercase tracking-wider text-slate-500">
            Inputs
          </span>
          <div className="mt-1 rounded border border-slate-800 bg-slate-950/50">
            {inputEntries.length === 0 ? (
              <div className="px-2 py-1 text-xs text-slate-500">None</div>
            ) : (
              inputEntries.map(([key, value]) => (
                <KeyValueRow key={key} label={key} value={value} />
              ))
            )}
          </div>
        </div>

        {/* Logic Path */}
        <div>
          <span className="text-[10px] font-semibold uppercase tracking-wider text-slate-500">
            Logic Path
          </span>
          <div className="mt-1 space-y-0.5">
            {decision.logic_path.length === 0 ? (
              <div className="px-2 py-1 text-xs text-slate-500">
                No logic steps recorded
              </div>
            ) : (
              decision.logic_path.map((step, i) => (
                <div key={i} className="flex items-start gap-2 text-xs">
                  <span className="shrink-0 font-mono text-slate-500">
                    {i + 1}.
                  </span>
                  {i > 0 && (
                    <span className="shrink-0 text-slate-600">&rarr;</span>
                  )}
                  <span className="font-mono text-slate-300">{step}</span>
                </div>
              ))
            )}
          </div>
        </div>

        {/* Output */}
        <div>
          <span className="text-[10px] font-semibold uppercase tracking-wider text-slate-500">
            Output
          </span>
          <div className="mt-1 rounded border border-slate-800 bg-slate-950/50">
            {outputEntries.map(([key, value]) => (
              <KeyValueRow key={key} label={key} value={value} />
            ))}
          </div>

          {/* Confidence bar */}
          {decision.confidence !== undefined && (
            <div className="mt-2 flex items-center gap-2">
              <span className="text-[10px] text-slate-500">Confidence</span>
              <div className="h-1.5 flex-1 rounded-full bg-slate-800">
                <div
                  className="h-full rounded-full bg-emerald-500 transition-all duration-300"
                  style={{
                    width: `${Math.round(decision.confidence * 100)}%`,
                  }}
                />
              </div>
              <span className="font-mono text-[10px] text-slate-400">
                {(decision.confidence * 100).toFixed(1)}%
              </span>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

interface ActiveConfigSectionProps {
  config: Record<string, unknown>;
}

function ActiveConfigSection({ config }: ActiveConfigSectionProps) {
  const [expanded, setExpanded] = useState(false);
  const entries = Object.entries(config);

  if (entries.length === 0) return null;

  return (
    <div className="border-t border-slate-800">
      <button
        type="button"
        onClick={() => setExpanded((p) => !p)}
        className="flex w-full items-center gap-2 px-3 py-2 text-xs text-slate-400 hover:text-slate-200 transition-colors"
        aria-expanded={expanded}
        aria-label="Toggle active configuration"
      >
        <Settings2 className="h-3 w-3" />
        {expanded ? (
          <ChevronDown className="h-3 w-3" />
        ) : (
          <ChevronRight className="h-3 w-3" />
        )}
        <span className="font-semibold">Active Config</span>
        <span className="font-mono text-[10px] text-slate-500">
          ({entries.length} keys)
        </span>
      </button>

      {expanded && (
        <div className="divide-y divide-slate-800/30 border-t border-slate-800/50">
          {entries.map(([key, value]) => (
            <KeyValueRow key={key} label={key} value={value} />
          ))}
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Props
// ---------------------------------------------------------------------------

interface AgentDecisionStateProps {
  agentId: string;
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function AgentDecisionState({ agentId }: AgentDecisionStateProps) {
  const agentState = useAgentViewStore((s) => s.agentStates[agentId]);

  const stateVars = agentState?.state_vars ?? {};
  const lastDecision = agentState?.last_decision;
  const activeConfig = agentState?.active_config ?? {};

  return (
    <div className="flex h-full flex-col overflow-auto bg-[#161b22]">
      {/* State Variables (top half) */}
      <StateVariablesSection stateVars={stateVars} />

      {/* Divider */}
      <div className="border-t border-slate-700/50" />

      {/* Last Decision Trace (bottom half) */}
      {lastDecision ? (
        <DecisionTraceSection decision={lastDecision} />
      ) : (
        <div className="flex flex-1 flex-col items-center justify-center gap-2 px-3 py-6">
          <Workflow className="h-5 w-5 text-slate-600" />
          <span className="text-xs text-slate-500">
            No decision traces recorded
          </span>
        </div>
      )}

      {/* Active Config (collapsed by default) */}
      <ActiveConfigSection config={activeConfig} />
    </div>
  );
}
