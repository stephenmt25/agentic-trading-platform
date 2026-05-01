"use client";

import React, { useEffect, useState } from "react";
import { api, type ProfileResponse } from "@/lib/api/client";
import { Loader2, Copy, FileJson } from "lucide-react";
import { toast } from "sonner";

export function RawProfileView() {
  const [profiles, setProfiles] = useState<ProfileResponse[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    api.profiles
      .list()
      .then((p) => {
        setProfiles(p);
        if (p.length > 0) setSelectedId(p[0].profile_id);
      })
      .catch(() => toast.error("Could not load profiles"))
      .finally(() => setIsLoading(false));
  }, []);

  const selected = profiles.find((p) => p.profile_id === selectedId);
  const canonical = selected?.rules_json_canonical ?? {};
  const formatted = JSON.stringify(canonical, null, 2);

  const handleCopy = () => {
    navigator.clipboard.writeText(formatted);
    toast.success("Canonical JSON copied");
  };

  if (isLoading) {
    return (
      <div className="flex justify-center py-12">
        <Loader2 className="w-5 h-5 animate-spin text-muted-foreground" />
      </div>
    );
  }

  if (profiles.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center py-20 gap-3 text-center">
        <FileJson className="w-8 h-8 text-muted-foreground" />
        <p className="text-sm text-muted-foreground">No profiles yet. Create one in the Builder tab.</p>
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-4 py-4">
      <div className="flex items-center justify-between gap-3 flex-wrap">
        <div>
          <p className="text-xs text-muted-foreground uppercase tracking-wider mb-1">Active Profile</p>
          <select
            value={selectedId ?? ""}
            onChange={(e) => setSelectedId(e.target.value)}
            className="bg-card border border-border rounded-md px-3 py-2 text-sm text-foreground min-h-[40px] min-w-[280px] focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary"
          >
            {profiles.map((p) => (
              <option key={p.profile_id} value={p.profile_id}>
                {p.name} {p.is_active ? "" : " (inactive)"}{p.deleted_at ? " (deleted)" : ""}
              </option>
            ))}
          </select>
        </div>
        <button
          onClick={handleCopy}
          className="flex items-center gap-2 px-3 py-2 rounded-md text-xs text-muted-foreground hover:text-foreground hover:bg-accent transition-colors min-h-[40px] focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary"
        >
          <Copy className="w-3.5 h-3.5" />
          Copy JSON
        </button>
      </div>

      <div>
        <p className="text-xs text-muted-foreground mb-2">
          The exact JSON the engine evaluates. This is the canonical form stored in <code className="px-1 rounded bg-card text-foreground/70">trading_profiles.strategy_rules</code>.
          Read-only — edit via the Builder tab.
        </p>
        <pre className="bg-background border border-border rounded-md p-4 font-mono text-xs text-foreground/80 overflow-auto whitespace-pre tabular-nums">
{formatted}
        </pre>
      </div>
    </div>
  );
}
