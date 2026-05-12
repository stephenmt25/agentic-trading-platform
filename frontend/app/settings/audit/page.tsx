"use client";

import { useEffect, useMemo, useState } from "react";
import { Download, Search, AlertTriangle } from "lucide-react";
import { toast } from "sonner";
import { Button, Input, Select, Tag, type SelectOption } from "@/components/primitives";
import { Pill } from "@/components/data-display";
import { api } from "@/lib/api/client";

const EVENT_TYPES: SelectOption[] = [
  { value: "all", label: "All events" },
  { value: "kill_switch", label: "Kill-switch transitions" },
  { value: "profile", label: "Profile changes" },
  { value: "api_key", label: "API key rotations" },
  { value: "override", label: "Agent overrides" },
  { value: "auth_fail", label: "Failed sign-ins" },
];

type EventTypeKey = "all" | "kill_switch" | "profile" | "api_key" | "override" | "auth_fail";

interface AuditEvent {
  id: string;
  type: string;
  description: string;
  actor: string;
  timestamp_ms: number;
}

const TYPE_LABEL: Record<string, string> = {
  kill_switch: "Kill switch",
  profile: "Profile",
  api_key: "API key",
  override: "Override",
  auth_fail: "Sign-in",
};

const POLL_MS = 30_000;

/**
 * /settings/audit — read-only user-action event log.
 * Surface spec: docs/design/05-surface-specs/06-profiles-settings.md §10.
 *
 * Wired against api.audit.userEvents (services/api_gateway/src/routes/audit.py).
 * Today's source: kill-switch transitions from Redis. Profile changes,
 * API-key rotations, agent overrides, and failed sign-ins are spec'd but
 * their sources don't emit yet — the page tags those in "What gets
 * recorded" with their reason; the response shape stays stable so each
 * source flips from Pending to Recorded as it lands.
 */
export default function AuditLogPage() {
  const [eventType, setEventType] = useState<EventTypeKey>("all");
  const [from, setFrom] = useState("");
  const [to, setTo] = useState("");

  const [events, setEvents] = useState<AuditEvent[]>([]);
  const [availableTypes, setAvailableTypes] = useState<Set<string>>(new Set());
  const [pendingTypes, setPendingTypes] = useState<Set<string>>(new Set());
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    const tick = () => {
      const fromMs = from ? Date.parse(from) : undefined;
      // Inclusive end-of-day for the upper bound — without this the user's
      // 'to' selection of e.g. 2026-05-10 only matches events at midnight.
      const toMs = to ? Date.parse(to) + 86_400_000 - 1 : undefined;
      api.audit
        .userEvents({
          type: eventType,
          from: Number.isFinite(fromMs) ? fromMs : undefined,
          to: Number.isFinite(toMs) ? toMs : undefined,
          limit: 200,
        })
        .then((res) => {
          if (cancelled) return;
          setEvents(res.events);
          setAvailableTypes(new Set(res.available_types));
          setPendingTypes(new Set(res.pending_types));
          setError(null);
        })
        .catch((e: unknown) => {
          if (cancelled) return;
          setError(e instanceof Error ? e.message : "Failed to load audit events");
        })
        .finally(() => {
          if (!cancelled) setLoading(false);
        });
    };
    tick();
    const id = window.setInterval(tick, POLL_MS);
    return () => {
      cancelled = true;
      window.clearInterval(id);
    };
  }, [eventType, from, to]);

  const hasFilters = eventType !== "all" || !!from || !!to;
  const allPendingTypeFiltered =
    eventType !== "all" && pendingTypes.has(eventType);

  const exportCsv = useMemo(
    () => () => {
      if (events.length === 0) {
        toast.info("Nothing to export.");
        return;
      }
      const header = "timestamp,type,description,actor";
      const rows = events.map((e) =>
        [
          new Date(e.timestamp_ms).toISOString(),
          e.type,
          JSON.stringify(e.description),
          JSON.stringify(e.actor),
        ].join(",")
      );
      const csv = [header, ...rows].join("\n");
      const blob = new Blob([csv], { type: "text/csv" });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `audit-events-${new Date().toISOString().slice(0, 10)}.csv`;
      a.click();
      URL.revokeObjectURL(url);
    },
    [events]
  );

  return (
    <section className="flex flex-col gap-6">
      <header className="flex flex-col gap-1">
        <h1 className="text-[22px] font-semibold tracking-tight text-fg">
          Audit log
        </h1>
        <p className="text-fg-secondary">
          Significant account events. Read-only. Filterable by type and date
          range. Exportable as CSV for compliance archives.
        </p>
      </header>

      {error && (
        <div role="alert" className="rounded-lg border border-danger-700/40 bg-danger-700/10 px-5 py-4 flex items-start gap-3 text-[13px] text-danger-500">
          <AlertTriangle className="w-4 h-4 shrink-0 mt-0.5" strokeWidth={1.5} aria-hidden />
          <div>
            <p className="font-medium">Audit feed unreachable</p>
            <p className="text-danger-500/80 mt-1">{error}</p>
          </div>
        </div>
      )}

      {pendingTypes.size > 0 && (
        <div className="rounded-lg border border-warn-700/40 bg-warn-700/10 px-5 py-4 flex items-start gap-3">
          <Pill intent="warn">Partial</Pill>
          <div className="flex-1 text-[13px] text-warn-400/90">
            <p className="font-medium text-warn-400">
              {availableTypes.size} of {availableTypes.size + pendingTypes.size} event sources are wired.
            </p>
            <p className="mt-1 text-warn-400/70">
              Pending sources ({[...pendingTypes].join(", ")}) will start
              appearing here as their producers land — no UI change needed.
            </p>
          </div>
        </div>
      )}

      <div className="rounded-lg border border-border-subtle bg-bg-panel p-4 flex flex-col gap-4">
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
          <Select
            label="Event type"
            options={EVENT_TYPES}
            value={eventType}
            onValueChange={(v) => setEventType(v as EventTypeKey)}
            density="comfortable"
          />
          <Input
            label="From"
            type="date"
            density="comfortable"
            value={from}
            onChange={(e) => setFrom(e.target.value)}
          />
          <Input
            label="To"
            type="date"
            density="comfortable"
            value={to}
            onChange={(e) => setTo(e.target.value)}
          />
        </div>
        <div className="flex flex-wrap items-center justify-between gap-3 pt-3 border-t border-border-subtle">
          <p className="text-[12px] text-fg-muted">
            {loading
              ? "Loading…"
              : `${events.length} event${events.length === 1 ? "" : "s"}${hasFilters ? " (filtered)" : ""}`}
          </p>
          <Button
            intent="secondary"
            size="md"
            leftIcon={<Download className="w-3.5 h-3.5" />}
            onClick={exportCsv}
            disabled={events.length === 0}
          >
            Export CSV
          </Button>
        </div>
      </div>

      {events.length === 0 ? (
        <div className="rounded-md border border-border-subtle bg-bg-panel/60 p-10 text-center">
          <Search className="w-5 h-5 text-fg-muted mx-auto" strokeWidth={1.5} aria-hidden />
          <p className="text-fg mt-3">
            {allPendingTypeFiltered
              ? "This event type is spec'd but its source doesn't emit yet."
              : hasFilters
                ? "No audit events recorded for this filter."
                : "No audit events recorded."}
          </p>
          <p className="text-[13px] text-fg-muted mt-1">
            Events appear here as they accrue — never mutable from the UI.
          </p>
        </div>
      ) : (
        <ul className="rounded-lg border border-border-subtle bg-bg-panel divide-y divide-border-subtle">
          {events.map((e) => (
            <li
              key={e.id}
              className="px-4 py-3 flex items-start gap-3 text-[13px]"
            >
              <Tag intent="neutral" className="shrink-0 mt-0.5">
                {TYPE_LABEL[e.type] ?? e.type}
              </Tag>
              <div className="min-w-0 flex-1">
                <p className="text-fg">{e.description}</p>
                <p className="text-[11px] text-fg-muted mt-0.5 num-tabular font-mono">
                  {new Date(e.timestamp_ms).toLocaleString()} · by{" "}
                  <span className="text-fg-secondary">{e.actor}</span>
                </p>
              </div>
            </li>
          ))}
        </ul>
      )}

      <div className="flex flex-col gap-2">
        <h2 className="text-[14px] font-semibold text-fg">What gets recorded</h2>
        <ul className="rounded-lg border border-border-subtle bg-bg-panel divide-y divide-border-subtle">
          <RecordedRow
            type="Kill-switch transitions"
            description="Off → soft → hard with reason and actor."
            recorded={availableTypes.has("kill_switch")}
          />
          <RecordedRow
            type="Profile changes"
            description="Created, edited (with field-level diff), or archived."
            recorded={availableTypes.has("profile")}
          />
          <RecordedRow
            type="API key rotations"
            description="Add, revoke, and successful test of exchange keys."
            recorded={availableTypes.has("api_key")}
          />
          <RecordedRow
            type="Agent overrides"
            description="When you intervene on an agent's recommendation in Observatory."
            recorded={availableTypes.has("override")}
          />
          <RecordedRow
            type="Failed sign-ins"
            description="Authentication attempts that the OAuth provider rejected."
            recorded={availableTypes.has("auth_fail")}
          />
        </ul>
      </div>
    </section>
  );
}

function RecordedRow({
  type,
  description,
  recorded,
}: {
  type: string;
  description: string;
  recorded: boolean;
}) {
  return (
    <li className="flex items-start justify-between gap-4 px-4 py-3">
      <div className="min-w-0 flex-1">
        <p className="text-[14px] text-fg">{type}</p>
        <p className="text-[12px] text-fg-muted mt-0.5">{description}</p>
      </div>
      {recorded ? (
        <Tag intent="bid">Recorded</Tag>
      ) : (
        <Tag intent="warn">Pending</Tag>
      )}
    </li>
  );
}
