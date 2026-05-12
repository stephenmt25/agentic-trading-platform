"use client";

import { Input, Select, Tag } from "@/components/primitives";

/**
 * Per-node configuration form, generated from the AGENT_CATALOG response
 * (services/api_gateway/src/routes/agent_config.py). Mirrors the legacy
 * NodeConfigDrawer's data plumbing but renders with redesign primitives.
 *
 * strategy_eval — the rule-bearing node — is rendered as a read-only JSON
 * snapshot with a Pending tag pointing at /profiles for edits, until the
 * full strategy editor is ported to redesign tokens (out of scope for 6.3).
 */

export interface AgentParam {
  type: string;
  default: unknown;
  description?: string;
  min?: number;
  max?: number;
  step?: number;
  options?: string[];
}

export interface AgentCatalogEntry {
  label: string;
  type: string;
  params: Record<string, AgentParam>;
}

export type AgentCatalog = Record<string, AgentCatalogEntry>;

interface InspectorContentProps {
  nodeId: string;
  nodeType: string;
  nodeLabel: string;
  config: Record<string, unknown>;
  catalog: AgentCatalog | null;
  onUpdate: (key: string, value: unknown) => void;
}

export function InspectorContent({
  nodeId,
  nodeType,
  nodeLabel,
  config,
  catalog,
  onUpdate,
}: InspectorContentProps) {
  const catalogEntry = catalog
    ? Object.values(catalog).find((c) => c.label === nodeLabel)
    : null;

  if (nodeId === "strategy_eval") {
    return (
      <div className="flex flex-col gap-2">
        <div className="flex items-center gap-2">
          <Tag intent="warn">Pending</Tag>
          <span className="text-[11px] text-fg-muted">
            Strategy rule editor is not yet ported to redesign. Edit at{" "}
            <a
              href="/profiles"
              className="text-accent-300 hover:text-accent-200 underline"
            >
              /profiles
            </a>{" "}
            until then.
          </span>
        </div>
        <pre className="text-[11px] font-mono text-fg-secondary bg-bg-canvas border border-border-subtle rounded-sm p-2 overflow-x-auto whitespace-pre">
          {JSON.stringify(config, null, 2)}
        </pre>
      </div>
    );
  }

  if (catalogEntry) {
    const entries = Object.entries(catalogEntry.params);
    if (entries.length === 0) {
      return <EmptyConfig />;
    }
    return (
      <div className="flex flex-col gap-3">
        {entries.map(([key, param]) => (
          <ParamField
            key={key}
            paramKey={key}
            param={param}
            value={config[key] ?? param.default}
            onChange={(v) => onUpdate(key, v)}
          />
        ))}
      </div>
    );
  }

  // No catalog entry — surface raw config (read-only-ish JSON, with a hint).
  const rawEntries = Object.entries(config);
  if (rawEntries.length === 0) {
    return (
      <p className="text-[12px] text-fg-muted">
        No configurable parameters for{" "}
        <span className="font-mono text-fg-secondary">{nodeType}</span>.
      </p>
    );
  }
  return (
    <div className="flex flex-col gap-3">
      {rawEntries.map(([key, value]) => (
        <RawJsonField
          key={key}
          paramKey={key}
          value={value}
          onChange={(v) => onUpdate(key, v)}
        />
      ))}
    </div>
  );
}

function EmptyConfig() {
  return (
    <p className="text-[12px] text-fg-muted">
      This node has no tunable parameters.
    </p>
  );
}

function ParamField({
  paramKey,
  param,
  value,
  onChange,
}: {
  paramKey: string;
  param: AgentParam;
  value: unknown;
  onChange: (v: unknown) => void;
}) {
  const label = (
    <div className="mb-1">
      <label className="block text-[11px] font-medium text-fg num-tabular">
        {paramKey}
      </label>
      {param.description && (
        <p className="text-[10px] text-fg-muted mt-0.5">{param.description}</p>
      )}
    </div>
  );

  if (param.type === "select" && param.options) {
    return (
      <div>
        {label}
        <Select
          density="compact"
          value={String(value)}
          onValueChange={(v) => onChange(v)}
          options={param.options.map((o) => ({ value: o, label: o }))}
        />
      </div>
    );
  }

  if (param.type === "integer" || param.type === "float") {
    const numericValue = Number(value);
    const display = Number.isFinite(numericValue) ? numericValue : param.default;
    const step = param.step ?? (param.type === "integer" ? 1 : 0.01);
    return (
      <div>
        {label}
        <div className="flex items-center gap-2">
          <input
            type="range"
            min={param.min ?? 0}
            max={param.max ?? (param.type === "integer" ? 100 : 1)}
            step={step}
            value={Number(display) || 0}
            onChange={(e) => onChange(Number(e.target.value))}
            className="flex-1 accent-[var(--color-accent-500)]"
            aria-label={paramKey}
          />
          <span className="text-[11px] font-mono num-tabular text-fg w-14 text-right">
            {Number(display).toFixed(param.type === "integer" ? 0 : 2)}
          </span>
        </div>
      </div>
    );
  }

  // array / string / other — JSON text editor.
  return (
    <RawJsonField paramKey={paramKey} value={value} onChange={onChange} label={label} />
  );
}

function RawJsonField({
  paramKey,
  value,
  onChange,
  label,
}: {
  paramKey: string;
  value: unknown;
  onChange: (v: unknown) => void;
  label?: React.ReactNode;
}) {
  return (
    <div>
      {label ?? (
        <label className="block text-[11px] font-medium text-fg num-tabular mb-1">
          {paramKey}
        </label>
      )}
      <Input
        density="compact"
        defaultValue={JSON.stringify(value)}
        onBlur={(e) => {
          const raw = e.currentTarget.value;
          try {
            onChange(JSON.parse(raw));
          } catch {
            onChange(raw);
          }
        }}
        className="font-mono"
        aria-label={paramKey}
      />
    </div>
  );
}
