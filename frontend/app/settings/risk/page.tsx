"use client";

import Link from "next/link";
import { ArrowRight, Info } from "lucide-react";
import { Button, Tag } from "@/components/primitives";

/**
 * /settings/risk — user-level risk defaults. Per surface spec §5.
 *
 * The backend does not yet expose a user-level risk-defaults endpoint;
 * risk caps are currently per-profile (api.profiles.update.risk_limits).
 * Until that lands, this section explains the model and routes the user
 * to per-profile editing instead of inventing a parallel store that
 * would silently disagree with what the engine enforces.
 */
export default function RiskDefaultsPage() {
  return (
    <section className="flex flex-col gap-6">
      <header className="flex flex-col gap-1">
        <h1 className="text-[22px] font-semibold tracking-tight text-fg">
          Risk defaults
        </h1>
        <p className="text-fg-secondary">
          Caps that apply unless a profile overrides them. Saving recompiles
          affected profiles.
        </p>
      </header>

      <div className="rounded-lg border border-warn-700/40 bg-warn-700/10 px-5 py-4 flex items-start gap-3">
        <Info className="w-4 h-4 text-warn-400 shrink-0 mt-0.5" strokeWidth={1.5} aria-hidden />
        <div className="flex-1 text-[13px] text-warn-400/90">
          <p className="font-medium text-warn-400">User-level defaults aren't wired yet.</p>
          <p className="mt-1 text-warn-400/70">
            Today, risk caps are configured per profile and enforced by the risk
            service against each profile's <code>risk_limits</code> JSONB. The
            account-level overrides shown in the IA need a backend store and a
            recompile path before this page can save anything that the engine
            actually reads.
          </p>
        </div>
      </div>

      <ul className="flex flex-col gap-3">
        <DefaultRow
          name="Max position size"
          description="Per-trade cap as a percent of free capital × signal confidence."
          status="profile"
        />
        <DefaultRow
          name="Max leverage"
          description="Hard ceiling on notional / margin per position."
          status="venue"
        />
        <DefaultRow
          name="Max daily loss"
          description="Halts new orders for the rest of the trading day."
          status="profile"
        />
        <DefaultRow
          name="Rate limit (orders / minute)"
          description="Sliding-window cap enforced by the rate_limiter service."
          status="service"
        />
        <DefaultRow
          name="Auto-pause triggers"
          description="Drawdown / daily loss kill — both configured on the profile."
          status="profile"
        />
      </ul>

      <div className="rounded-lg border border-border-subtle bg-bg-panel p-5 flex flex-col gap-3">
        <h2 className="text-[15px] font-semibold text-fg">Edit risk per profile</h2>
        <p className="text-[13px] text-fg-secondary">
          Open a profile to set its risk overrides. Until user-level defaults
          ship, this is the authoritative place to tune caps.
        </p>
        <div>
          <Link href="/settings/profiles">
            <Button intent="primary" size="md" rightIcon={<ArrowRight className="w-3.5 h-3.5" />}>
              Open profiles
            </Button>
          </Link>
        </div>
      </div>
    </section>
  );
}

function DefaultRow({
  name,
  description,
  status,
}: {
  name: string;
  description: string;
  status: "profile" | "venue" | "service";
}) {
  const tag =
    status === "profile" ? (
      <Tag intent="accent">Per profile</Tag>
    ) : status === "venue" ? (
      <Tag intent="neutral">Venue-side</Tag>
    ) : (
      <Tag intent="neutral">Service-wide</Tag>
    );
  const where =
    status === "profile"
      ? "Configure under Profiles › Risk overrides."
      : status === "venue"
        ? "Configure on the exchange itself."
        : "Configured in service config; not user-editable here.";
  return (
    <li className="rounded-md border border-border-subtle bg-bg-panel px-4 py-3 flex items-start justify-between gap-4">
      <div className="min-w-0 flex-1">
        <p className="text-[14px] text-fg">{name}</p>
        <p className="text-[12px] text-fg-muted mt-0.5">{description}</p>
        <p className="text-[12px] text-fg-secondary mt-1">{where}</p>
      </div>
      <div className="shrink-0">{tag}</div>
    </li>
  );
}
