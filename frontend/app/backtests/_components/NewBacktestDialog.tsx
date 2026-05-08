"use client";

import { useEffect, useMemo, useState } from "react";
import { Play, X, Info } from "lucide-react";
import { toast } from "sonner";
import {
  Button,
  Input,
  Select,
  Tag,
  type SelectOption,
} from "@/components/primitives";
import { api, type ProfileResponse } from "@/lib/api/client";

const TIMEFRAMES: SelectOption[] = [
  { value: "1m", label: "1 minute" },
  { value: "5m", label: "5 minutes" },
  { value: "15m", label: "15 minutes" },
  { value: "1h", label: "1 hour" },
  { value: "1d", label: "1 day" },
];

interface SubmittedRun {
  jobId: string;
  profileId: string;
  symbol: string;
  startDate: string;
  endDate: string;
  timeframe: string;
  status: "queued" | "running";
}

function defaultStartDate(): string {
  const d = new Date();
  d.setDate(d.getDate() - 30);
  return d.toISOString().slice(0, 10);
}

function defaultEndDate(): string {
  return new Date().toISOString().slice(0, 10);
}

/**
 * NewBacktestDialog — modal per surface spec §4.
 *
 * The spec lists multi-symbol, slippage model, fees, walk-forward, and
 * weighting fields. The api.backtest.submit endpoint only supports
 * single symbol + numeric slippage % + simple date range. The dialog
 * renders what's wired and footnotes the rest as Pending — matching the
 * Settings surface's pattern of surfacing reality rather than faking
 * fields the engine doesn't read.
 */
export function NewBacktestDialog({
  profiles,
  onCancel,
  onSubmit,
}: {
  profiles: ProfileResponse[];
  onCancel: () => void;
  onSubmit: (run: SubmittedRun) => void;
}) {
  const activeProfiles = useMemo(
    () => profiles.filter((p) => !p.deleted_at),
    [profiles]
  );

  const [profileId, setProfileId] = useState<string | undefined>(
    activeProfiles[0]?.profile_id
  );
  const [symbol, setSymbol] = useState("BTC/USDT");
  const [startDate, setStartDate] = useState(defaultStartDate());
  const [endDate, setEndDate] = useState(defaultEndDate());
  const [timeframe, setTimeframe] = useState("1m");
  const [slippagePct, setSlippagePct] = useState("0.001");
  const [submitting, setSubmitting] = useState(false);

  const profileOptions: SelectOption[] = activeProfiles.map((p) => ({
    value: p.profile_id,
    label: p.name || p.profile_id,
  }));

  // Esc to cancel.
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        e.preventDefault();
        onCancel();
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onCancel]);

  const valid =
    !!profileId &&
    !!symbol &&
    !!startDate &&
    !!endDate &&
    !!timeframe &&
    Number.isFinite(parseFloat(slippagePct)) &&
    parseFloat(slippagePct) >= 0 &&
    new Date(startDate).getTime() <= new Date(endDate).getTime();

  const handleSubmit = async () => {
    if (!valid || !profileId) return;
    const profile = activeProfiles.find((p) => p.profile_id === profileId);
    if (!profile) {
      toast.error("Selected profile not found.");
      return;
    }
    setSubmitting(true);
    try {
      const res = await api.backtest.submit({
        symbol,
        strategy_rules: profile.rules_json,
        start_date: `${startDate}T00:00:00`,
        end_date: `${endDate}T00:00:00`,
        timeframe,
        slippage_pct: parseFloat(slippagePct),
      });
      onSubmit({
        jobId: res.job_id,
        profileId,
        symbol,
        startDate,
        endDate,
        timeframe,
        status: (res.status as "queued" | "running") ?? "queued",
      });
    } catch (e: unknown) {
      toast.error(e instanceof Error ? e.message : "Failed to start backtest.");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-labelledby="new-backtest-title"
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 px-4"
      onClick={(e) => {
        if (e.target === e.currentTarget) onCancel();
      }}
    >
      <div className="w-full max-w-xl rounded-lg border border-border-subtle bg-bg-panel shadow-lg">
        <header className="flex items-center justify-between gap-4 px-5 py-4 border-b border-border-subtle">
          <h2 id="new-backtest-title" className="text-[15px] font-semibold text-fg">
            New backtest
          </h2>
          <button
            type="button"
            onClick={onCancel}
            aria-label="Close"
            className="text-fg-muted hover:text-fg p-1 rounded-sm focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent-500"
          >
            <X className="w-4 h-4" strokeWidth={1.5} aria-hidden />
          </button>
        </header>

        <div className="px-5 py-5 flex flex-col gap-4">
          <Select
            label="Profile"
            options={profileOptions}
            value={profileId}
            onValueChange={setProfileId}
            density="comfortable"
            placeholder={
              activeProfiles.length === 0
                ? "No profiles — create one in Canvas"
                : "Select…"
            }
            searchable
            disabled={activeProfiles.length === 0}
            hint="Backtest runs against the profile's saved canonical rules."
          />

          <Input
            label="Symbol"
            density="comfortable"
            placeholder="BTC/USDT"
            value={symbol}
            onChange={(e) => setSymbol(e.target.value.toUpperCase())}
            mono
            hint="Single symbol. Multi-symbol runs are pending (see below)."
          />

          <div className="grid grid-cols-2 gap-3">
            <Input
              label="Start date"
              type="date"
              density="comfortable"
              value={startDate}
              onChange={(e) => setStartDate(e.target.value)}
            />
            <Input
              label="End date"
              type="date"
              density="comfortable"
              value={endDate}
              onChange={(e) => setEndDate(e.target.value)}
            />
          </div>

          <div className="grid grid-cols-2 gap-3">
            <Select
              label="Timeframe"
              options={TIMEFRAMES}
              value={timeframe}
              onValueChange={setTimeframe}
              density="comfortable"
            />
            <Input
              label="Slippage (%)"
              density="comfortable"
              type="number"
              numeric
              min={0}
              max={5}
              step={0.0005}
              value={slippagePct}
              onChange={(e) => setSlippagePct(e.target.value)}
              hint="Per-trade fractional slippage (0.001 = 0.1%)."
            />
          </div>

          <div className="rounded-md border border-warn-700/40 bg-warn-700/10 px-4 py-3 flex items-start gap-3">
            <Info className="w-4 h-4 text-warn-400 shrink-0 mt-0.5" strokeWidth={1.5} aria-hidden />
            <div className="flex-1 text-[12px] text-warn-400/90 leading-relaxed">
              <p className="font-medium text-warn-400">
                Spec calls for richer config that isn&apos;t wired yet.
              </p>
              <p className="text-warn-400/70 mt-1">
                Multi-symbol, named slippage models (e.g. realistic-with-impact),
                fee profiles per venue, walk-forward windows, and multi-symbol
                weighting need backend additions before the modal can pass them.
                The current API takes a single symbol + numeric slippage and
                fee assumptions baked into the simulator.
              </p>
              <div className="mt-2 flex flex-wrap gap-1.5">
                <Tag intent="warn">Multi-symbol</Tag>
                <Tag intent="warn">Slippage models</Tag>
                <Tag intent="warn">Fees</Tag>
                <Tag intent="warn">Walk-forward</Tag>
                <Tag intent="warn">Random seed</Tag>
                <Tag intent="warn">Weighting</Tag>
              </div>
            </div>
          </div>
        </div>

        <footer className="flex items-center justify-end gap-2 px-5 py-3 border-t border-border-subtle">
          <Button intent="secondary" size="md" onClick={onCancel}>
            Cancel
          </Button>
          <Button
            intent="primary"
            size="md"
            leftIcon={<Play className="w-3.5 h-3.5" />}
            onClick={handleSubmit}
            disabled={!valid}
            loading={submitting}
          >
            Run
          </Button>
        </footer>
      </div>
    </div>
  );
}
