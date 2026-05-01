"use client";

import React, { useState } from "react";
import { Plus, Trash2, X, Loader2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { api } from "@/lib/api/client";
import { toast } from "sonner";

const INDICATORS = ["rsi", "atr", "macd_line", "macd_signal", "macd_histogram"] as const;
const COMPARISONS = ["above", "below", "at_or_above", "at_or_below", "equals"] as const;

type Indicator = (typeof INDICATORS)[number];
type Comparison = (typeof COMPARISONS)[number];

interface Signal {
  indicator: Indicator;
  comparison: Comparison;
  threshold: number;
}

interface Props {
  open: boolean;
  onClose: () => void;
  onCreated: (profileId: string) => void;
}

const DEFAULT_SIGNAL: Signal = { indicator: "rsi", comparison: "below", threshold: 30 };

export function NewProfileModal({ open, onClose, onCreated }: Props) {
  const [name, setName] = useState("");
  const [allocation, setAllocation] = useState("1.0");
  const [direction, setDirection] = useState<"long" | "short">("long");
  const [matchMode, setMatchMode] = useState<"all" | "any">("all");
  const [confidence, setConfidence] = useState("0.6");
  const [signals, setSignals] = useState<Signal[]>([{ ...DEFAULT_SIGNAL }]);
  const [submitting, setSubmitting] = useState(false);

  if (!open) return null;

  const updateSignal = (idx: number, patch: Partial<Signal>) => {
    setSignals((prev) => prev.map((s, i) => (i === idx ? { ...s, ...patch } : s)));
  };

  const addSignal = () => setSignals((prev) => [...prev, { ...DEFAULT_SIGNAL }]);
  const removeSignal = (idx: number) => setSignals((prev) => prev.filter((_, i) => i !== idx));

  const handleSubmit = async () => {
    if (!name.trim()) {
      toast.error("Profile name required");
      return;
    }
    if (signals.length === 0) {
      toast.error("At least one signal required");
      return;
    }
    const conf = parseFloat(confidence);
    if (Number.isNaN(conf) || conf < 0 || conf > 1) {
      toast.error("Confidence must be between 0 and 1");
      return;
    }

    setSubmitting(true);
    try {
      const res = await api.profiles.create({
        name: name.trim(),
        allocation_pct: parseFloat(allocation) || 1.0,
        rules_json: {
          direction,
          match_mode: matchMode,
          confidence: conf,
          signals: signals.map((s) => ({
            indicator: s.indicator,
            comparison: s.comparison,
            threshold: Number(s.threshold),
          })),
        },
      });
      toast.success(`Profile "${name}" created`);
      onCreated(res.id);
      onClose();
      // Reset state for next open
      setName("");
      setAllocation("1.0");
      setDirection("long");
      setMatchMode("all");
      setConfidence("0.6");
      setSignals([{ ...DEFAULT_SIGNAL }]);
    } catch (e: any) {
      toast.error(e.message || "Failed to create profile");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="fixed inset-0 bg-black/60 flex items-center justify-center z-50 p-4" onClick={onClose}>
      <div
        className="bg-card border border-border rounded-md w-full max-w-lg max-h-[90vh] overflow-y-auto"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between px-5 py-4 border-b border-border">
          <h2 className="text-base font-medium text-foreground">New Profile</h2>
          <button
            onClick={onClose}
            className="p-2 text-muted-foreground hover:text-foreground transition-colors min-h-[44px] min-w-[44px] flex items-center justify-center focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary"
            aria-label="Close"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        <div className="px-5 py-4 space-y-4">
          <div>
            <label className="text-[10px] uppercase tracking-wider text-muted-foreground font-medium mb-1.5 block">
              Name
            </label>
            <Input
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="e.g. BTC RSI Reversal"
              autoFocus
              className="bg-background border-border min-h-[44px]"
            />
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="text-[10px] uppercase tracking-wider text-muted-foreground font-medium mb-1.5 block">
                Allocation %
              </label>
              <Input
                type="number"
                step="0.1"
                min="0"
                max="100"
                value={allocation}
                onChange={(e) => setAllocation(e.target.value)}
                className="bg-background border-border font-mono tabular-nums min-h-[44px]"
              />
            </div>
            <div>
              <label className="text-[10px] uppercase tracking-wider text-muted-foreground font-medium mb-1.5 block">
                Confidence
              </label>
              <Input
                type="number"
                step="0.05"
                min="0"
                max="1"
                value={confidence}
                onChange={(e) => setConfidence(e.target.value)}
                className="bg-background border-border font-mono tabular-nums min-h-[44px]"
              />
            </div>
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="text-[10px] uppercase tracking-wider text-muted-foreground font-medium mb-1.5 block">
                Direction
              </label>
              <select
                value={direction}
                onChange={(e) => setDirection(e.target.value as "long" | "short")}
                className="w-full bg-background border border-border rounded-md px-3 text-sm text-foreground min-h-[44px] focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary"
              >
                <option value="long">long</option>
                <option value="short">short</option>
              </select>
            </div>
            <div>
              <label className="text-[10px] uppercase tracking-wider text-muted-foreground font-medium mb-1.5 block">
                Trigger when
              </label>
              <select
                value={matchMode}
                onChange={(e) => setMatchMode(e.target.value as "all" | "any")}
                className="w-full bg-background border border-border rounded-md px-3 text-sm text-foreground min-h-[44px] focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary"
              >
                <option value="all">all signals match</option>
                <option value="any">any signal matches</option>
              </select>
            </div>
          </div>

          <div>
            <div className="flex items-center justify-between mb-2">
              <label className="text-[10px] uppercase tracking-wider text-muted-foreground font-medium">
                Signals
              </label>
              <button
                onClick={addSignal}
                type="button"
                className="text-xs text-primary hover:text-primary/80 flex items-center gap-1 min-h-[28px]"
              >
                <Plus className="w-3 h-3" /> Add signal
              </button>
            </div>
            <div className="space-y-2">
              {signals.map((s, idx) => (
                <div key={idx} className="flex items-center gap-2 p-2 border border-border rounded-md bg-background">
                  <select
                    value={s.indicator}
                    onChange={(e) => updateSignal(idx, { indicator: e.target.value as Indicator })}
                    className="bg-card border border-border rounded-md px-2 py-1.5 text-xs text-foreground font-mono min-h-[36px]"
                  >
                    {INDICATORS.map((ind) => (
                      <option key={ind} value={ind}>{ind}</option>
                    ))}
                  </select>
                  <select
                    value={s.comparison}
                    onChange={(e) => updateSignal(idx, { comparison: e.target.value as Comparison })}
                    className="bg-card border border-border rounded-md px-2 py-1.5 text-xs text-foreground font-mono min-h-[36px]"
                  >
                    {COMPARISONS.map((c) => (
                      <option key={c} value={c}>{c.replace(/_/g, " ")}</option>
                    ))}
                  </select>
                  <Input
                    type="number"
                    step="0.01"
                    value={s.threshold}
                    onChange={(e) => updateSignal(idx, { threshold: parseFloat(e.target.value) || 0 })}
                    className="flex-1 bg-card border-border font-mono tabular-nums text-xs min-h-[36px]"
                  />
                  {signals.length > 1 && (
                    <button
                      onClick={() => removeSignal(idx)}
                      type="button"
                      className="p-1.5 text-muted-foreground hover:text-red-500 transition-colors min-h-[36px] min-w-[36px] flex items-center justify-center"
                      aria-label="Remove signal"
                    >
                      <Trash2 className="w-3.5 h-3.5" />
                    </button>
                  )}
                </div>
              ))}
            </div>
          </div>
        </div>

        <div className="flex justify-end gap-3 px-5 py-4 border-t border-border">
          <Button variant="ghost" onClick={onClose} className="text-muted-foreground min-h-[44px]">
            Cancel
          </Button>
          <Button
            onClick={handleSubmit}
            disabled={submitting || !name.trim()}
            className="bg-primary text-primary-foreground hover:bg-primary/90 font-medium min-h-[44px]"
          >
            {submitting ? (
              <>
                <Loader2 className="w-4 h-4 mr-2 animate-spin" /> Creating...
              </>
            ) : (
              <>
                <Plus className="w-4 h-4 mr-2" /> Create Profile
              </>
            )}
          </Button>
        </div>
      </div>
    </div>
  );
}
