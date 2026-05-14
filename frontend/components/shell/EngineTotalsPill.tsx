"use client";

import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import { Wallet, ExternalLink } from "lucide-react";
import { cn } from "@/lib/utils";
import { api, type PaperTradingStatus } from "@/lib/api/client";
import { useConnectionStore } from "@/lib/stores/connectionStore";

/**
 * Chrome engine-totals pill per `02-information-architecture.md` §4.1.
 *
 * Collapsed state shows net-P&L-since-boot (the headline that the
 * standalone PnL pill would carry once it lands). Click expands a popover
 * with the full strip — gross P&L, trades, win rate, max DD, Sharpe.
 *
 * Polling discipline (2026-05-13): the chrome lives on every surface, so a
 * misbehaving poll cascades into every page. Hardening:
 *   - 30s interval (was 10s) — the strip is "since boot," not real-time
 *   - Skip if the previous request is still in flight (no stacking)
 *   - Hard 8s timeout via AbortController (kills the slowest tail of
 *     /paper-trading/status when the backend is under load — see TECH-DEBT
 *     row for that endpoint)
 *   - Stale-aware render: keep the last known value when a poll fails or
 *     times out, so we don't blink back to "—"
 */

const POLL_INTERVAL_MS = 30_000;
// 20s timeout — long enough to ride out backend slowness (status endpoint
// has been observed in the 20–25s p95 range under memory pressure) without
// letting a truly stuck request occupy one of the browser's 6 concurrent
// slots per origin indefinitely.
const REQUEST_TIMEOUT_MS = 20_000;

type Metrics = PaperTradingStatus["metrics"];

function formatSignedUsdc(value: number): string {
  const sign = value > 0 ? "+" : value < 0 ? "" : "";
  const formatted = value.toLocaleString(undefined, {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  });
  return `${sign}${formatted}`;
}

function formatPct(value: number, decimals = 1): string {
  return `${(value * 100).toFixed(decimals)}%`;
}

function formatRatio(value: number): string {
  return value.toFixed(2);
}

function toneForPnL(value: number | undefined): "ok" | "danger" | "neutral" {
  if (value === undefined) return "neutral";
  if (value > 0) return "ok";
  if (value < 0) return "danger";
  return "neutral";
}

export function EngineTotalsPill() {
  const backendStatus = useConnectionStore((s) => s.backendStatus);
  const [status, setStatus] = useState<PaperTradingStatus | null>(null);
  const [open, setOpen] = useState(false);
  const wrapperRef = useRef<HTMLDivElement>(null);
  const inFlightRef = useRef(false);

  // Poll while connected. Last good snapshot survives a failed poll so the
  // headline doesn't blink to "—" — staleness is implicit from the chrome
  // connection pill. See the polling-discipline note at module top.
  useEffect(() => {
    if (backendStatus !== "connected") return;
    let cancelled = false;

    const fetchStatus = async () => {
      if (inFlightRef.current) return; // skip overlapping polls
      inFlightRef.current = true;

      const controller = new AbortController();
      const timeoutId = window.setTimeout(
        () => controller.abort(),
        REQUEST_TIMEOUT_MS,
      );

      try {
        const next = await api.paperTrading.status({
          signal: controller.signal,
        });
        if (!cancelled) setStatus(next);
      } catch {
        // Swallow — connection pill owns error surfacing. Stale `status`
        // remains visible.
      } finally {
        window.clearTimeout(timeoutId);
        inFlightRef.current = false;
      }
    };

    fetchStatus();
    const id = window.setInterval(fetchStatus, POLL_INTERVAL_MS);
    return () => {
      cancelled = true;
      window.clearInterval(id);
    };
  }, [backendStatus]);

  useEffect(() => {
    if (!open) return;
    const onClickOutside = (e: MouseEvent) => {
      if (wrapperRef.current && !wrapperRef.current.contains(e.target as Node)) {
        setOpen(false);
      }
    };
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") setOpen(false);
    };
    document.addEventListener("mousedown", onClickOutside);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", onClickOutside);
      document.removeEventListener("keydown", onKey);
    };
  }, [open]);

  const metrics: Metrics | null = status?.metrics ?? null;
  const netPnL = metrics?.total_net_pnl;
  const headlineTone = toneForPnL(netPnL);
  const headline =
    netPnL === undefined ? "engine: —" : `engine ${formatSignedUsdc(netPnL)}`;

  return (
    <div className="relative" ref={wrapperRef}>
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        aria-label={`Engine totals: ${headline}`}
        aria-expanded={open}
        aria-haspopup="dialog"
        className={cn(
          "inline-flex items-center gap-1.5 h-6 px-2 rounded-md border text-[11px] num-tabular",
          "transition-colors focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent-500",
          headlineTone === "ok" &&
            "border-bid-700 bg-bid-900/30 text-bid-400 hover:bg-bid-900/50",
          headlineTone === "danger" &&
            "border-danger-700 bg-danger-700/15 text-danger-500 hover:bg-danger-700/25",
          headlineTone === "neutral" &&
            "border-border-subtle bg-bg-canvas text-fg-secondary hover:bg-bg-raised"
        )}
      >
        <Wallet className="w-3 h-3" strokeWidth={1.5} aria-hidden />
        <span>{headline}</span>
      </button>

      {open && (
        <div
          role="dialog"
          aria-label="Engine totals since boot"
          className={cn(
            "absolute right-0 top-8 z-40 w-72 rounded-md p-3",
            "border border-border-subtle bg-bg-panel shadow-lg",
            "text-[12px] text-fg num-tabular"
          )}
        >
          <p className="text-[10px] uppercase tracking-wider text-fg-muted mb-2.5">
            Engine totals (since boot)
          </p>

          {metrics ? (
            <dl className="grid grid-cols-[auto_1fr] gap-x-3 gap-y-1.5">
              <MetricRow
                label="Net P&L"
                value={formatSignedUsdc(metrics.total_net_pnl)}
                tone={toneForPnL(metrics.total_net_pnl)}
              />
              <MetricRow
                label="Gross P&L"
                value={formatSignedUsdc(metrics.total_gross_pnl)}
                tone={toneForPnL(metrics.total_gross_pnl)}
              />
              <MetricRow
                label="Trades"
                value={metrics.total_trades.toLocaleString()}
              />
              <MetricRow
                label="Win rate"
                value={formatPct(metrics.avg_win_rate)}
              />
              <MetricRow
                label="Max DD"
                value={`-${formatPct(Math.abs(metrics.max_drawdown))}`}
                tone={metrics.max_drawdown !== 0 ? "danger" : "neutral"}
              />
              <MetricRow
                label="Sharpe"
                value={formatRatio(metrics.avg_sharpe)}
              />
            </dl>
          ) : (
            <p className="text-fg-muted">
              Live metrics not yet loaded.
            </p>
          )}

          <div className="mt-3 pt-2.5 border-t border-border-subtle flex items-center justify-between text-[11px] text-fg-muted">
            <span>
              {status?.start_date
                ? `since ${status.start_date}`
                : "since boot"}
            </span>
            <Link
              href="/hot/profiles"
              onClick={() => setOpen(false)}
              className="inline-flex items-center gap-1 text-accent-300 hover:text-accent-200"
            >
              open detailed report
              <ExternalLink className="w-3 h-3" strokeWidth={1.5} aria-hidden />
            </Link>
          </div>
        </div>
      )}
    </div>
  );
}

function MetricRow({
  label,
  value,
  tone = "neutral",
}: {
  label: string;
  value: string;
  tone?: "ok" | "danger" | "neutral";
}) {
  return (
    <>
      <dt className="text-fg-muted">{label}</dt>
      <dd
        className={cn(
          "text-right font-medium",
          tone === "ok" && "text-bid-300",
          tone === "danger" && "text-danger-500",
          tone === "neutral" && "text-fg"
        )}
      >
        {value}
      </dd>
    </>
  );
}

export default EngineTotalsPill;
