"use client";

import {
  forwardRef,
  useState,
  type HTMLAttributes,
} from "react";
import {
  Play,
  CircleDot,
  Save,
  X,
  TrendingUp,
  ShieldAlert,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { Button } from "@/components/primitives/Button";
import { Select, type SelectOption } from "@/components/primitives/Select";

/**
 * RunControlBar per docs/design/04-component-specs/canvas.md.
 *
 * Top bar of the Pipeline Canvas surface. Left: profile selector + dirty/
 * saved indicator. Right: three run buttons. Per spec, run-live is the
 * only one with `intent="primary"` color treatment AND it requires
 * confirmation when clicked.
 *
 * Critical UX rule (per spec): run-live and run-paper are visually
 * distinct — different colors AND different sizes — so the user can
 * never mistake "this is real money" for "this is paper money."
 */

export type RunActivity =
  | "idle"
  | "paper-active"
  | "live-active"
  | "backtesting-active";

export interface RunControlBarProps
  extends Omit<HTMLAttributes<HTMLDivElement>, "children"> {
  profileOptions: SelectOption[];
  activeProfileId?: string;
  onProfileChange?: (id: string) => void;
  /** Indicates unsaved changes on the canvas. */
  dirty?: boolean;
  /** Pretty-printed save state, e.g., "saved 3m ago". */
  savedAtText?: string;
  onSave?: () => void;
  activity?: RunActivity;
  onRunPaper?: () => void;
  onRunLive?: () => void;
  onRunBacktest?: () => void;
  onCancelBacktest?: () => void;
  /** Confirmation copy for the live run. Pass null to skip confirm. */
  liveConfirmText?: string | null;
}

const DEFAULT_LIVE_CONFIRM =
  "Run with live capital? This places real orders.";

export const RunControlBar = forwardRef<HTMLDivElement, RunControlBarProps>(
  (
    {
      profileOptions,
      activeProfileId,
      onProfileChange,
      dirty,
      savedAtText,
      onSave,
      activity = "idle",
      onRunPaper,
      onRunLive,
      onRunBacktest,
      onCancelBacktest,
      liveConfirmText = DEFAULT_LIVE_CONFIRM,
      className,
      ...props
    },
    ref
  ) => {
    const [liveArmed, setLiveArmed] = useState(false);
    const handleLiveClick = () => {
      if (liveConfirmText === null) {
        onRunLive?.();
        return;
      }
      if (!liveArmed) {
        setLiveArmed(true);
        return;
      }
      setLiveArmed(false);
      onRunLive?.();
    };

    return (
      <div
        ref={ref}
        role="toolbar"
        aria-label="Run controls"
        data-activity={activity}
        className={cn(
          "flex items-center gap-3 px-3 h-12 border-b border-border-subtle bg-bg-panel",
          className
        )}
        {...props}
      >
        {/* Profile selector */}
        <div className="flex items-center gap-2 flex-1 min-w-0">
          <Select
            options={profileOptions}
            value={activeProfileId}
            onValueChange={onProfileChange}
            density="compact"
            className="w-44"
            placeholder="Pick a profile…"
            aria-label="Active profile"
          />
          {/* Saved indicator */}
          {dirty ? (
            <span className="inline-flex items-center gap-1.5 text-[11px] text-warn-500">
              <CircleDot
                className="w-3 h-3"
                strokeWidth={2}
                aria-hidden
              />
              <span className="num-tabular">unsaved</span>
              {onSave && (
                <Button
                  size="xs"
                  intent="secondary"
                  onClick={onSave}
                  leftIcon={<Save className="w-3 h-3" strokeWidth={1.5} />}
                >
                  save
                </Button>
              )}
            </span>
          ) : savedAtText ? (
            <span className="inline-flex items-center gap-1.5 text-[11px] text-fg-muted num-tabular">
              <CircleDot
                className="w-2.5 h-2.5 text-fg-muted"
                strokeWidth={2}
                aria-hidden
              />
              {savedAtText}
            </span>
          ) : null}
        </div>

        {/* Backtest active overlay banner */}
        {activity === "backtesting-active" && (
          <div className="flex items-center gap-2 px-3 py-1 rounded-sm bg-accent-500/15 border border-accent-700/40 text-[11px] text-accent-300">
            <span className="inline-block w-2 h-2 rounded-full bg-accent-400 animate-pulse" />
            backtesting…
            {onCancelBacktest && (
              <button
                type="button"
                onClick={onCancelBacktest}
                aria-label="Cancel backtest"
                className="ml-1 hover:text-accent-200"
              >
                <X className="w-3 h-3" strokeWidth={1.5} aria-hidden />
              </button>
            )}
          </div>
        )}

        {/* Run buttons */}
        <div className="flex items-center gap-2">
          <Button
            size="sm"
            intent={activity === "paper-active" ? "bid" : "secondary"}
            onClick={onRunPaper}
            leftIcon={<Play className="w-3 h-3" strokeWidth={1.5} />}
            data-active={activity === "paper-active" || undefined}
            aria-pressed={activity === "paper-active"}
          >
            run paper
          </Button>

          <Button
            size="sm"
            intent="secondary"
            onClick={onRunBacktest}
            leftIcon={<TrendingUp className="w-3 h-3" strokeWidth={1.5} />}
            disabled={activity === "backtesting-active"}
          >
            run backtest
          </Button>

          {/* Live is BIGGER (size="md" vs size="sm") and uses intent="primary"
              when not armed; turns danger when armed (the consequence
              color for "you are about to use real capital"). */}
          <Button
            size="md"
            intent={
              liveArmed
                ? "danger"
                : activity === "live-active"
                  ? "primary"
                  : "primary"
            }
            onClick={handleLiveClick}
            leftIcon={
              liveArmed ? (
                <ShieldAlert className="w-3.5 h-3.5" strokeWidth={1.5} />
              ) : (
                <Play className="w-3.5 h-3.5" strokeWidth={1.5} />
              )
            }
            data-active={activity === "live-active" || undefined}
            aria-pressed={activity === "live-active"}
            data-testid="run-control-live"
            aria-label={
              liveArmed
                ? "Confirm run live"
                : activity === "live-active"
                  ? "Stop live run"
                  : "Run live"
            }
          >
            {liveArmed ? "click again to confirm" : "run live"}
          </Button>
        </div>
      </div>
    );
  }
);
RunControlBar.displayName = "RunControlBar";

export default RunControlBar;
