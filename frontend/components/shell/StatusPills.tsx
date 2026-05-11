"use client";

import { useEffect } from "react";
import { useConnectionStore } from "@/lib/stores/connectionStore";
import { useKillSwitchStore } from "@/lib/stores/killSwitchStore";
import { useTradingModeStore, type TradingMode } from "@/lib/stores/tradingModeStore";
import { api } from "@/lib/api/client";
import { Activity, Shield, FlaskConical, Beaker, AlertTriangle } from "lucide-react";
import { cn } from "@/lib/utils";

const IS_MOCK_DATA = process.env.NEXT_PUBLIC_AGENT_VIEW_MOCK === "true";

type PillTone = "neutral" | "ok" | "warn" | "danger" | "accent";

interface PillProps {
  icon: React.ComponentType<{ className?: string; strokeWidth?: number; "aria-hidden"?: boolean }>;
  label: string;
  value: string;
  tone?: PillTone;
}

function Pill({ icon: Icon, label, value, tone = "neutral" }: PillProps) {
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 h-6 px-2 rounded-md border text-[11px] num-tabular",
        tone === "ok" && "border-bid-700 bg-bid-900/30 text-bid-400",
        tone === "warn" && "border-warn-700 bg-warn-700/15 text-warn-400",
        tone === "danger" && "border-danger-700 bg-danger-700/15 text-danger-500",
        tone === "accent" && "border-accent-700 bg-accent-900/30 text-accent-400",
        tone === "neutral" && "border-border-subtle bg-bg-canvas text-fg-secondary"
      )}
      aria-label={`${label}: ${value}`}
    >
      <Icon className="w-3 h-3" strokeWidth={1.5} aria-hidden />
      <span>{value}</span>
    </span>
  );
}

const MODE_TONE: Record<TradingMode, PillTone> = {
  PAPER: "warn",
  TESTNET: "accent",
  LIVE: "danger",
};

const MODE_ICON: Record<TradingMode, React.ComponentType<{ className?: string; strokeWidth?: number; "aria-hidden"?: boolean }>> = {
  PAPER: FlaskConical,
  TESTNET: Beaker,
  LIVE: AlertTriangle,
};

/**
 * Status pills row per IA §4. Phase 4.3 shipped the live/connection pill
 * and the kill-switch pill (the two with real data sources today).
 * Phase 8.1 GAP-3 (2026-05-11) adds the trading-mode pill — misreading
 * PAPER vs LIVE is a real-money risk class, so the badge belongs in
 * every-surface chrome.
 *
 * Regime, latency, agent count, and live PnL pills are deferred to
 * Phase 6 surface integrations where the data sources land.
 */
export function StatusPills() {
  const backendStatus = useConnectionStore((s) => s.backendStatus);
  const killState = useKillSwitchStore((s) => s.state);
  const mode = useTradingModeStore((s) => s.mode);
  const setMode = useTradingModeStore((s) => s.setMode);

  // Bootstrap fetch: the trading mode is set by env vars at api_gateway
  // startup, so a one-shot fetch on mount is enough. We also re-fetch any
  // time backendStatus flips back to "connected" so the badge recovers
  // after an api_gateway restart instead of staying stuck on the prior value.
  useEffect(() => {
    if (backendStatus !== "connected") return;
    let cancelled = false;
    api.paperTrading.mode()
      .then((m) => { if (!cancelled) setMode(m.effective_mode); })
      .catch(() => { /* offline — leave whatever was last seen */ });
    return () => { cancelled = true; };
  }, [backendStatus, setMode]);

  const liveTone: PillTone = IS_MOCK_DATA
    ? "warn"
    : backendStatus === "connected"
      ? "ok"
      : "danger";
  const liveLabel = IS_MOCK_DATA
    ? "mock"
    : backendStatus === "connected"
      ? "live"
      : "offline";

  const ksTone: PillTone =
    killState === "off" ? "neutral" : killState === "soft" ? "warn" : "danger";
  const ksValue = killState === "off" ? "armed: off" : `armed: ${killState}`;

  return (
    <div className="hidden md:flex items-center gap-1.5">
      <Pill icon={Activity} label="connection" value={liveLabel} tone={liveTone} />
      <Pill icon={Shield} label="kill switch" value={ksValue} tone={ksTone} />
      {mode && (
        <Pill
          icon={MODE_ICON[mode]}
          label="trading mode"
          value={mode.toLowerCase()}
          tone={MODE_TONE[mode]}
        />
      )}
    </div>
  );
}
