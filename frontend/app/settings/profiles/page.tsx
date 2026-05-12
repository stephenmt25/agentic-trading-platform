"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { Plus, ArrowRight, AlertTriangle } from "lucide-react";
import { toast } from "sonner";
import { Button, Input } from "@/components/primitives";
import { Pill, StatusDot } from "@/components/data-display";
import { cn } from "@/lib/utils";
import { api, type ProfileResponse } from "@/lib/api/client";
import { formatRelative } from "./_lib/format";

/**
 * /settings/profiles — list of trading profiles with summary info.
 * Per surface spec §3 and §12 (empty state).
 *
 * Live PnL / trade counts per profile are not available from the
 * /profiles endpoint and there's no aggregated "last 7 days" backend
 * call yet. The card surfaces what we have honestly (created_at,
 * allocation, signal count) and links to the surfaces where richer
 * metrics live (canvas, backtests).
 */
export default function ProfilesIndexPage() {
  const router = useRouter();
  const [profiles, setProfiles] = useState<ProfileResponse[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [search, setSearch] = useState("");

  const load = () => {
    setLoading(true);
    setError(null);
    return api.profiles
      .list()
      .then(setProfiles)
      .catch((e: unknown) => {
        const msg = e instanceof Error ? e.message : "Failed to load profiles";
        if (!msg.includes("Unauthorized")) setError(msg);
      })
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);
    api.profiles
      .list()
      .then((data) => {
        if (!cancelled) setProfiles(data);
      })
      .catch((e: unknown) => {
        if (cancelled) return;
        const msg = e instanceof Error ? e.message : "Failed to load profiles";
        if (!msg.includes("Unauthorized")) setError(msg);
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const filtered = useMemo(() => {
    const q = search.trim().toLowerCase();
    if (!q) return profiles;
    return profiles.filter(
      (p) =>
        p.name.toLowerCase().includes(q) ||
        p.profile_id.toLowerCase().includes(q)
    );
  }, [profiles, search]);

  const liveProfiles = profiles.filter((p) => !p.deleted_at && p.is_active).length;

  return (
    <section aria-labelledby="profiles-heading" className="flex flex-col gap-6">
      <header className="flex flex-col gap-1">
        <h1 id="profiles-heading" className="text-[22px] font-semibold tracking-tight text-fg">
          Profiles
        </h1>
        <p className="text-fg-secondary">
          Trading profiles and their day-to-day configuration. Pipeline structure
          is edited in the Canvas; identity, schedule, and risk overrides live here.
        </p>
      </header>

      <div className="flex flex-wrap items-center gap-3">
        <Input
          aria-label="Search profiles"
          placeholder="Search by name or ID…"
          density="comfortable"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          className="max-w-sm"
        />
        <span className="text-[13px] text-fg-muted num-tabular">
          {liveProfiles} live · {profiles.length} total
        </span>
        <div className="flex-1" />
        <Button
          intent="primary"
          size="lg"
          leftIcon={<Plus className="w-4 h-4" />}
          onClick={() => router.push("/canvas")}
        >
          New profile
        </Button>
      </div>

      <p className="text-[12px] text-fg-muted -mt-3">
        Profiles are created in the Pipeline Canvas. Open canvas to start a new one.
      </p>

      {loading && <ProfileListSkeleton />}

      {error && !loading && (
        <div
          role="alert"
          className="flex items-start gap-3 rounded-md border border-danger-700/40 bg-danger-700/10 p-4 text-[13px] text-danger-500"
        >
          <AlertTriangle className="w-4 h-4 shrink-0 mt-0.5" strokeWidth={1.5} aria-hidden />
          <div className="flex-1">
            <p className="font-medium">Could not load profiles.</p>
            <p className="text-fg-muted mt-0.5">{error}</p>
          </div>
          <Button
            intent="secondary"
            size="sm"
            onClick={() => {
              load().catch((e: unknown) => {
                toast.error(e instanceof Error ? e.message : "Failed");
              });
            }}
          >
            Retry
          </Button>
        </div>
      )}

      {!loading && !error && filtered.length === 0 && (
        <EmptyState hasSearch={!!search.trim()} totalCount={profiles.length} />
      )}

      {!loading && !error && filtered.length > 0 && (
        <ul className="flex flex-col gap-3" role="list">
          {filtered.map((p) => (
            <li key={p.profile_id}>
              <ProfileCard profile={p} onNavigate={(href) => router.push(href)} />
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}

function ProfileCard({
  profile,
  onNavigate,
}: {
  profile: ProfileResponse;
  onNavigate: (href: string) => void;
}) {
  const isDeleted = !!profile.deleted_at;
  const rules = profile.rules_json as Record<string, unknown>;
  const signals = rules?.signals;
  const signalCount = Array.isArray(signals) ? signals.length : 0;
  const direction = rules?.direction;
  const directionLabel = typeof direction === "string" ? direction : "—";

  const id = encodeURIComponent(profile.profile_id);

  return (
    <article
      className={cn(
        "rounded-lg border bg-bg-panel p-5 transition-colors",
        isDeleted
          ? "border-border-subtle opacity-60"
          : "border-border-subtle hover:border-border-strong"
      )}
    >
      <div className="flex items-start justify-between gap-4">
        <div className="min-w-0 flex-1">
          <h3 className="text-[16px] font-semibold text-fg truncate">
            {profile.name || profile.profile_id}
          </h3>
          <p className="text-[13px] text-fg-muted mt-0.5">
            <span className="font-mono">{profile.profile_id}</span>
            <span className="mx-2 text-fg-muted/50">·</span>
            Created {formatRelative(profile.created_at)}
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

      <dl className="mt-4 grid grid-cols-3 gap-x-6 gap-y-2 text-[13px]">
        <div>
          <dt className="text-[11px] uppercase tracking-wider text-fg-muted">Direction</dt>
          <dd className="mt-0.5 text-fg num-tabular capitalize">{directionLabel}</dd>
        </div>
        <div>
          <dt className="text-[11px] uppercase tracking-wider text-fg-muted">Signals</dt>
          <dd className="mt-0.5 text-fg num-tabular">{signalCount}</dd>
        </div>
        <div>
          <dt className="text-[11px] uppercase tracking-wider text-fg-muted">
            Capital scale
          </dt>
          <dd className="mt-0.5 text-fg num-tabular">{profile.allocation_pct.toFixed(2)}×</dd>
        </div>
      </dl>

      <div className="mt-5 flex flex-wrap gap-2 border-t border-border-subtle pt-4">
        {!isDeleted && (
          <Button
            intent="secondary"
            size="md"
            rightIcon={<ArrowRight className="w-3.5 h-3.5" />}
            onClick={() => onNavigate(`/canvas/${id}`)}
          >
            Open in canvas
          </Button>
        )}
        <Button
          intent="secondary"
          size="md"
          rightIcon={<ArrowRight className="w-3.5 h-3.5" />}
          onClick={() => onNavigate(`/settings/profiles/${id}`)}
        >
          Edit settings
        </Button>
        {!isDeleted && (
          <Button
            intent="secondary"
            size="md"
            rightIcon={<ArrowRight className="w-3.5 h-3.5" />}
            onClick={() => onNavigate(`/backtests?profile=${id}`)}
          >
            Run backtest
          </Button>
        )}
      </div>
    </article>
  );
}

function ProfileListSkeleton() {
  return (
    <ul className="flex flex-col gap-3" aria-label="Loading profiles">
      {[0, 1, 2].map((i) => (
        <li
          key={i}
          className="rounded-lg border border-border-subtle bg-bg-panel p-5 animate-pulse-subtle"
          aria-hidden
        >
          <div className="h-5 w-48 bg-bg-raised rounded" />
          <div className="h-3 w-72 bg-bg-raised/70 rounded mt-2" />
          <div className="grid grid-cols-3 gap-6 mt-4">
            <div className="h-3 w-16 bg-bg-raised/60 rounded" />
            <div className="h-3 w-16 bg-bg-raised/60 rounded" />
            <div className="h-3 w-16 bg-bg-raised/60 rounded" />
          </div>
        </li>
      ))}
    </ul>
  );
}

function EmptyState({
  hasSearch,
  totalCount,
}: {
  hasSearch: boolean;
  totalCount: number;
}) {
  if (hasSearch) {
    return (
      <div className="rounded-lg border border-border-subtle bg-bg-panel/60 p-10 text-center">
        <p className="text-fg">No profiles match your search.</p>
        <p className="text-[13px] text-fg-muted mt-1">
          Try a different name or profile ID.
        </p>
      </div>
    );
  }
  if (totalCount === 0) {
    return (
      <div className="rounded-lg border border-border-subtle bg-bg-panel/60 p-10 text-center">
        <p className="text-fg">No profiles yet.</p>
        <p className="text-[13px] text-fg-muted mt-1">
          Create one in Pipeline Canvas to start trading.
        </p>
        <div className="mt-4">
          <Link href="/canvas">
            <Button intent="primary" size="md">
              Open canvas
            </Button>
          </Link>
        </div>
      </div>
    );
  }
  return null;
}
