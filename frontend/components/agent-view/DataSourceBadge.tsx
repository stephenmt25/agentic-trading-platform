"use client";

import { FlaskConical } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { DATA_SOURCE_COLORS } from "@/lib/constants/agent-view";
import type { DataSource } from "@/lib/types/telemetry";

const IS_MOCK = process.env.NEXT_PUBLIC_AGENT_VIEW_MOCK === "true";

// ---------------------------------------------------------------------------
// Single badge for one data source
// ---------------------------------------------------------------------------

function DataSourceBadge({ source }: { source: DataSource }) {
  const color = DATA_SOURCE_COLORS[source.type];
  return (
    <Badge
      variant="secondary"
      className="px-1.5 text-[10px] font-mono font-medium gap-1"
      style={{ backgroundColor: `${color}20`, color }}
    >
      {source.label}
    </Badge>
  );
}

// ---------------------------------------------------------------------------
// Indicator: renders mock override or real source badges
// ---------------------------------------------------------------------------

export function DataSourceIndicator({
  data_sources,
}: {
  data_sources?: DataSource[];
}) {
  if (IS_MOCK) {
    return (
      <Badge
        variant="secondary"
        className="px-1.5 text-[10px] font-mono font-medium gap-1"
        style={{ backgroundColor: "#f59e0b20", color: "#f59e0b" }}
      >
        <FlaskConical className="h-3 w-3" />
        Simulated
      </Badge>
    );
  }

  if (!data_sources?.length) return null;

  return (
    <span className="flex items-center gap-1 flex-wrap">
      {data_sources.map((src) => (
        <DataSourceBadge key={src.label} source={src} />
      ))}
    </span>
  );
}
