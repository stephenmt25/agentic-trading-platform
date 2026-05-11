"use client";

import { useCallback, useState } from "react";
import { AlertTriangle, ArrowUp, ArrowDown, Check, X } from "lucide-react";

import { api } from "@/lib/api/client";
import { useHITLStore, type HITLRequest } from "@/lib/stores/hitlStore";
import { Button } from "@/components/primitives/Button";
import { cn } from "@/lib/utils";

/**
 * HITLApprovalCard — one pending human-in-the-loop approval row.
 *
 * Per Phase 8.1 GAP-2 / ADR-016: HITL lives on /agents/observatory next to the
 * DebatePanel-style override flow, not as a dedicated /approvals surface. This
 * card is the smallest unit the observatory page composes into a "Pending
 * Approvals" section above the agent telemetry stream.
 *
 * Visual contract:
 *   - intent="warn" border + tone for pending; intent="ok"/"danger" once resolved
 *     to give the user a 3-second visual confirmation before the row disappears.
 *   - Side is colored bid/ask (semantic), not by agent identity (ADR-012).
 *   - Confidence + per-agent scores rendered as compact monospace.
 *   - Reject prompts for an optional reason via a tiny inline textarea so the
 *     audit log gets a useful trail.
 */
export interface HITLApprovalCardProps {
  request: HITLRequest;
  embedded?: boolean;
}

const SIDE_TONE: Record<string, string> = {
  long: "text-bid-400",
  buy: "text-bid-400",
  short: "text-ask-400",
  sell: "text-ask-400",
};

const SIDE_ICON: Record<string, typeof ArrowUp> = {
  long: ArrowUp,
  buy: ArrowUp,
  short: ArrowDown,
  sell: ArrowDown,
};

export function HITLApprovalCard({ request, embedded = false }: HITLApprovalCardProps) {
  const { updateStatus, removeRequest } = useHITLStore();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [rejectMode, setRejectMode] = useState(false);
  const [reason, setReason] = useState("");

  const sideKey = request.side.toLowerCase();
  const SideIcon = SIDE_ICON[sideKey] ?? ArrowUp;

  const handleApprove = useCallback(async () => {
    setBusy(true);
    setError(null);
    try {
      await api.hitl.respond(request.event_id, "APPROVED");
      updateStatus(request.event_id, "APPROVED");
      window.setTimeout(() => removeRequest(request.event_id), 3000);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Approve failed");
    } finally {
      setBusy(false);
    }
  }, [request.event_id, updateStatus, removeRequest]);

  const handleReject = useCallback(async () => {
    setBusy(true);
    setError(null);
    try {
      await api.hitl.respond(
        request.event_id,
        "REJECTED",
        reason.trim() || "Manual rejection"
      );
      updateStatus(request.event_id, "REJECTED");
      window.setTimeout(() => removeRequest(request.event_id), 3000);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Reject failed");
    } finally {
      setBusy(false);
    }
  }, [request.event_id, reason, updateStatus, removeRequest]);

  const resolved = request.status === "APPROVED" || request.status === "REJECTED";
  const resolvedTone =
    request.status === "APPROVED"
      ? "border-bid-700 bg-bid-900/15"
      : request.status === "REJECTED"
        ? "border-ask-700 bg-ask-900/15"
        : "";

  return (
    <article
      data-status={request.status}
      role="region"
      aria-label={`HITL approval for ${request.symbol} ${request.side}`}
      className={cn(
        "rounded-md border bg-bg-panel flex flex-col gap-3 p-3",
        !resolved && "border-warn-700/50",
        resolved && resolvedTone,
        embedded && "shadow-none"
      )}
    >
      {/* Top row: side + symbol + size/price + confidence/floor */}
      <div className="flex items-baseline gap-3 flex-wrap">
        <div className={cn("inline-flex items-center gap-1 text-[13px] font-medium", SIDE_TONE[sideKey])}>
          <SideIcon className="w-3.5 h-3.5" strokeWidth={1.5} aria-hidden />
          {request.side.toUpperCase()}
        </div>
        <span className="text-[13px] font-mono text-fg num-tabular">{request.symbol}</span>
        <span className="text-[12px] text-fg-secondary num-tabular">
          {request.quantity.toFixed(4)} @ {request.price.toFixed(2)}
        </span>
        <span className="ml-auto text-[11px] text-fg-muted num-tabular">
          confidence{" "}
          <span className="text-fg">{(request.confidence * 100).toFixed(0)}%</span>
        </span>
      </div>

      {/* Trigger reason + risk context */}
      <div className="flex items-start gap-2 text-[12px] text-fg-secondary">
        <AlertTriangle className="w-3.5 h-3.5 text-warn-500 mt-0.5 shrink-0" strokeWidth={1.5} aria-hidden />
        <span>{request.trigger_reason}</span>
      </div>

      {/* Agent scores */}
      {Object.keys(request.agent_scores).length > 0 && (
        <div className="flex items-center gap-1.5 flex-wrap">
          {Object.entries(request.agent_scores).map(([name, data]) => {
            const tone =
              data.score > 0.3
                ? "text-bid-400"
                : data.score < -0.3
                  ? "text-ask-400"
                  : "text-fg-muted";
            return (
              <span
                key={name}
                className="inline-flex items-center gap-1.5 rounded-md border border-border-subtle bg-bg-canvas px-2 py-0.5 text-[11px]"
              >
                <span className="uppercase tracking-wide text-fg-muted">{name}</span>
                <span className={cn("font-mono num-tabular", tone)}>
                  {data.score >= 0 ? "+" : ""}{data.score.toFixed(2)}
                </span>
              </span>
            );
          })}
        </div>
      )}

      {/* Risk metrics row (compact) */}
      <div className="flex items-center gap-3 text-[11px] text-fg-muted num-tabular">
        <span>alloc <span className="text-fg-secondary">{(request.risk_metrics.allocation_pct * 100).toFixed(1)}%</span></span>
        <span>dd <span className="text-fg-secondary">{(request.risk_metrics.drawdown_pct * 100).toFixed(1)}%</span></span>
        <span>regime <span className="text-fg-secondary">{request.risk_metrics.regime}</span></span>
        <span>rsi <span className="text-fg-secondary">{request.risk_metrics.rsi.toFixed(1)}</span></span>
        <span>atr <span className="text-fg-secondary">{request.risk_metrics.atr.toFixed(2)}</span></span>
      </div>

      {/* Action row */}
      {!resolved && !rejectMode && (
        <div className="flex items-center gap-2">
          <Button
            size="sm"
            intent="primary"
            leftIcon={<Check className="w-3.5 h-3.5" strokeWidth={1.5} />}
            onClick={handleApprove}
            disabled={busy}
            data-testid={`hitl-approve-${request.event_id}`}
          >
            Approve
          </Button>
          <Button
            size="sm"
            intent="danger"
            leftIcon={<X className="w-3.5 h-3.5" strokeWidth={1.5} />}
            onClick={() => setRejectMode(true)}
            disabled={busy}
            data-testid={`hitl-reject-${request.event_id}`}
          >
            Reject
          </Button>
          {error && (
            <span role="alert" className="text-[11px] text-danger-500">
              {error}
            </span>
          )}
        </div>
      )}

      {/* Reject reason inline editor */}
      {!resolved && rejectMode && (
        <div className="flex flex-col gap-2">
          <textarea
            value={reason}
            onChange={(e) => setReason(e.target.value)}
            placeholder="Optional reason (logged to audit)"
            rows={2}
            className="rounded-md border border-border-subtle bg-bg-canvas px-2 py-1 text-[12px] text-fg placeholder:text-fg-muted focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent-500"
          />
          <div className="flex items-center gap-2">
            <Button size="sm" intent="danger" onClick={handleReject} disabled={busy}>
              Confirm reject
            </Button>
            <Button size="sm" intent="secondary" onClick={() => { setRejectMode(false); setReason(""); }} disabled={busy}>
              Cancel
            </Button>
            {error && (
              <span role="alert" className="text-[11px] text-danger-500">
                {error}
              </span>
            )}
          </div>
        </div>
      )}

      {resolved && (
        <p
          className={cn(
            "text-[11px] num-tabular",
            request.status === "APPROVED" ? "text-bid-400" : "text-ask-400"
          )}
        >
          {request.status === "APPROVED" ? "Approved" : "Rejected"} — closing in 3s
        </p>
      )}
    </article>
  );
}
