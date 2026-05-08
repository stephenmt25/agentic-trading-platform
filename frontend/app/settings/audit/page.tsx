"use client";

import { useMemo, useState } from "react";
import { Download, Search } from "lucide-react";
import { Button, Input, Select, Tag, type SelectOption } from "@/components/primitives";
import { Pill } from "@/components/data-display";

const EVENT_TYPES: SelectOption[] = [
  { value: "all", label: "All events" },
  { value: "profile", label: "Profile changes" },
  { value: "kill_switch", label: "Kill-switch transitions" },
  { value: "api_key", label: "API key rotations" },
  { value: "override", label: "Agent overrides" },
  { value: "auth_fail", label: "Failed sign-ins" },
];

interface AuditEvent {
  id: string;
  type: string;
  description: string;
  actor: string;
  timestamp: string;
}

/**
 * /settings/audit — read-only event log. Per surface spec §10.
 *
 * The user-action audit feed (profile edits, kill-switch transitions,
 * API-key rotations, override events, failed auth) needs a backend
 * audit_events table that doesn't exist yet. The page renders filters,
 * empty state, and CSV export to spec; the data hookup waits on the
 * audit-events endpoint.
 *
 * The closed-trades ledger surfaced under api.audit.closedTrades is
 * trade-side audit, not user-action — it lives in Backtesting and
 * trade reports, not here.
 */
export default function AuditLogPage() {
  const [eventType, setEventType] = useState("all");
  const [from, setFrom] = useState("");
  const [to, setTo] = useState("");

  const events: AuditEvent[] = useMemo(() => [], []);
  const hasFilters = eventType !== "all" || !!from || !!to;

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

      <div className="rounded-lg border border-warn-700/40 bg-warn-700/10 px-5 py-4 flex items-start gap-3">
        <Pill intent="warn">Pending</Pill>
        <div className="flex-1 text-[13px] text-warn-400/90">
          <p className="font-medium text-warn-400">
            User-action audit events aren&apos;t persisted yet.
          </p>
          <p className="mt-1 text-warn-400/70">
            The endpoint backing this surface is the next item on the audit
            schema. Until then, the filter bar and empty state below match the
            target shape so wiring is mechanical when it lands.
          </p>
        </div>
      </div>

      <div className="rounded-lg border border-border-subtle bg-bg-panel p-4 flex flex-col gap-4">
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
          <Select
            label="Event type"
            options={EVENT_TYPES}
            value={eventType}
            onValueChange={setEventType}
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
            {hasFilters ? "Filters applied." : "Showing all event types."}
          </p>
          <Button
            intent="secondary"
            size="md"
            leftIcon={<Download className="w-3.5 h-3.5" />}
            disabled
          >
            Export CSV
          </Button>
        </div>
      </div>

      <div className="rounded-md border border-border-subtle bg-bg-panel/60 p-10 text-center">
        <Search className="w-5 h-5 text-fg-muted mx-auto" strokeWidth={1.5} aria-hidden />
        <p className="text-fg mt-3">
          {events.length === 0 && hasFilters
            ? "No audit events recorded for this date range."
            : "No audit events recorded."}
        </p>
        <p className="text-[13px] text-fg-muted mt-1">
          Events appear here as they accrue — never mutable from the UI.
        </p>
      </div>

      <div className="flex flex-col gap-2">
        <h2 className="text-[14px] font-semibold text-fg">What gets recorded</h2>
        <ul className="rounded-lg border border-border-subtle bg-bg-panel divide-y divide-border-subtle">
          <RecordedRow
            type="Profile changes"
            description="Created, edited (with field-level diff), or archived."
          />
          <RecordedRow
            type="Kill-switch transitions"
            description="Off → soft → hard with reason and actor."
          />
          <RecordedRow
            type="API key rotations"
            description="Add, revoke, and successful test of exchange keys."
          />
          <RecordedRow
            type="Agent overrides"
            description="When you intervene on an agent's recommendation in Observatory."
          />
          <RecordedRow
            type="Failed sign-ins"
            description="Authentication attempts that the OAuth provider rejected."
          />
        </ul>
      </div>
    </section>
  );
}

function RecordedRow({
  type,
  description,
}: {
  type: string;
  description: string;
}) {
  return (
    <li className="flex items-start justify-between gap-4 px-4 py-3">
      <div className="min-w-0 flex-1">
        <p className="text-[14px] text-fg">{type}</p>
        <p className="text-[12px] text-fg-muted mt-0.5">{description}</p>
      </div>
      <Tag intent="neutral">Recorded</Tag>
    </li>
  );
}
