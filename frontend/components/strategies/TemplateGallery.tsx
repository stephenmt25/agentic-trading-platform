"use client";

import React, { useMemo, useState } from "react";
import { Loader2, Plus, Sparkles } from "lucide-react";
import { Button } from "@/components/ui/button";
import { api } from "@/lib/api/client";
import { toast } from "sonner";
import templatesJson from "@/app/strategies/templates.json";

type StrategySignal = {
  indicator: string;
  comparison: string;
  threshold: number;
};

type TemplateRules =
  | {
      direction: "long" | "short";
      match_mode: "all" | "any";
      confidence: number;
      signals: StrategySignal[];
    }
  | {
      confidence: number;
      entry_long?: StrategySignal[];
      match_mode_long?: "all" | "any";
      entry_short?: StrategySignal[];
      match_mode_short?: "all" | "any";
    };

type Template = {
  id: string;
  name: string;
  description: string;
  preferred_regimes: string[];
  rules: TemplateRules;
};

interface Props {
  onCreated?: (profileId: string) => void;
}

export function TemplateGallery({ onCreated }: Props) {
  const templates = useMemo(() => (templatesJson as { templates: Template[] }).templates, []);
  const [submittingId, setSubmittingId] = useState<string | null>(null);

  const handleCreate = async (template: Template) => {
    setSubmittingId(template.id);
    try {
      const rulesJson: Record<string, unknown> = {
        ...(template.rules as Record<string, unknown>),
      };
      if (template.preferred_regimes.length > 0) {
        rulesJson.preferred_regimes = template.preferred_regimes;
      }
      const res = await api.profiles.create({
        name: template.name,
        rules_json: rulesJson,
        allocation_pct: 1.0,
      });
      toast.success(`Profile "${template.name}" created from template`);
      onCreated?.(res.id);
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : "Failed to create profile";
      toast.error(message);
    } finally {
      setSubmittingId(null);
    }
  };

  return (
    <div className="space-y-3">
      <div className="flex items-center gap-2">
        <Sparkles className="w-4 h-4 text-primary" />
        <h2 className="text-sm font-medium text-foreground">Templates</h2>
        <span className="text-[10px] uppercase tracking-wider text-muted-foreground">
          one-click profile starters
        </span>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
        {templates.map((template) => {
          const summary = describeRules(template.rules);
          return (
            <div
              key={template.id}
              className="border border-border bg-card rounded-md p-4 flex flex-col gap-3"
            >
              <div>
                <h3 className="text-sm font-medium text-foreground">{template.name}</h3>
                <p className="text-xs text-muted-foreground mt-1 leading-relaxed">
                  {template.description}
                </p>
              </div>

              <div className="text-[11px] font-mono text-muted-foreground space-y-1">
                {summary.map((line, idx) => (
                  <div key={idx} className="truncate">{line}</div>
                ))}
                {template.preferred_regimes.length > 0 && (
                  <div className="text-[10px] uppercase tracking-wider opacity-70">
                    regimes: {template.preferred_regimes.join(", ")}
                  </div>
                )}
              </div>

              <div className="flex justify-end">
                <Button
                  onClick={() => handleCreate(template)}
                  disabled={submittingId !== null}
                  size="sm"
                  className="bg-primary text-primary-foreground hover:bg-primary/90"
                >
                  {submittingId === template.id ? (
                    <>
                      <Loader2 className="w-3.5 h-3.5 mr-1.5 animate-spin" /> Creating...
                    </>
                  ) : (
                    <>
                      <Plus className="w-3.5 h-3.5 mr-1.5" /> Create profile
                    </>
                  )}
                </Button>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

function describeRules(rules: TemplateRules): string[] {
  const lines: string[] = [];
  if ("entry_long" in rules || "entry_short" in rules) {
    if (rules.entry_long?.length) {
      lines.push(`long  ${rules.match_mode_long ?? "all"}: ${rules.entry_long.map(formatSignal).join(", ")}`);
    }
    if (rules.entry_short?.length) {
      lines.push(`short ${rules.match_mode_short ?? "all"}: ${rules.entry_short.map(formatSignal).join(", ")}`);
    }
  } else {
    lines.push(`${rules.direction} ${rules.match_mode}: ${rules.signals.map(formatSignal).join(", ")}`);
  }
  lines.push(`confidence: ${rules.confidence}`);
  return lines;
}

function formatSignal(s: StrategySignal): string {
  return `${s.indicator} ${s.comparison} ${s.threshold}`;
}
