"use client";

import { useEffect, useState } from "react";
import { signOut, useSession } from "next-auth/react";
import { CheckCircle2, ExternalLink, LogOut, ShieldCheck } from "lucide-react";
import { Avatar, Button, Input, Tag, Tooltip } from "@/components/primitives";
import { Pill } from "@/components/data-display";
import { api } from "@/lib/api/client";

interface MeData {
  user_id: string;
  email: string;
  display_name: string;
  avatar_url?: string;
  provider: string;
}

/**
 * /settings/account — display name, email/provider, 2FA, theme,
 * density preferences. Per surface spec §8.
 *
 * Praxis auth runs through OAuth (NextAuth provider), so there is no
 * Praxis-managed password to set or rotate; the section explains that
 * and links to the OAuth provider for credential changes — honoring
 * the CALM-mode rule "never auto-fill or auto-set" credentials.
 */
export default function AccountSettingsPage() {
  const { data: session } = useSession();
  const [me, setMe] = useState<MeData | null>(null);
  const [meError, setMeError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    api.auth
      .me()
      .then((data) => {
        if (!cancelled) setMe(data);
      })
      .catch((e: unknown) => {
        if (cancelled) return;
        const msg = e instanceof Error ? e.message : "Could not load account";
        if (!msg.includes("Unauthorized")) setMeError(msg);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const displayName = me?.display_name ?? session?.user?.name ?? "—";
  const email = me?.email ?? session?.user?.email ?? "—";
  const avatarUrl = me?.avatar_url ?? session?.user?.image ?? undefined;
  const provider = me?.provider ?? session?.user?.provider ?? "—";

  return (
    <section className="flex flex-col gap-6">
      <header className="flex flex-col gap-1">
        <h1 className="text-[22px] font-semibold tracking-tight text-fg">
          Account
        </h1>
        <p className="text-fg-secondary">
          Identity and preferences. Authentication is provided by the OAuth
          provider you signed in with.
        </p>
      </header>

      {meError && (
        <div role="alert" className="text-[13px] text-warn-400/90">
          {meError}
        </div>
      )}

      <FieldGroup title="Identity">
        <div className="flex items-center gap-4">
          <Avatar size="lg" src={avatarUrl} name={displayName} />
          <div className="flex-1 min-w-0">
            <p className="text-[15px] text-fg truncate">{displayName}</p>
            <p className="text-[13px] text-fg-muted truncate">{email}</p>
          </div>
        </div>

        <Input
          label="Display name"
          density="comfortable"
          value={displayName}
          disabled
          hint="Sourced from your OAuth provider; edit it there."
        />
        <div className="flex flex-col gap-1.5">
          <label className="text-xs font-medium text-fg-secondary">Email</label>
          <div className="flex items-center justify-between gap-3 rounded-md border border-border-subtle bg-bg-raised px-3 h-10">
            <span className="text-[14px] text-fg truncate">{email}</span>
            <Pill intent="bid">
              <CheckCircle2 className="w-3 h-3" strokeWidth={1.5} aria-hidden /> Verified
            </Pill>
          </div>
          <p className="text-[11px] text-fg-muted">
            Email verification is delegated to the OAuth provider.
          </p>
        </div>
      </FieldGroup>

      <FieldGroup title="Sign-in">
        <div className="flex items-center justify-between rounded-md border border-border-subtle bg-bg-panel px-4 py-3">
          <div className="flex items-center gap-3">
            <ShieldCheck className="w-4 h-4 text-bid-400" strokeWidth={1.5} aria-hidden />
            <div>
              <p className="text-[14px] text-fg capitalize">{provider} OAuth</p>
              <p className="text-[12px] text-fg-muted">
                Praxis does not store a password for OAuth accounts.
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
        <Tooltip content="Manage credentials at your OAuth provider's account settings.">
          <a
            href={
              provider === "github"
                ? "https://github.com/settings/security"
                : "https://myaccount.google.com/security"
            }
            target="_blank"
            rel="noreferrer"
            className="inline-flex items-center gap-1.5 text-[13px] text-accent-400 hover:text-accent-300 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent-500 rounded-sm w-fit"
          >
            Manage password & 2FA at provider
            <ExternalLink className="w-3 h-3" strokeWidth={1.5} aria-hidden />
          </a>
        </Tooltip>
      </FieldGroup>

      <FieldGroup title="Preferences">
        <PreferenceRow
          name="Theme"
          value="Dark"
          status="locked"
          note="Light theme is committed for v2. v1 ships dark only."
        />
        <PreferenceRow
          name="Default density"
          value="Standard"
          status="pending"
          note="Per-surface density toggles ship with Phase 7 polish."
        />
        <PreferenceRow
          name="Tabular numerics"
          value="Always on"
          status="locked"
          note="Praxis always uses tabular numerics for financial data (ADR-008)."
        />
      </FieldGroup>
    </section>
  );
}

function FieldGroup({
  title,
  children,
}: {
  title: string;
  children: React.ReactNode;
}) {
  return (
    <section className="flex flex-col gap-3 border-t border-border-subtle pt-6 first:border-t-0 first:pt-0">
      <h2 className="text-[16px] font-semibold text-fg">{title}</h2>
      <div className="flex flex-col gap-4">{children}</div>
    </section>
  );
}

function PreferenceRow({
  name,
  value,
  status,
  note,
}: {
  name: string;
  value: string;
  status: "locked" | "pending";
  note: string;
}) {
  return (
    <div className="flex items-start justify-between gap-4 rounded-md border border-border-subtle bg-bg-panel px-4 py-3">
      <div className="min-w-0 flex-1">
        <p className="text-[14px] text-fg">{name}</p>
        <p className="text-[12px] text-fg-muted mt-0.5">{note}</p>
      </div>
      <div className="flex items-center gap-2 shrink-0">
        <span className="text-[13px] text-fg-secondary num-tabular">{value}</span>
        {status === "pending" && <Tag intent="warn">Pending</Tag>}
        {status === "locked" && <Tag intent="neutral">Locked</Tag>}
      </div>
    </div>
  );
}
