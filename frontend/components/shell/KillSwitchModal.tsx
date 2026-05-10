"use client";

import {
  useCallback,
  useEffect,
  useRef,
  useState,
  type FormEvent,
} from "react";
import { Lock, Unlock, Loader2, X } from "lucide-react";
import { toast } from "sonner";

import { Button, Input } from "@/components/primitives";
import { api } from "@/lib/api/client";
import { useKillSwitchStore } from "@/lib/stores/killSwitchStore";

/**
 * Global kill-switch modal. Mounted once in RedesignShell so Cmd+Shift+K
 * works from any surface; per ADR-006 / IA §7 the kill switch is a
 * "≤2 keystrokes from any surface" affordance and previously each surface
 * had to mount its own copy.
 *
 * The modal:
 *   - Reads `armed` from the killSwitch store (whichever surface last
 *     polled api.commands.killSwitchStatus has populated this).
 *   - On open, refreshes status to avoid showing the wrong action when
 *     the user lands here from a surface that doesn't poll
 *     (e.g. /settings, /backtests).
 *   - Validates a non-empty reason, posts the toggle, and broadcasts the
 *     new state through the store so chrome on every surface re-renders.
 *
 * Backend kill switch is binary today — the spec calls for soft/hard
 * separation but that's a Pending backend distinction (see surface spec
 * 05-risk-control.md). Treat `state === "off"` as disarmed and any other
 * value as armed.
 */
export function KillSwitchModal() {
  const open = useKillSwitchStore((s) => s.modalOpen);
  const setOpen = useKillSwitchStore((s) => s.setModalOpen);
  const localState = useKillSwitchStore((s) => s.state);
  const setLocalState = useKillSwitchStore((s) => s.setState);

  const [armed, setArmed] = useState(localState !== "off");
  const [reason, setReason] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const inputRef = useRef<HTMLInputElement | null>(null);

  // Sync local armed flag with the store every time the modal opens, and
  // refresh from the API in case the store was stale.
  useEffect(() => {
    if (!open) return;
    setReason("");
    setError(null);
    setSubmitting(false);
    setArmed(localState !== "off");
    inputRef.current?.focus();

    let cancelled = false;
    api.commands
      .killSwitchStatus()
      .then((s) => {
        if (cancelled) return;
        setArmed(s.active);
        setLocalState(s.active ? "soft" : "off");
      })
      .catch(() => {
        // Keep the store-derived value; the input is still usable.
      });
    return () => {
      cancelled = true;
    };
  }, [open, localState, setLocalState]);

  // Esc closes.
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

  const handleSubmit = useCallback(
    async (e: FormEvent) => {
      e.preventDefault();
      if (!reason.trim()) {
        setError("Reason is required.");
        return;
      }
      setSubmitting(true);
      setError(null);
      try {
        const willActivate = !armed;
        await api.commands.killSwitchToggle(willActivate, reason.trim());
        setLocalState(willActivate ? "soft" : "off");
        toast.success(
          willActivate ? "Kill switch armed (soft)" : "Kill switch disarmed"
        );
        setOpen(false);
      } catch (e: unknown) {
        const msg = e instanceof Error ? e.message : "Could not change state";
        setError(msg);
      } finally {
        setSubmitting(false);
      }
    },
    [armed, reason, setLocalState, setOpen]
  );

  if (!open) return null;

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
      <div className="w-full max-w-md rounded-md border-2 border-warn-500 bg-bg-panel shadow-xl">
        <header className="px-5 py-4 border-b border-border-subtle flex items-start justify-between gap-2">
          <div>
            <h2
              id="kill-switch-modal-title"
              className="text-[15px] font-semibold text-fg"
            >
              {armed ? "Disarm kill switch?" : "Arm soft kill switch?"}
            </h2>
            <p className="text-[12px] text-fg-muted mt-1">
              {armed
                ? "Trading will resume immediately for all profiles."
                : "All new orders will be blocked across all profiles. Existing positions remain open."}
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
        <form onSubmit={handleSubmit} className="px-5 py-4 flex flex-col gap-3">
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
            />
          </label>
          {error && (
            <p className="text-[12px] text-danger-500" role="alert">
              {error}
            </p>
          )}
          <div className="flex items-center justify-end gap-2 pt-2">
            <Button
              type="button"
              intent="secondary"
              size="sm"
              onClick={handleClose}
              disabled={submitting}
            >
              Cancel
            </Button>
            <Button
              type="submit"
              intent={armed ? "primary" : "danger"}
              size="sm"
              leftIcon={
                submitting ? (
                  <Loader2 className="w-3.5 h-3.5 animate-spin" aria-hidden />
                ) : armed ? (
                  <Unlock className="w-3.5 h-3.5" strokeWidth={1.5} />
                ) : (
                  <Lock className="w-3.5 h-3.5" strokeWidth={1.5} />
                )
              }
              disabled={submitting}
            >
              {armed ? "Disarm" : "Arm soft"}
            </Button>
          </div>
        </form>
      </div>
    </div>
  );
}
