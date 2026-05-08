"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { ArrowRight, Loader2, AlertTriangle, Workflow } from "lucide-react";
import { Button } from "@/components/primitives";
import { Pill, StatusDot } from "@/components/data-display";
import { api, type ProfileResponse } from "@/lib/api/client";

/**
 * /canvas — Pipeline Canvas index. Per surface spec
 * docs/design/05-surface-specs/03-pipeline-canvas.md, the actual editor lives at
 * /canvas/{profile_id}; this index lets the user pick a profile.
 *
 * If exactly one profile exists we auto-redirect to it; otherwise we render a
 * small profile picker. Empty state points to /profiles for creation.
 */
export default function CanvasIndexPage() {
  const router = useRouter();
  const [profiles, setProfiles] = useState<ProfileResponse[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    api.profiles
      .list()
      .then((list) => {
        if (cancelled) return;
        setProfiles(list);
        if (list.length === 1) {
          router.replace(`/canvas/${encodeURIComponent(list[0].profile_id)}`);
        }
      })
      .catch((e: unknown) => {
        if (cancelled) return;
        setError(e instanceof Error ? e.message : "Failed to load profiles");
      });
    return () => {
      cancelled = true;
    };
  }, [router]);

  return (
    <div data-mode="cool" className="flex flex-col h-full bg-bg-canvas text-fg">
      <header className="flex items-start justify-between gap-4 border-b border-border-subtle px-6 py-4">
        <div className="min-w-0">
          <div className="flex items-center gap-2 text-[12px] text-fg-muted">
            <Workflow className="w-3.5 h-3.5" strokeWidth={1.5} aria-hidden />
            <span className="num-tabular">Pipeline Canvas</span>
          </div>
          <h1 className="text-[18px] font-semibold tracking-tight text-fg mt-1.5">
            Choose a profile to edit
          </h1>
          <p className="text-[12px] text-fg-muted mt-0.5">
            The canvas is the source of truth for{" "}
            <span className="font-mono">trading_profiles.pipeline_config</span>.
            Saving compiles{" "}
            <span className="font-mono">strategy_rules</span> atomically.
          </p>
        </div>
      </header>

      <div className="flex-1 min-h-0 overflow-auto px-6 py-6">
        {profiles === null && !error && (
          <div className="rounded-md border border-border-subtle bg-bg-panel p-6 flex items-center gap-3">
            <Loader2 className="w-4 h-4 text-fg-muted animate-spin" aria-hidden />
            <span className="text-[13px] text-fg-muted">Loading profiles…</span>
          </div>
        )}

        {error && (
          <div
            role="alert"
            className="rounded-md border border-danger-700/40 bg-danger-700/10 p-4 flex items-start gap-3 text-[13px] text-danger-500"
          >
            <AlertTriangle
              className="w-4 h-4 shrink-0 mt-0.5"
              strokeWidth={1.5}
              aria-hidden
            />
            <div className="flex-1">
              <p className="font-medium">Could not load profiles.</p>
              <p className="text-fg-muted mt-0.5">{error}</p>
            </div>
          </div>
        )}

        {profiles && profiles.length === 0 && (
          <div className="rounded-md border border-border-subtle bg-bg-panel p-8 flex flex-col items-start gap-3 max-w-xl">
            <h2 className="text-[15px] font-semibold text-fg">No profiles yet</h2>
            <p className="text-[12px] text-fg-muted">
              Create a profile first — the canvas edits an existing
              profile&apos;s pipeline.
            </p>
            <Link href="/profiles">
              <Button intent="primary" size="sm">
                Open Profiles
              </Button>
            </Link>
          </div>
        )}

        {profiles && profiles.length > 1 && (
          <ul className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3 max-w-5xl">
            {profiles.map((p) => (
              <li key={p.profile_id}>
                <Link
                  href={`/canvas/${encodeURIComponent(p.profile_id)}`}
                  className="group block rounded-md border border-border-subtle bg-bg-panel p-4 hover:border-accent-500/50 hover:bg-bg-rowhover focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent-500"
                >
                  <div className="flex items-start justify-between gap-2">
                    <div className="min-w-0 flex-1">
                      <h2 className="text-[14px] font-semibold text-fg truncate">
                        {p.name}
                      </h2>
                      <p className="font-mono text-[11px] text-fg-muted mt-0.5 truncate">
                        {p.profile_id.slice(0, 8)}
                      </p>
                    </div>
                    <ArrowRight
                      className="w-4 h-4 text-fg-muted shrink-0 group-hover:text-accent-300 transition-colors"
                      strokeWidth={1.5}
                      aria-hidden
                    />
                  </div>
                  <div className="mt-3 flex items-center gap-2">
                    {p.is_active ? (
                      <Pill
                        intent="bid"
                        icon={<StatusDot state="live" size={6} pulse />}
                      >
                        Active
                      </Pill>
                    ) : (
                      <Pill
                        intent="neutral"
                        icon={<StatusDot state="idle" size={6} />}
                      >
                        Inactive
                      </Pill>
                    )}
                    <span className="text-[11px] text-fg-muted num-tabular">
                      {(p.allocation_pct * 100).toFixed(0)}% allocation
                    </span>
                  </div>
                </Link>
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}
