"use client";

import { useCallback, useState } from "react";
import { signOut } from "next-auth/react";
import { AlertTriangle, Laptop, LogOut, Smartphone } from "lucide-react";
import { toast } from "sonner";
import { Button, Tag } from "@/components/primitives";
import { Pill, StatusDot } from "@/components/data-display";
import { api } from "@/lib/api/client";
import { useSessions } from "@/lib/api/hooks";

interface SessionRow {
  session_id: string;
  device: string | null;
  browser: string | null;
  ip: string | null;
  user_agent: string | null;
  created_at: string | null;
  last_seen_at: string | null;
  is_current: boolean;
}

/**
 * /settings/sessions — active sessions, API tokens, webhooks.
 * Per surface spec §9.
 *
 * Active sessions are wired against /auth/sessions (migration 022) via the
 * shared `useSessions` query (60s refetchInterval — FE-W2.1, no page-local
 * setInterval). API token issuance and webhook destinations are still
 * pending — those are their own projects, each surfaced explicitly here
 * with a short reason so the partner can see what's coming.
 */
export default function SessionsSettingsPage() {
  const [revoking, setRevoking] = useState<string | null>(null);

  const sessionsQuery = useSessions();
  const sessions: SessionRow[] = sessionsQuery.data?.sessions ?? [];
  const loading = sessionsQuery.isPending;
  const error = sessionsQuery.error
    ? sessionsQuery.error instanceof Error
      ? sessionsQuery.error.message
      : "Failed to load sessions"
    : null;
  const refetchSessions = sessionsQuery.refetch;

  const handleRevoke = useCallback(
    async (sessionId: string, isCurrent: boolean) => {
      setRevoking(sessionId);
      try {
        await api.sessions.revoke(sessionId);
        toast.success(
          isCurrent ? "Session revoked. Signing out." : "Session revoked."
        );
        if (isCurrent) {
          await signOut({ callbackUrl: "/login" });
          return;
        }
        await refetchSessions();
      } catch (e: unknown) {
        toast.error(
          e instanceof Error ? e.message : "Failed to revoke session."
        );
      } finally {
        setRevoking(null);
      }
    },
    [refetchSessions]
  );

  return (
    <section className="flex flex-col gap-6">
      <header className="flex flex-col gap-1">
        <h1 className="text-[22px] font-semibold tracking-tight text-fg">
          Sessions / API
        </h1>
        <p className="text-fg-secondary">
          Active sessions, programmatic-access tokens, and webhook destinations.
        </p>
      </header>

      <FieldGroup
        title="Active sessions"
        description="Devices currently signed in to your account. Revoking a session forces that browser back to /login on its next refresh."
      >
        {error && (
          <div
            role="alert"
            className="rounded-md border border-danger-700/40 bg-danger-700/10 px-4 py-3 flex items-start gap-3 text-[13px] text-danger-500"
          >
            <AlertTriangle
              className="w-4 h-4 shrink-0 mt-0.5"
              strokeWidth={1.5}
              aria-hidden
            />
            <div>
              <p className="font-medium">Sessions endpoint unreachable</p>
              <p className="text-danger-500/80 mt-1">{error}</p>
            </div>
          </div>
        )}

        {loading && !sessions.length ? (
          <div className="rounded-md border border-border-subtle bg-bg-panel/60 p-6 text-center">
            <p className="text-[13px] text-fg-muted">Loading sessions…</p>
          </div>
        ) : sessions.length === 0 ? (
          <div className="rounded-md border border-border-subtle bg-bg-panel/60 p-6 text-center">
            <p className="text-fg">No active sessions.</p>
            <p className="text-[13px] text-fg-muted mt-1">
              That shouldn&apos;t happen if you&apos;re reading this — try
              refreshing.
            </p>
          </div>
        ) : (
          <ul className="rounded-md border border-border-subtle bg-bg-panel divide-y divide-border-subtle">
            {sessions.map((s) => (
              <SessionItem
                key={s.session_id}
                session={s}
                revoking={revoking === s.session_id}
                onRevoke={() => handleRevoke(s.session_id, s.is_current)}
              />
            ))}
          </ul>
        )}
      </FieldGroup>

      <FieldGroup
        title="API tokens"
        description="Programmatic access for scripts and integrations. Full secret is shown once at creation, then masked."
      >
        <div className="rounded-md border border-border-subtle bg-bg-panel/60 p-6 text-center">
          <p className="text-fg">No API tokens.</p>
          <p className="text-[13px] text-fg-muted mt-1">
            Token issuance, hashed storage, and scoped permissions are coming
            in a follow-up. The session-revocation infrastructure that lands
            today is the foundation it builds on.
          </p>
          <div className="mt-4 inline-flex">
            <Tag intent="warn">Pending</Tag>
          </div>
        </div>
      </FieldGroup>

      <FieldGroup
        title="Webhook destinations"
        description="Endpoints that receive event POSTs (fills, drawdown, kill-switch transitions)."
      >
        <div className="rounded-md border border-border-subtle bg-bg-panel/60 p-6 text-center">
          <p className="text-fg">No webhooks configured.</p>
          <p className="text-[13px] text-fg-muted mt-1">
            Webhook delivery pairs with the per-event notification matrix
            (Notifications page). They land together.
          </p>
          <div className="mt-4 inline-flex">
            <Tag intent="warn">Pending</Tag>
          </div>
        </div>
      </FieldGroup>
    </section>
  );
}

function SessionItem({
  session,
  revoking,
  onRevoke,
}: {
  session: SessionRow;
  revoking: boolean;
  onRevoke: () => void;
}) {
  const isMobile =
    session.device === "iPhone" || session.device === "Android";
  const Icon = isMobile ? Smartphone : Laptop;

  const deviceLabel = session.device ?? "Unknown device";
  const browserLabel = session.browser ?? "Browser";

  return (
    <li className="px-4 py-3 flex items-center justify-between gap-4">
      <div className="flex items-center gap-3 min-w-0">
        <Icon
          className="w-5 h-5 text-fg-muted shrink-0"
          strokeWidth={1.5}
          aria-hidden
        />
        <div className="min-w-0">
          <div className="flex items-center gap-2 flex-wrap">
            <p className="text-[14px] text-fg">
              {browserLabel} · {deviceLabel}
            </p>
            {session.is_current && (
              <Pill intent="bid" icon={<StatusDot state="live" size={6} pulse />}>
                This session
              </Pill>
            )}
          </div>
          <p className="text-[12px] text-fg-muted mt-0.5 num-tabular font-mono">
            {session.ip ? `${session.ip} · ` : ""}
            {session.last_seen_at
              ? `last seen ${new Date(session.last_seen_at).toLocaleString()}`
              : "last seen unknown"}
          </p>
        </div>
      </div>
      <Button
        intent={session.is_current ? "secondary" : "danger"}
        size="md"
        leftIcon={<LogOut className="w-3.5 h-3.5" />}
        onClick={onRevoke}
        loading={revoking}
        disabled={revoking}
      >
        {session.is_current ? "Sign out" : "Revoke"}
      </Button>
    </li>
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
      <div className="flex flex-col gap-3">{children}</div>
    </section>
  );
}
