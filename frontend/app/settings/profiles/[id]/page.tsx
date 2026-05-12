"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import {
  ArrowLeft,
  Save,
  Power,
  PowerOff,
  Trash2,
  CheckCircle2,
  AlertTriangle,
  ArrowRight,
} from "lucide-react";
import { toast } from "sonner";
import { Button, Input, Tag, Toggle, Tooltip } from "@/components/primitives";
import { Pill, StatusDot } from "@/components/data-display";
import { cn } from "@/lib/utils";
import { api, type ProfileResponse } from "@/lib/api/client";
import { formatDateTime, formatRelative } from "../_lib/format";

const RISK_DEFAULTS = {
  max_allocation_pct: 1.0,
  stop_loss_pct: 0.05,
  take_profit_pct: 0.015,
  max_drawdown_pct: 0.1,
  circuit_breaker_daily_loss_pct: 0.02,
  max_holding_hours: 48.0,
} as const;

type RiskKey = keyof typeof RISK_DEFAULTS;

interface RiskFieldDef {
  key: RiskKey;
  label: string;
  help: string;
  isPct: boolean;
  min: number;
  max: number;
  step: number;
}

const RISK_FIELDS: RiskFieldDef[] = [
  {
    key: "max_allocation_pct",
    label: "Max trade size",
    help: "Per-trade cap as % of free capital × signal confidence.",
    isPct: true,
    min: 1,
    max: 100,
    step: 1,
  },
  {
    key: "stop_loss_pct",
    label: "Stop loss",
    help: "Auto-close on this loss vs. entry.",
    isPct: true,
    min: 0.1,
    max: 50,
    step: 0.1,
  },
  {
    key: "take_profit_pct",
    label: "Take profit",
    help: "Auto-close on this gain vs. entry.",
    isPct: true,
    min: 0.1,
    max: 50,
    step: 0.1,
  },
  {
    key: "max_drawdown_pct",
    label: "Max drawdown",
    help: "Block new trades when peak-to-trough loss exceeds this.",
    isPct: true,
    min: 1,
    max: 50,
    step: 0.5,
  },
  {
    key: "circuit_breaker_daily_loss_pct",
    label: "Daily loss kill",
    help: "Halt trading when realised daily loss exceeds this fraction.",
    isPct: true,
    min: 0.1,
    max: 50,
    step: 0.1,
  },
  {
    key: "max_holding_hours",
    label: "Max hold (hours)",
    help: "Force-close any position held longer than this.",
    isPct: false,
    min: 0.5,
    max: 720,
    step: 0.5,
  },
];

function readNumber(rl: Record<string, unknown>, key: string, fallback: number): number {
  const v = rl[key];
  if (typeof v === "number" && Number.isFinite(v)) return v;
  if (typeof v === "string") {
    const parsed = parseFloat(v);
    return Number.isFinite(parsed) ? parsed : fallback;
  }
  return fallback;
}

interface FormState {
  name: string;
  is_active: boolean;
  allocation_pct: number;
  risk: Record<RiskKey, number>;
}

function fromProfile(p: ProfileResponse): FormState {
  const rl = (p.risk_limits ?? {}) as Record<string, unknown>;
  return {
    name: p.name,
    is_active: p.is_active,
    allocation_pct: typeof p.allocation_pct === "number" ? p.allocation_pct : 1.0,
    risk: {
      max_allocation_pct: readNumber(rl, "max_allocation_pct", RISK_DEFAULTS.max_allocation_pct),
      stop_loss_pct: readNumber(rl, "stop_loss_pct", RISK_DEFAULTS.stop_loss_pct),
      take_profit_pct: readNumber(rl, "take_profit_pct", RISK_DEFAULTS.take_profit_pct),
      max_drawdown_pct: readNumber(rl, "max_drawdown_pct", RISK_DEFAULTS.max_drawdown_pct),
      circuit_breaker_daily_loss_pct: readNumber(
        rl,
        "circuit_breaker_daily_loss_pct",
        RISK_DEFAULTS.circuit_breaker_daily_loss_pct
      ),
      max_holding_hours: readNumber(rl, "max_holding_hours", RISK_DEFAULTS.max_holding_hours),
    },
  };
}

function isEqual(a: FormState, b: FormState): boolean {
  if (a.name !== b.name || a.is_active !== b.is_active) return false;
  if (a.allocation_pct !== b.allocation_pct) return false;
  for (const k of Object.keys(a.risk) as RiskKey[]) {
    if (a.risk[k] !== b.risk[k]) return false;
  }
  return true;
}

/**
 * /settings/profiles/[id] — per-profile editor.
 *
 * Sections per surface spec §3:
 *   - Identity (name, profile id, status)
 *   - Risk overrides (subset of risk defaults the user can override)
 *   - Symbols whitelist, schedule, auto-pause triggers (deferred —
 *     no schema for these yet; surface explains)
 *   - Audit history (deferred — no per-profile audit feed yet)
 *
 * Save model per §11: explicit Save, ✓ Saved indicator, unsaved-changes
 * banner. Pipeline structure edits live in the Canvas (§3 split).
 */
export default function ProfileDetailPage() {
  const router = useRouter();
  const params = useParams<{ id: string }>();
  const profileId = decodeURIComponent(params.id);

  const [profile, setProfile] = useState<ProfileResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [form, setForm] = useState<FormState | null>(null);
  const [pristine, setPristine] = useState<FormState | null>(null);
  const [saving, setSaving] = useState(false);
  const [savedAt, setSavedAt] = useState<number | null>(null);
  const [showDelete, setShowDelete] = useState(false);

  const dirty = useMemo(
    () => (form && pristine ? !isEqual(form, pristine) : false),
    [form, pristine]
  );

  const load = useCallback(() => {
    setLoading(true);
    setError(null);
    return api.profiles
      .list()
      .then((all) => {
        const p = all.find((x) => x.profile_id === profileId);
        if (!p) {
          setError(`Profile "${profileId}" not found.`);
          setProfile(null);
          setForm(null);
          setPristine(null);
          return;
        }
        setProfile(p);
        const next = fromProfile(p);
        setForm(next);
        setPristine(next);
      })
      .catch((e: unknown) => {
        const msg = e instanceof Error ? e.message : "Failed to load profile";
        if (!msg.includes("Unauthorized")) setError(msg);
      })
      .finally(() => setLoading(false));
  }, [profileId]);

  useEffect(() => {
    load();
  }, [load]);

  // Browser back / refresh / tab close warning while dirty.
  useEffect(() => {
    if (!dirty) return;
    const handler = (e: BeforeUnloadEvent) => {
      e.preventDefault();
      e.returnValue = "";
    };
    window.addEventListener("beforeunload", handler);
    return () => window.removeEventListener("beforeunload", handler);
  }, [dirty]);

  // Auto-fade the ✓ Saved indicator after 4s.
  useEffect(() => {
    if (!savedAt) return;
    const t = window.setTimeout(() => setSavedAt(null), 4000);
    return () => window.clearTimeout(t);
  }, [savedAt]);

  const handleSave = useCallback(async () => {
    if (!profile || !form) return;
    setSaving(true);
    try {
      await api.profiles.update(profile.profile_id, {
        rules_json: profile.rules_json,
        is_active: form.is_active,
        risk_limits: form.risk,
        allocation_pct: form.allocation_pct,
      });
      toast.success("Profile saved");
      setSavedAt(Date.now());
      // Reload to capture canonical server state.
      await load();
    } catch (e: unknown) {
      toast.error(e instanceof Error ? e.message : "Failed to save profile");
    } finally {
      setSaving(false);
    }
  }, [profile, form, load]);

  const handleDelete = useCallback(async () => {
    if (!profile) return;
    try {
      await api.profiles.delete(profile.profile_id);
      toast.success("Profile archived.");
      router.push("/settings/profiles");
    } catch (e: unknown) {
      toast.error(e instanceof Error ? e.message : "Failed to delete profile");
    }
  }, [profile, router]);

  const handleNavBack = useCallback(() => {
    if (dirty) {
      const ok = window.confirm("You have unsaved changes. Discard them?");
      if (!ok) return;
    }
    router.push("/settings/profiles");
  }, [dirty, router]);

  if (loading) return <DetailSkeleton />;
  if (error)
    return (
      <ErrorState
        title="Could not load profile."
        message={error}
        onRetry={() => load()}
      />
    );
  if (!profile || !form) return null;

  const isDeleted = !!profile.deleted_at;

  return (
    <section className="flex flex-col gap-6">
      <header className="flex flex-col gap-3">
        <button
          type="button"
          onClick={handleNavBack}
          className="self-start inline-flex items-center gap-1.5 text-[13px] text-fg-muted hover:text-fg transition-colors focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent-500 rounded-sm"
        >
          <ArrowLeft className="w-3.5 h-3.5" strokeWidth={1.5} aria-hidden />
          All profiles
        </button>

        <div className="flex items-start justify-between gap-4">
          <div className="min-w-0">
            <h1 className="text-[22px] font-semibold tracking-tight text-fg truncate">
              {profile.name || profile.profile_id}
            </h1>
            <p className="text-[13px] text-fg-muted mt-1 font-mono">
              {profile.profile_id}
            </p>
          </div>
          {isDeleted ? (
            <Pill intent="ask">Deleted</Pill>
          ) : profile.is_active ? (
            <Pill intent="bid" icon={<StatusDot state="live" size={6} pulse />}>
              Live
            </Pill>
          ) : (
            <Pill intent="neutral" icon={<StatusDot state="idle" size={6} />}>
              Dormant
            </Pill>
          )}
        </div>
      </header>

      {dirty && !isDeleted && (
        <div
          role="status"
          className="rounded-md border border-warn-700/50 bg-warn-700/10 px-4 py-3 text-[13px] text-warn-400 flex items-center gap-3"
        >
          <AlertTriangle className="w-4 h-4 shrink-0" strokeWidth={1.5} aria-hidden />
          <span>Unsaved changes. Save to apply, or navigate away to discard.</span>
        </div>
      )}

      {savedAt && !dirty && (
        <div
          role="status"
          className="rounded-md border border-bid-700/50 bg-bid-900/20 px-4 py-3 text-[13px] text-bid-300 flex items-center gap-3"
        >
          <CheckCircle2 className="w-4 h-4 shrink-0" strokeWidth={1.5} aria-hidden />
          <span>Saved.</span>
        </div>
      )}

      {isDeleted && (
        <div
          role="status"
          className="rounded-md border border-ask-700/40 bg-ask-900/15 px-4 py-3 text-[13px] text-ask-300"
        >
          This profile is archived. Configuration is read-only.
        </div>
      )}

      {/* Identity */}
      <FieldGroup
        title="Identity"
        description="The user-facing name. The profile ID is immutable."
      >
        <Input
          label="Display name"
          density="comfortable"
          value={form.name}
          onChange={(e) => setForm({ ...form, name: e.target.value })}
          disabled={isDeleted}
        />
        <Input
          label="Profile ID"
          density="comfortable"
          value={profile.profile_id}
          mono
          disabled
          hint="Generated at creation. Used in canvas URLs and audit logs."
        />
      </FieldGroup>

      {/* Status */}
      <FieldGroup
        title="Status"
        description="Activate to let live trading execute against this profile. Deactivating halts new orders without affecting open positions."
      >
        <div className="flex items-center justify-between rounded-md border border-border-subtle bg-bg-panel px-4 py-3">
          <div className="flex items-center gap-3">
            {form.is_active ? (
              <Power className="w-4 h-4 text-bid-400" strokeWidth={1.5} aria-hidden />
            ) : (
              <PowerOff className="w-4 h-4 text-fg-muted" strokeWidth={1.5} aria-hidden />
            )}
            <div>
              <p className="text-[14px] text-fg">
                {form.is_active ? "Active" : "Inactive"}
              </p>
              <p className="text-[12px] text-fg-muted">
                Toggle on to allow new orders for this profile.
              </p>
            </div>
          </div>
          <Toggle
            checked={form.is_active}
            onCheckedChange={(next) => setForm({ ...form, is_active: next })}
            disabled={isDeleted}
            label="Active"
          />
        </div>
      </FieldGroup>

      {/* Risk overrides */}
      <FieldGroup
        title="Risk overrides"
        description="Subset of user-level risk defaults overridable per profile. Saved values are merged server-side; siblings keep their existing values."
      >
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          {RISK_FIELDS.map((f) => {
            const stored = form.risk[f.key];
            const display = f.isPct ? stored * 100 : stored;
            return (
              <Input
                key={f.key}
                label={f.label + (f.isPct ? " (%)" : "")}
                hint={f.help}
                density="comfortable"
                type="number"
                numeric
                min={f.min}
                max={f.max}
                step={f.step}
                value={Number.isFinite(display) ? display : ""}
                onChange={(e) => {
                  const raw = parseFloat(e.target.value);
                  if (!Number.isFinite(raw)) return;
                  const fraction = f.isPct ? raw / 100 : raw;
                  setForm({
                    ...form,
                    risk: { ...form.risk, [f.key]: fraction },
                  });
                }}
                disabled={isDeleted}
              />
            );
          })}
          <Input
            label="Capital scale (×)"
            hint={`= $${(form.allocation_pct * 10000).toLocaleString(undefined, { maximumFractionDigits: 0 })} notional at $10,000 base.`}
            density="comfortable"
            type="number"
            numeric
            min={0.01}
            max={100}
            step={0.1}
            value={Number.isFinite(form.allocation_pct) ? form.allocation_pct : ""}
            onChange={(e) => {
              const v = parseFloat(e.target.value);
              if (Number.isFinite(v)) setForm({ ...form, allocation_pct: v });
            }}
            disabled={isDeleted}
          />
        </div>
      </FieldGroup>

      {/* Spec sections we don't have schema for yet */}
      <FieldGroup
        title="Symbols whitelist"
        description="Which symbols this profile is allowed to trade."
      >
        <DeferredField
          note="Symbols are currently sourced from rules_json.symbols. A first-class whitelist editor lands with the canvas symbol-bound source node."
        />
      </FieldGroup>

      <FieldGroup
        title="Schedule"
        description="Active hours and days for this profile."
      >
        <DeferredField note="Schedule editor is on the Phase 2 roadmap. Currently profiles run whenever they are Active." />
      </FieldGroup>

      <FieldGroup
        title="Auto-pause triggers"
        description="Conditions that automatically deactivate this profile (e.g., drawdown breach)."
      >
        <DeferredField note="Auto-pause triggers are evaluated server-side via the risk limits above (drawdown / daily loss kill). A user-defined trigger DSL is on the Phase 2 roadmap." />
      </FieldGroup>

      <FieldGroup
        title="Audit history"
        description="Significant changes to this profile."
      >
        <DeferredField note="Per-profile audit feed lands with the audit-log surface (see Audit log section). Today, change history is reconstructable only from the closed-trades ledger." />
      </FieldGroup>

      <FieldGroup
        title="Pipeline"
        description="The strategy graph for this profile is edited in the Canvas. Settings here apply alongside whatever the canvas evaluates."
      >
        <Link
          href={`/canvas/${encodeURIComponent(profile.profile_id)}`}
          className="inline-flex items-center justify-between gap-3 rounded-md border border-border-subtle bg-bg-panel px-4 py-3 hover:border-border-strong transition-colors focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent-500"
        >
          <span className="text-[14px] text-fg">Open in Pipeline Canvas</span>
          <ArrowRight className="w-4 h-4 text-fg-muted" strokeWidth={1.5} aria-hidden />
        </Link>
      </FieldGroup>

      {/* Sticky action footer */}
      <SaveBar
        dirty={dirty}
        saving={saving}
        disabled={isDeleted}
        savedRecently={!!savedAt && !dirty}
        onSave={handleSave}
        onDiscard={() => pristine && setForm(pristine)}
        onDelete={() => setShowDelete(true)}
        deleted={isDeleted}
        createdAt={profile.created_at}
      />

      {showDelete && (
        <DeleteDialog
          profileName={profile.name || profile.profile_id}
          onCancel={() => setShowDelete(false)}
          onConfirm={async () => {
            setShowDelete(false);
            await handleDelete();
          }}
        />
      )}
    </section>
  );
}

function FieldGroup({
  title,
  description,
  children,
}: {
  title: string;
  description?: string;
  children: React.ReactNode;
}) {
  return (
    <section className="flex flex-col gap-3 border-t border-border-subtle pt-6 first:border-t-0 first:pt-0">
      <header>
        <h2 className="text-[16px] font-semibold text-fg">{title}</h2>
        {description && (
          <p className="text-[13px] text-fg-secondary mt-1">{description}</p>
        )}
      </header>
      <div className="flex flex-col gap-4">{children}</div>
    </section>
  );
}

function DeferredField({ note }: { note: string }) {
  return (
    <div className="rounded-md border border-dashed border-border-subtle bg-bg-canvas/40 px-4 py-3">
      <div className="flex items-start gap-3">
        <Tag intent="warn">Pending</Tag>
        <p className="text-[13px] text-fg-secondary leading-snug flex-1">{note}</p>
      </div>
    </div>
  );
}

function SaveBar({
  dirty,
  saving,
  disabled,
  savedRecently,
  onSave,
  onDiscard,
  onDelete,
  deleted,
  createdAt,
}: {
  dirty: boolean;
  saving: boolean;
  disabled: boolean;
  savedRecently: boolean;
  onSave: () => void;
  onDiscard: () => void;
  onDelete: () => void;
  deleted: boolean;
  createdAt: string;
}) {
  return (
    <div
      className={cn(
        "sticky bottom-0 -mx-6 md:-mx-10 px-6 md:px-10 py-3",
        "bg-bg-canvas/95 backdrop-blur border-t border-border-subtle",
        "flex items-center justify-between gap-3"
      )}
    >
      <div className="text-[12px] text-fg-muted">
        Created {formatRelative(createdAt)}
        <span className="mx-2 text-fg-muted/40">·</span>
        <Tooltip content={formatDateTime(createdAt)}>
          <span className="num-tabular cursor-help">{formatDateTime(createdAt)}</span>
        </Tooltip>
      </div>
      <div className="flex items-center gap-2">
        {!deleted && (
          <Button intent="secondary" size="md" onClick={onDelete} leftIcon={<Trash2 className="w-3.5 h-3.5" />}>
            Archive
          </Button>
        )}
        {dirty && (
          <Button intent="secondary" size="md" onClick={onDiscard} disabled={saving}>
            Discard
          </Button>
        )}
        <Button
          intent="primary"
          size="md"
          onClick={onSave}
          disabled={disabled || !dirty}
          loading={saving}
          leftIcon={!saving && savedRecently ? <CheckCircle2 className="w-3.5 h-3.5" /> : <Save className="w-3.5 h-3.5" />}
        >
          {saving ? "Saving…" : savedRecently ? "Saved" : "Save changes"}
        </Button>
      </div>
    </div>
  );
}

function DeleteDialog({
  profileName,
  onCancel,
  onConfirm,
}: {
  profileName: string;
  onCancel: () => void;
  onConfirm: () => void;
}) {
  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-labelledby="delete-title"
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 px-4"
    >
      <div className="w-full max-w-md rounded-lg border border-border-subtle bg-bg-panel p-6">
        <h3 id="delete-title" className="text-[16px] font-semibold text-fg">
          Archive profile?
        </h3>
        <p className="text-[13px] text-fg-secondary mt-2">
          <span className="text-fg font-medium">{profileName}</span> will be
          deactivated and hidden. Open positions are not affected. The profile
          and its history remain queryable for audit.
        </p>
        <div className="mt-5 flex justify-end gap-2">
          <Button intent="secondary" size="md" onClick={onCancel}>
            Cancel
          </Button>
          <Button intent="danger" size="md" onClick={onConfirm}>
            Archive profile
          </Button>
        </div>
      </div>
    </div>
  );
}

function DetailSkeleton() {
  return (
    <div className="flex flex-col gap-6 animate-pulse-subtle" aria-label="Loading profile">
      <div className="h-3 w-24 bg-bg-raised/60 rounded" />
      <div className="h-7 w-72 bg-bg-raised rounded" />
      <div className="h-3 w-48 bg-bg-raised/60 rounded" />
      <div className="h-32 bg-bg-panel rounded-lg border border-border-subtle" />
      <div className="h-48 bg-bg-panel rounded-lg border border-border-subtle" />
    </div>
  );
}

function ErrorState({
  title,
  message,
  onRetry,
}: {
  title: string;
  message: string;
  onRetry: () => void;
}) {
  return (
    <div
      role="alert"
      className="rounded-md border border-danger-700/40 bg-danger-700/10 p-5 flex items-start gap-4"
    >
      <AlertTriangle className="w-5 h-5 text-danger-500 shrink-0 mt-0.5" strokeWidth={1.5} aria-hidden />
      <div className="flex-1">
        <p className="text-[14px] font-medium text-danger-500">{title}</p>
        <p className="text-[13px] text-fg-muted mt-1">{message}</p>
        <div className="mt-3 flex gap-2">
          <Button intent="secondary" size="sm" onClick={onRetry}>
            Retry
          </Button>
          <Link href="/settings/profiles">
            <Button intent="secondary" size="sm">
              Back to profiles
            </Button>
          </Link>
        </div>
      </div>
    </div>
  );
}
