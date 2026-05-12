"use client";

import { useEffect, useState } from "react";
import { signOut, useSession } from "next-auth/react";
import { Laptop, LogOut } from "lucide-react";
import { Button, Tag } from "@/components/primitives";
import { Pill, StatusDot } from "@/components/data-display";

function detectDevice(): { device: string; browser: string } {
  if (typeof navigator === "undefined") {
    return { device: "Unknown device", browser: "Unknown" };
  }
  const ua = navigator.userAgent;
  const isMac = /Macintosh|Mac OS X/i.test(ua);
  const isWindows = /Windows NT/i.test(ua);
  const isLinux = /Linux/i.test(ua);
  const isiPhone = /iPhone/i.test(ua);
  const isAndroid = /Android/i.test(ua);

  const device = isMac
    ? "Mac"
    : isWindows
      ? "Windows"
      : isLinux
        ? "Linux"
        : isiPhone
          ? "iPhone"
          : isAndroid
            ? "Android"
            : "Unknown device";

  const browser = /Edg\//i.test(ua)
    ? "Edge"
    : /Chrome\//i.test(ua)
      ? "Chrome"
      : /Firefox\//i.test(ua)
        ? "Firefox"
        : /Safari\//i.test(ua)
          ? "Safari"
          : "Browser";

  return { device, browser };
}

/**
 * /settings/sessions — active sessions, API tokens, webhooks.
 * Per surface spec §9.
 *
 * Cross-session listing and API-token CRUD need backend endpoints
 * that don't exist yet. The current session is shown from
 * navigator/useSession; the rest is surfaced as Pending so the
 * structure is in place when the backend lands.
 */
export default function SessionsSettingsPage() {
  const { data: session } = useSession();
  const [agent, setAgent] = useState<{ device: string; browser: string }>({
    device: "—",
    browser: "—",
  });

  useEffect(() => {
    setAgent(detectDevice());
  }, []);

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
        description="Devices currently signed in to your account."
      >
        <div className="rounded-md border border-border-subtle bg-bg-panel px-4 py-3 flex items-center justify-between gap-4">
          <div className="flex items-center gap-3 min-w-0">
            <Laptop className="w-5 h-5 text-fg-muted" strokeWidth={1.5} aria-hidden />
            <div className="min-w-0">
              <div className="flex items-center gap-2">
                <p className="text-[14px] text-fg">
                  {agent.browser} · {agent.device}
                </p>
                <Pill intent="bid" icon={<StatusDot state="live" size={6} pulse />}>
                  This session
                </Pill>
              </div>
              <p className="text-[12px] text-fg-muted">
                Signed in as {session?.user?.email || "—"}
              </p>
            </div>
          </div>
          <Button
            intent="secondary"
            size="md"
            leftIcon={<LogOut className="w-3.5 h-3.5" />}
            onClick={() => signOut({ callbackUrl: "/login" })}
          >
            Sign out
          </Button>
        </div>

        <div className="rounded-md border border-dashed border-border-subtle bg-bg-canvas/40 px-4 py-3 flex items-start gap-3">
          <Tag intent="warn">Pending</Tag>
          <p className="text-[13px] text-fg-secondary leading-snug flex-1">
            Listing other devices, IPs, and last-seen times needs a backend
            sessions endpoint. Until then, only the current browser appears.
          </p>
        </div>
      </FieldGroup>

      <FieldGroup
        title="API tokens"
        description="Programmatic access for scripts and integrations. Full secret is shown once at creation, then masked."
      >
        <div className="rounded-md border border-border-subtle bg-bg-panel/60 p-6 text-center">
          <p className="text-fg">No API tokens.</p>
          <p className="text-[13px] text-fg-muted mt-1">
            Token issuance lands with the auth-tokens endpoint.
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
            Configurable destinations land alongside the notification matrix.
          </p>
          <div className="mt-4 inline-flex">
            <Tag intent="warn">Pending</Tag>
          </div>
        </div>
      </FieldGroup>
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
      <div className="flex flex-col gap-3">{children}</div>
    </section>
  );
}
