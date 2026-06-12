"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import {
  AlertTriangle,
  ChevronLeft,
  Loader2,
  Lock,
  OctagonX,
  Play,
  Shield,
  ShieldAlert,
  X,
} from "lucide-react";
import { toast } from "sonner";
import { useMutation, useQueryClient } from "@tanstack/react-query";

import { Button, Input } from "@/components/primitives";
import { api, type KillSwitchStatus } from "@/lib/api/client";
import { queryKeys } from "@/lib/api/hooks";
import {
  parseHaltLevel,
  severity,
  useKillSwitchStore,
  type HaltLevel,
} from "@/lib/stores/killSwitchStore";
import { cn } from "@/lib/utils";

/**
 * Global tiered-halt control (FE-W1, DECISIONS.md 2026-06-10 decision #2).
 * Mounted once in RedesignShell so Cmd+Shift+K works from any surface.
 *
 * Graduated verb ladder — each rung subsumes the cheaper ones:
 *   STOP_OPENING / DE_RISK / NEUTRALIZE: single-click after a required reason.
 *   FLATTEN: two-stage confirm gate stating the locked auto-FLATTEN policy,
 *   plus typed confirmation ("FLATTEN"). Structurally unreachable via
 *   Enter-key fallthrough (no <form>; every button is type="button") or
 *   stage-1 double-click (stage 2's button starts disabled until typed).
 *
 * Optimistic update with reconcile-on-poll: the mutation snapshots the
 * ["killSwitch"] cache + store level, sets both to the target, ROLLS BACK
 * both on error, and invalidates on settle so the 10s useKillSwitch poll
 * (mounted globally in RedesignShell, which also mirrors it into the store)
 * reconciles. A mis-reconcile on a safety control is worse than a spinner.
 */

/** Exported so OrderEntryPanel's tiered halt banner reuses this exact copy
 * (DECISIONS-verbatim) instead of retyping it. */
export const LADDER: Array<{
  level: Exclude<HaltLevel, "NONE">;
  description: string;
}> = [
  { level: "STOP_OPENING", description: "Block new entries" },
  { level: "DE_RISK", description: "+ cancel resting orders / halt averaging-in" },
  {
    level: "NEUTRALIZE",
    description: "+ reduce-only trims to ≤50% gross budget; never flips direction",
  },
  { level: "FLATTEN", description: "Close ALL positions to zero" },
];

/** Locked policy (DECISIONS.md 2026-06-10 decision #2) — shown verbatim in
 * the FLATTEN stage-2 gate. */
const FLATTEN_POLICY =
  "Manual FLATTEN is an explicit human authorization. Automated FLATTEN is " +
  "permitted only when ≥2 independent severe triggers (intraday drawdown " +
  "≥15%, reconciliation drift alarm, CRISIS regime) persist ≥30s; below " +
  "that bar it requires explicit human authorization.";

export function KillSwitchModal() {
  const open = useKillSwitchStore((s) => s.modalOpen);
  const setOpen = useKillSwitchStore((s) => s.setModalOpen);
  const storeLevel = useKillSwitchStore((s) => s.level);
  const setStoreLevel = useKillSwitchStore((s) => s.setLevel);

  const [reason, setReason] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [stage, setStage] = useState<"ladder" | "flatten-confirm">("ladder");
  const [flattenText, setFlattenText] = useState("");
  const inputRef = useRef<HTMLInputElement | null>(null);

  const queryClient = useQueryClient();

  const mutation = useMutation({
    mutationFn: ({ level, reason }: { level: HaltLevel; reason: string }) =>
      api.commands.killSwitchSetLevel(level, reason),
    onMutate: async ({ level }) => {
      // Snapshot cache + store, then optimistically set both to the target.
      await queryClient.cancelQueries({ queryKey: queryKeys.killSwitch });
      const prevLevel = useKillSwitchStore.getState().level;
      // If the cache is somehow empty (poll not yet landed), snapshot a
      // store-derived value so onError always rolls back to a DEFINED state
      // (setQueryData(undefined) would be a no-op and strand the optimistic
      // value until the next poll).
      const prevCache =
        queryClient.getQueryData<KillSwitchStatus>(queryKeys.killSwitch) ??
        ({
          active: prevLevel !== "NONE",
          level: prevLevel,
          recent_log: [],
        } satisfies KillSwitchStatus);
      queryClient.setQueryData<KillSwitchStatus>(
        queryKeys.killSwitch,
        (old) =>
          old
            ? { ...old, level, active: level !== "NONE" }
            : { active: level !== "NONE", level, recent_log: [] }
      );
      setStoreLevel(level);
      return { prevCache, prevLevel };
    },
    onError: (e: unknown, _vars, ctx) => {
      // ROLL BACK both the cache and the store to the snapshot.
      if (ctx) {
        queryClient.setQueryData(queryKeys.killSwitch, ctx.prevCache);
        setStoreLevel(ctx.prevLevel);
      }
      setError(e instanceof Error ? e.message : "Could not change halt level");
    },
    onSuccess: (_data, { level }) => {
      toast.success(
        level === "NONE"
          ? "Trading resumed (halt cleared)"
          : `Halt level set: ${level}`
      );
      setOpen(false);
    },
    onSettled: () => {
      // The 10s useKillSwitch poll (mounted in RedesignShell) reconciles
      // from here.
      queryClient.invalidateQueries({ queryKey: queryKeys.killSwitch });
    },
  });
  const submitting = mutation.isPending;

  // Reset + refresh from the API every time the modal opens (the store can
  // be stale when arriving from a surface that doesn't poll, e.g. /settings).
  useEffect(() => {
    if (!open) return;
    setReason("");
    setError(null);
    setStage("ladder");
    setFlattenText("");
    inputRef.current?.focus();

    let cancelled = false;
    api.commands
      .killSwitchStatus()
      .then((s) => {
        if (cancelled) return;
        setStoreLevel(parseHaltLevel(s.level, s.active));
      })
      .catch(() => {
        // Keep the store-derived value; the control is still usable.
      });
    return () => {
      cancelled = true;
    };
  }, [open, setStoreLevel]);

  // Esc closes (kept from the binary modal).
  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        e.preventDefault();
        setOpen(false);
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, setOpen]);

  const handleClose = useCallback(() => setOpen(false), [setOpen]);

  const requireReason = useCallback((): string | null => {
    const r = reason.trim();
    if (!r) {
      setError("Reason is required.");
      inputRef.current?.focus();
      return null;
    }
    setError(null);
    return r;
  }, [reason]);

  /** Single-click rungs (STOP_OPENING / DE_RISK / NEUTRALIZE) + resume. */
  const handleSetLevel = useCallback(
    (level: Exclude<HaltLevel, "FLATTEN">) => {
      if (submitting) return;
      const r = requireReason();
      if (!r) return;
      mutation.mutate({ level, reason: r });
    },
    [mutation, requireReason, submitting]
  );

  /** FLATTEN stage 1 → opens the confirm gate; never submits directly. */
  const handleFlattenStage1 = useCallback(() => {
    if (submitting) return;
    const r = requireReason();
    if (!r) return;
    setFlattenText("");
    setStage("flatten-confirm");
  }, [requireReason, submitting]);

  /** FLATTEN stage 2 — only reachable with reason + typed confirmation. */
  const handleFlattenConfirm = useCallback(() => {
    if (submitting) return;
    if (flattenText !== "FLATTEN") return;
    const r = requireReason();
    if (!r) return;
    mutation.mutate({ level: "FLATTEN", reason: r });
  }, [flattenText, mutation, requireReason, submitting]);

  if (!open) return null;

  const sev = severity(storeLevel);

  return (
    <div
      data-mode="calm"
      role="dialog"
      aria-modal="true"
      aria-labelledby="kill-switch-modal-title"
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm p-4"
      onClick={(e) => {
        if (e.target === e.currentTarget) handleClose();
      }}
    >
      <div
        className={cn(
          "w-full max-w-lg rounded-md border-2 bg-bg-panel shadow-xl",
          sev === "danger" ? "border-danger-500" : "border-warn-500"
        )}
      >
        <header className="px-5 py-4 border-b border-border-subtle flex items-start justify-between gap-2">
          <div>
            <h2
              id="kill-switch-modal-title"
              className="text-[15px] font-semibold text-fg"
            >
              {stage === "flatten-confirm"
                ? "Confirm FLATTEN — close everything?"
                : "Trading halt control"}
            </h2>
            <p className="text-[12px] text-fg-muted mt-1 num-tabular">
              current level:{" "}
              <span
                className={cn(
                  "font-mono font-semibold",
                  sev === "off" && "text-fg",
                  sev === "warn" && "text-warn-400",
                  sev === "danger" && "text-danger-500"
                )}
                data-testid="kill-current-level"
              >
                {storeLevel}
              </span>
            </p>
          </div>
          <button
            type="button"
            onClick={handleClose}
            aria-label="Close"
            className="text-fg-muted hover:text-fg"
          >
            <X className="w-4 h-4" strokeWidth={1.5} aria-hidden />
          </button>
        </header>

        {/* NOTE: deliberately NOT a <form> — Enter in any input must never
            submit anything. Every action is an explicit button click. */}
        <div className="px-5 py-4 flex flex-col gap-3">
          <label className="flex flex-col gap-1.5">
            <span className="text-[11px] uppercase tracking-wider text-fg-muted num-tabular">
              reason (required)
            </span>
            <Input
              ref={inputRef}
              value={reason}
              onChange={(e) => setReason(e.target.value)}
              placeholder="why are you doing this?"
              aria-label="Reason"
              autoComplete="off"
              // Mirrors KillSwitchRequest.reason max_length=256 — the reason
              // is persisted to the Redis log and re-served on every status
              // poll, so it must stay bounded.
              maxLength={256}
              disabled={submitting}
            />
          </label>

          {error && (
            <p className="text-[12px] text-danger-500" role="alert">
              {error}
            </p>
          )}

          {stage === "ladder" ? (
            <>
              <ul className="flex flex-col gap-1.5" aria-label="Halt levels">
                {LADDER.map(({ level, description }) => {
                  const isCurrent = storeLevel === level;
                  const rungSev = severity(level);
                  const isFlatten = level === "FLATTEN";
                  return (
                    <li key={level}>
                      <button
                        type="button"
                        onClick={() =>
                          isFlatten
                            ? handleFlattenStage1()
                            : handleSetLevel(level)
                        }
                        disabled={submitting || isCurrent}
                        data-testid={`halt-${level}`}
                        aria-label={
                          isFlatten ? `${level} (requires confirmation)` : level
                        }
                        className={cn(
                          "w-full text-left rounded-md border px-3 py-2.5 flex items-start gap-3 transition-colors",
                          "disabled:cursor-not-allowed",
                          isCurrent
                            ? "border-border-strong bg-bg-raised opacity-70"
                            : rungSev === "danger"
                              ? "border-danger-700/50 hover:bg-danger-700/10"
                              : "border-border-subtle hover:bg-bg-raised"
                        )}
                      >
                        <span
                          aria-hidden
                          className={cn(
                            "mt-0.5 shrink-0",
                            rungSev === "danger"
                              ? "text-danger-500"
                              : "text-warn-400"
                          )}
                        >
                          {isFlatten ? (
                            <OctagonX className="w-4 h-4" strokeWidth={1.5} />
                          ) : level === "STOP_OPENING" ? (
                            <Lock className="w-4 h-4" strokeWidth={1.5} />
                          ) : level === "DE_RISK" ? (
                            <Shield className="w-4 h-4" strokeWidth={1.5} />
                          ) : (
                            <ShieldAlert className="w-4 h-4" strokeWidth={1.5} />
                          )}
                        </span>
                        <span className="min-w-0">
                          <span
                            className={cn(
                              "block text-[13px] font-semibold font-mono num-tabular",
                              rungSev === "danger"
                                ? "text-danger-500"
                                : "text-fg"
                            )}
                          >
                            {level}
                            {isCurrent && (
                              <span className="ml-2 text-[10px] uppercase tracking-wider text-fg-muted">
                                current
                              </span>
                            )}
                            {isFlatten && (
                              <span className="ml-2 text-[10px] uppercase tracking-wider text-danger-500/80">
                                2-step confirm
                              </span>
                            )}
                          </span>
                          <span className="block text-[12px] text-fg-secondary mt-0.5">
                            {description}
                          </span>
                        </span>
                      </button>
                    </li>
                  );
                })}
              </ul>

              <div className="flex items-center justify-between gap-2 pt-2">
                {storeLevel !== "NONE" ? (
                  <Button
                    type="button"
                    intent="primary"
                    size="sm"
                    leftIcon={
                      submitting ? (
                        <Loader2 className="w-3.5 h-3.5 animate-spin will-change-transform" aria-hidden />
                      ) : (
                        <Play className="w-3.5 h-3.5" strokeWidth={1.5} />
                      )
                    }
                    onClick={() => handleSetLevel("NONE")}
                    disabled={submitting}
                    data-testid="halt-NONE"
                  >
                    Resume trading
                  </Button>
                ) : (
                  <span />
                )}
                <Button
                  type="button"
                  intent="secondary"
                  size="sm"
                  onClick={handleClose}
                  disabled={submitting}
                >
                  Cancel
                </Button>
              </div>
            </>
          ) : (
            <>
              <div
                className="rounded-md border border-danger-700/50 bg-danger-700/10 p-3 flex items-start gap-2.5"
                role="note"
              >
                <AlertTriangle
                  className="w-4 h-4 text-danger-500 shrink-0 mt-0.5"
                  strokeWidth={1.5}
                  aria-hidden
                />
                <p className="text-[12px] leading-relaxed text-fg-secondary">
                  {FLATTEN_POLICY}
                </p>
              </div>

              <label className="flex flex-col gap-1.5">
                <span className="text-[11px] uppercase tracking-wider text-fg-muted num-tabular">
                  type FLATTEN to confirm
                </span>
                <Input
                  value={flattenText}
                  onChange={(e) => setFlattenText(e.target.value)}
                  placeholder="FLATTEN"
                  aria-label="Type FLATTEN to confirm"
                  autoComplete="off"
                  disabled={submitting}
                />
              </label>

              <div className="flex items-center justify-between gap-2 pt-2">
                <Button
                  type="button"
                  intent="secondary"
                  size="sm"
                  leftIcon={
                    <ChevronLeft className="w-3.5 h-3.5" strokeWidth={1.5} />
                  }
                  onClick={() => setStage("ladder")}
                  disabled={submitting}
                >
                  Back
                </Button>
                <Button
                  type="button"
                  intent="danger"
                  size="sm"
                  leftIcon={
                    submitting ? (
                      <Loader2 className="w-3.5 h-3.5 animate-spin will-change-transform" aria-hidden />
                    ) : (
                      <OctagonX className="w-3.5 h-3.5" strokeWidth={1.5} />
                    )
                  }
                  onClick={handleFlattenConfirm}
                  disabled={submitting || flattenText !== "FLATTEN"}
                  data-testid="halt-FLATTEN-confirm"
                >
                  FLATTEN — close everything
                </Button>
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  );
}
