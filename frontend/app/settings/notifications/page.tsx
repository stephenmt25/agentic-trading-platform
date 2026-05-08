"use client";

import { useEffect, useMemo, useState } from "react";
import { AlertTriangle, CheckCircle2, Save } from "lucide-react";
import { toast } from "sonner";
import { Button, Toggle, Tag } from "@/components/primitives";
import { cn } from "@/lib/utils";
import { api } from "@/lib/api/client";

interface Prefs {
  email_alerts: boolean;
  trade_notifications: boolean;
  default_exchange: string;
  timezone: string;
}

const DEFAULT_PREFS: Prefs = {
  email_alerts: true,
  trade_notifications: true,
  default_exchange: "binance",
  timezone:
    typeof Intl !== "undefined"
      ? Intl.DateTimeFormat().resolvedOptions().timeZone
      : "UTC",
};

/**
 * /settings/notifications — per-event delivery configuration.
 * Per surface spec §6.
 *
 * The backend currently exposes two coarse booleans (email_alerts,
 * trade_notifications). The full per-event matrix from the spec
 * (kill-switch transitions, large fills, override events × email /
 * push / audible) needs a richer schema before it can save. The page
 * surfaces what's wired and flags the rest as Pending — the spec's
 * anti-pattern of a "mega all-on/off toggle" is honored: each row is
 * its own switch.
 */
export default function NotificationsPage() {
  const [prefs, setPrefs] = useState<Prefs>(DEFAULT_PREFS);
  const [pristine, setPristine] = useState<Prefs>(DEFAULT_PREFS);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [savedAt, setSavedAt] = useState<number | null>(null);

  const dirty = useMemo(
    () =>
      prefs.email_alerts !== pristine.email_alerts ||
      prefs.trade_notifications !== pristine.trade_notifications,
    [prefs, pristine]
  );

  useEffect(() => {
    let cancelled = false;
    api.preferences
      .get()
      .then((p) => {
        if (cancelled) return;
        setPrefs(p);
        setPristine(p);
      })
      .catch(() => {
        // Backend may not have the endpoint yet — fall back to defaults.
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

  const handleSave = async () => {
    setSaving(true);
    try {
      await api.preferences.save(prefs);
      toast.success("Notification preferences saved.");
      setPristine(prefs);
      setSavedAt(Date.now());
    } catch (e: unknown) {
      toast.error(e instanceof Error ? e.message : "Failed to save preferences.");
    } finally {
      setSaving(false);
    }
  };

  return (
    <section className="flex flex-col gap-6">
      <header className="flex flex-col gap-1">
        <h1 className="text-[22px] font-semibold tracking-tight text-fg">
          Notifications
        </h1>
        <p className="text-fg-secondary">
          Choose which events surface where. Each event is configured separately
          — there is no global mute.
        </p>
      </header>

      {dirty && (
        <DirtyBanner />
      )}
      {savedAt && !dirty && <SavedBanner />}

      <div className="rounded-lg border border-border-subtle bg-bg-panel divide-y divide-border-subtle">
        <EventRow
          name="Daily summary email"
          description="A roll-up of fills, PnL, and significant agent events for the day."
          checked={prefs.email_alerts}
          onChange={(v) => setPrefs({ ...prefs, email_alerts: v })}
          disabled={loading}
          channel="email"
        />
        <EventRow
          name="Trade fills"
          description="Each executed order surfaces an in-app notification."
          checked={prefs.trade_notifications}
          onChange={(v) => setPrefs({ ...prefs, trade_notifications: v })}
          disabled={loading}
          channel="in-app"
        />
      </div>

      <div className="flex flex-col gap-3">
        <h2 className="text-[14px] font-semibold text-fg">Pending events</h2>
        <p className="text-[13px] text-fg-muted">
          The spec calls for richer per-event delivery (email × push × audible).
          The backend schema for these isn't wired yet — events below land when
          a preferences-matrix endpoint ships.
        </p>
        <ul className="rounded-lg border border-dashed border-border-subtle bg-bg-canvas/40 divide-y divide-border-subtle/60">
          <PendingEventRow name="Kill-switch state changes" reason="Critical-path event; should be high-signal in-app + audible." />
          <PendingEventRow name="Large fills (size threshold)" reason="Threshold UX needs a per-symbol spec." />
          <PendingEventRow name="Agent override events" reason="Sourced from the analyst service; needs a delivery schema." />
          <PendingEventRow name="Profile drawdown trigger" reason="Currently surfaced in Risk Control only." />
          <PendingEventRow name="Monthly tax report ready" reason="Pairs with the tax-export action under Tax." />
        </ul>
      </div>

      <SaveBar
        dirty={dirty}
        saving={saving}
        savedRecently={!!savedAt && !dirty}
        onSave={handleSave}
        onDiscard={() => setPrefs(pristine)}
      />
    </section>
  );
}

function EventRow({
  name,
  description,
  checked,
  onChange,
  disabled,
  channel,
}: {
  name: string;
  description: string;
  checked: boolean;
  onChange: (v: boolean) => void;
  disabled?: boolean;
  channel: "email" | "in-app" | "audible";
}) {
  const channelLabel =
    channel === "email" ? "Email" : channel === "in-app" ? "In-app" : "Audible";
  return (
    <div className="flex items-center justify-between gap-4 px-5 py-4">
      <div className="min-w-0 flex-1">
        <div className="flex items-center gap-2">
          <p className="text-[14px] text-fg">{name}</p>
          <Tag intent="neutral">{channelLabel}</Tag>
        </div>
        <p className="text-[12px] text-fg-muted mt-1">{description}</p>
      </div>
      <Toggle
        checked={checked}
        onCheckedChange={onChange}
        label={name}
        disabled={disabled}
      />
    </div>
  );
}

function PendingEventRow({ name, reason }: { name: string; reason: string }) {
  return (
    <li className="px-5 py-4 flex items-center justify-between gap-4">
      <div className="min-w-0 flex-1">
        <p className="text-[14px] text-fg">{name}</p>
        <p className="text-[12px] text-fg-muted mt-0.5">{reason}</p>
      </div>
      <Tag intent="warn">Pending</Tag>
    </li>
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
        leftIcon={savedRecently ? <CheckCircle2 className="w-3.5 h-3.5" /> : <Save className="w-3.5 h-3.5" />}
        loading={saving}
        disabled={!dirty}
        onClick={onSave}
      >
        {saving ? "Saving…" : savedRecently ? "Saved" : "Save changes"}
      </Button>
    </div>
  );
}
