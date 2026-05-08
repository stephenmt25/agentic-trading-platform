"use client";

import { useMemo, useState } from "react";
import { Download, FileText, Info } from "lucide-react";
import { toast } from "sonner";
import { Button, Select, type SelectOption, Tag } from "@/components/primitives";

const CURRENT_YEAR = new Date().getFullYear();

const YEARS: SelectOption[] = Array.from({ length: 5 }).map((_, i) => {
  const y = CURRENT_YEAR - i;
  return { value: String(y), label: String(y) };
});

const JURISDICTIONS: SelectOption[] = [
  { value: "us", label: "United States" },
  { value: "uk", label: "United Kingdom" },
  { value: "eu", label: "European Union" },
  { value: "ca", label: "Canada" },
  { value: "au", label: "Australia" },
];

const METHODS: SelectOption[] = [
  { value: "fifo", label: "FIFO — First in, first out" },
  { value: "hifo", label: "HIFO — Highest in, first out" },
  { value: "lifo", label: "LIFO — Last in, first out" },
];

/**
 * /settings/tax — tax report generation. Per surface spec §7.
 *
 * The tax service exists (services/tax) but has no client wrapper in
 * lib/api/client.ts yet. The form is rendered to spec; the Generate
 * action is disabled until a client method is added. No silent fallback
 * — surfacing the gap explicitly is the right move per the working
 * stance (ASK before inventing).
 */
export default function TaxSettingsPage() {
  const [year, setYear] = useState(String(CURRENT_YEAR - 1));
  const [jurisdiction, setJurisdiction] = useState<string | undefined>(undefined);
  const [method, setMethod] = useState<string | undefined>(undefined);

  const canGenerate = useMemo(
    () => !!year && !!jurisdiction && !!method,
    [year, jurisdiction, method]
  );

  return (
    <section className="flex flex-col gap-6">
      <header className="flex flex-col gap-1">
        <h1 className="text-[22px] font-semibold tracking-tight text-fg">Tax</h1>
        <p className="text-fg-secondary">
          Generate cost-basis reports from the trade ledger. Method selection is
          intentional — there is no default; pick the one your jurisdiction
          allows.
        </p>
      </header>

      <div className="rounded-lg border border-warn-700/40 bg-warn-700/10 px-5 py-4 flex items-start gap-3">
        <Info className="w-4 h-4 text-warn-400 shrink-0 mt-0.5" strokeWidth={1.5} aria-hidden />
        <div className="flex-1 text-[13px] text-warn-400/90">
          <p className="font-medium text-warn-400">
            Tax export is wired to the service but not the client.
          </p>
          <p className="mt-1 text-warn-400/70">
            The tax microservice runs at port 8089. A typed wrapper in{" "}
            <code>lib/api/client.ts</code> needs to land before this form can
            generate reports. Form is rendered to spec so the path is ready.
          </p>
        </div>
      </div>

      <div className="rounded-lg border border-border-subtle bg-bg-panel p-5 flex flex-col gap-5">
        <h2 className="text-[14px] font-semibold text-fg">Generate report</h2>
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
          <Select
            label="Tax year"
            options={YEARS}
            value={year}
            onValueChange={setYear}
            density="comfortable"
          />
          <Select
            label="Jurisdiction"
            options={JURISDICTIONS}
            value={jurisdiction}
            onValueChange={setJurisdiction}
            density="comfortable"
            placeholder="Select…"
          />
          <Select
            label="Method"
            options={METHODS}
            value={method}
            onValueChange={setMethod}
            density="comfortable"
            placeholder="Select…"
          />
        </div>
        <p className="text-[12px] text-fg-muted">
          Reports include realized gains, fees, and per-lot disposals. Closed
          trades only — open positions are excluded.
        </p>
        <div className="flex justify-end pt-3 border-t border-border-subtle">
          <Button
            intent="primary"
            size="lg"
            leftIcon={<Download className="w-4 h-4" />}
            disabled={!canGenerate}
            onClick={() =>
              toast.error("Tax client wrapper not wired yet — see banner above.")
            }
          >
            Generate report
          </Button>
        </div>
      </div>

      <div className="flex flex-col gap-3">
        <h2 className="text-[14px] font-semibold text-fg">Prior reports</h2>
        <div className="rounded-md border border-border-subtle bg-bg-panel/60 p-6 text-center">
          <FileText className="w-5 h-5 text-fg-muted mx-auto" strokeWidth={1.5} aria-hidden />
          <p className="text-fg mt-2">No prior reports.</p>
          <p className="text-[13px] text-fg-muted mt-1">
            Generated reports appear here with a download link.
          </p>
        </div>
      </div>

      <div className="rounded-lg border border-border-subtle bg-bg-panel p-5 flex flex-col gap-2">
        <div className="flex items-center gap-2">
          <h2 className="text-[14px] font-semibold text-fg">Manual lot adjustments</h2>
          <Tag intent="warn">Pending</Tag>
        </div>
        <p className="text-[13px] text-fg-secondary">
          Manual adjustments — corrections to imported lots or reconciliations
          across exchanges — land alongside the report client. They are
          intentionally rare; the default is to trust the trade ledger.
        </p>
      </div>
    </section>
  );
}
