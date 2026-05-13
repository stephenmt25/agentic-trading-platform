"use client";

import { useEffect, useMemo, useState } from "react";
import { AlertTriangle, CheckCircle2, Info, Save } from "lucide-react";
import { toast } from "sonner";
import { Button, Input } from "@/components/primitives";
import { cn } from "@/lib/utils";
import { api } from "@/lib/api/client";

interface RiskDefaults {
  max_position_size_pct: number;
  max_leverage: number;
  max_daily_loss_pct: number;
  rate_limit_orders_per_min: number;
  auto_pause_drawdown_pct: number;
}

const FALLBACK_DEFAULTS: RiskDefaults = {
  max_position_size_pct: 0.10,
  max_leverage: 1.0,
  max_daily_loss_pct: 0.02,
  rate_limit_orders_per_min: 30,
  auto_pause_drawdown_pct: 0.05,
};

/**
 * /settings/risk — user-level risk defaults persisted via /risk-defaults.
 *
 * Scope: defaults apply to *newly created* profiles. The recompile fan-out
 * that propagates a save to running profiles is its own project and is
 * disclosed in the inline note below. Per surface spec §5.
 */
export default function RiskDefaultsPage() {
  const [values, setValues] = useState<RiskDefaults>(FALLBACK_DEFAULTS);
  const [pristine, setPristine] = useState<RiskDefaults>(FALLBACK_DEFAULTS);
  const [updatedAt, setUpdatedAt] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [savedAt, setSavedAt] = useState<number | null>(null);

  useEffect(() => {
    let cancelled = false;
    api.riskDefaults
      .get()
      .then((res) => {
        if (cancelled) return;
        setValues(res.defaults);
        setPristine(res.defaults);
        setUpdatedAt(res.updated_at);
      })
      .catch(() => {
        // Endpoint unreachable — fall back to canonical defaults so the form
        // still renders rather than blocking the user behind an error state.
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    if (!savedAt) return;
    const t = window.setTimeout(() => setSavedAt(null), 4000);
    return () => window.clearTimeout(t);
  }, [savedAt]);

  const dirty = useMemo(
    () =>
      values.max_position_size_pct !== pristine.max_position_size_pct ||
      values.max_leverage !== pristine.max_leverage ||
      values.max_daily_loss_pct !== pristine.max_daily_loss_pct ||
      values.rate_limit_orders_per_min !== pristine.rate_limit_orders_per_min ||
      values.auto_pause_drawdown_pct !== pristine.auto_pause_drawdown_pct,
    [values, pristine]
  );

  const handleSave = async () => {
    setSaving(true);
    try {
      const res = await api.riskDefaults.save(values);
      toast.success("Risk defaults saved.");
      setValues(res.defaults);
      setPristine(res.defaults);
      setUpdatedAt(res.updated_at);
      setSavedAt(Date.now());
    } catch (e: unknown) {
      toast.error(e instanceof Error ? e.message : "Failed to save risk defaults.");
    } finally {
      setSaving(false);
    }
  };

  return (
    <section className="flex flex-col gap-6">
      <header className="flex flex-col gap-1">
        <h1 className="text-[22px] font-semibold tracking-tight text-fg">
          Risk defaults
        </h1>
        <p className="text-fg-secondary">
          Caps that apply when a profile doesn&apos;t override them. Each value
          is a hard ceiling — the engine refuses orders that would breach it.
        </p>
      </header>

      <div className="rounded-lg border border-border-subtle bg-bg-panel/50 px-5 py-4 flex items-start gap-3">
        <Info className="w-4 h-4 text-accent-500 shrink-0 mt-0.5" strokeWidth={1.5} aria-hidden />
        <div className="flex-1 text-[13px] text-fg-secondary">
          <p className="text-fg">
            Defaults apply to newly created profiles.
          </p>
          <p className="mt-1 text-fg-muted">
            Propagation to <em>running</em> profiles (the recompile fan-out)
            ships in a follow-up. Existing profiles keep whatever caps they
            were created with until then. Per-profile overrides remain
            authoritative on each profile&apos;s settings page.
          </p>
        </div>
      </div>

      {dirty && <DirtyBanner />}
      {savedAt && !dirty && <SavedBanner />}

      <div className="rounded-lg border border-border-subtle bg-bg-panel p-5 grid grid-cols-1 sm:grid-cols-2 gap-x-6 gap-y-5">
        <PercentInput
          label="Max position size"
          hint="Per trade, fraction of free capital × signal confidence."
          value={values.max_position_size_pct}
          onChange={(v) => setValues({ ...values, max_position_size_pct: v })}
          disabled={loading}
          min={0}
          max={100}
        />
        <Input
          label="Max leverage"
          hint="Hard ceiling on notional / margin per position."
          numeric
          density="comfortable"
          value={values.max_leverage}
          onChange={(e) =>
            setValues({ ...values, max_leverage: Number(e.target.value) || 1 })
          }
          rightAdornment={<span className="text-[12px] font-medium">×</span>}
          disabled={loading}
          step="0.1"
          min={1}
          max={20}
        />
        <PercentInput
          label="Max daily loss"
          hint="Halts new orders for the rest of the day once breached."
          value={values.max_daily_loss_pct}
          onChange={(v) => setValues({ ...values, max_daily_loss_pct: v })}
          disabled={loading}
          min={0}
          max={100}
        />
        <Input
          label="Rate limit"
          hint="Sliding-window cap enforced by the rate_limiter service."
          numeric
          density="comfortable"
          value={values.rate_limit_orders_per_min}
          onChange={(e) =>
            setValues({
              ...values,
              rate_limit_orders_per_min: Number(e.target.value) || 1,
            })
          }
          rightAdornment={<span className="text-[12px] font-medium">/ min</span>}
          disabled={loading}
          step="1"
          min={1}
          max={600}
        />
        <PercentInput
          label="Auto-pause drawdown"
          hint="Trips when a profile's drawdown crosses this threshold."
          value={values.auto_pause_drawdown_pct}
          onChange={(v) => setValues({ ...values, auto_pause_drawdown_pct: v })}
          disabled={loading}
          min={0}
          max={100}
        />
      </div>

      <div className="text-[12px] text-fg-muted">
        {loading
          ? "Loading…"
          : updatedAt
            ? `Last saved ${new Date(updatedAt).toLocaleString()}.`
            : "No saved defaults yet. Showing canonical fallbacks."}
      </div>

      <SaveBar
        dirty={dirty}
        saving={saving}
        savedRecently={!!savedAt && !dirty}
        onSave={handleSave}
        onDiscard={() => setValues(pristine)}
      />
    </section>
  );
}

function PercentInput({
  label,
  hint,
  value,
  onChange,
  disabled,
  min,
  max,
}: {
  label: string;
  hint?: string;
  value: number;
  onChange: (v: number) => void;
  disabled?: boolean;
  min?: number;
  max?: number;
}) {
  // Stored as a fraction (0.10 = 10%); displayed as percent. Round to one
  // decimal place on input so typing doesn't flicker between 9.9 and 10.0.
  const displayed = Number((value * 100).toFixed(2));
  return (
    <Input
      label={label}
      hint={hint}
      numeric
      density="comfortable"
      value={displayed}
      onChange={(e) => {
        const next = Number(e.target.value);
        if (Number.isFinite(next)) onChange(next / 100);
      }}
      rightAdornment={<span className="text-[12px] font-medium">%</span>}
      disabled={disabled}
      step="0.5"
      min={min}
      max={max}
    />
  );
}

function DirtyBanner() {
  return (
    <div
      role="status"
      className="rounded-md border border-warn-700/50 bg-warn-700/10 px-4 py-3 text-[13px] text-warn-400 flex items-center gap-3"
    >
      <AlertTriangle className="w-4 h-4 shrink-0" strokeWidth={1.5} aria-hidden />
      <span>Unsaved changes. Save to apply, or discard.</span>
    </div>
  );
}

function SavedBanner() {
  return (
    <div
      role="status"
      className="rounded-md border border-bid-700/50 bg-bid-900/20 px-4 py-3 text-[13px] text-bid-300 flex items-center gap-3"
    >
      <CheckCircle2 className="w-4 h-4 shrink-0" strokeWidth={1.5} aria-hidden />
      <span>Saved.</span>
    </div>
  );
}

function SaveBar({
  dirty,
  saving,
  savedRecently,
  onSave,
  onDiscard,
}: {
  dirty: boolean;
  saving: boolean;
  savedRecently: boolean;
  onSave: () => void;
  onDiscard: () => void;
}) {
  return (
    <div
      className={cn(
        "sticky bottom-0 -mx-6 md:-mx-10 px-6 md:px-10 py-3",
        "bg-bg-canvas/95 backdrop-blur border-t border-border-subtle",
        "flex items-center justify-end gap-2"
      )}
    >
      {dirty && (
        <Button intent="secondary" size="md" onClick={onDiscard} disabled={saving}>
          Discard
        </Button>
      )}
      <Button
        intent="primary"
        size="md"
        leftIcon={
          savedRecently ? (
            <CheckCircle2 className="w-3.5 h-3.5" />
          ) : (
            <Save className="w-3.5 h-3.5" />
          )
        }
        loading={saving}
        disabled={!dirty}
        onClick={onSave}
      >
        {saving ? "Saving…" : savedRecently ? "Saved" : "Save changes"}
      </Button>
    </div>
  );
}
