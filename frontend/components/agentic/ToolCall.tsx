"use client";

import {
  forwardRef,
  useState,
  type HTMLAttributes,
  type ReactNode,
} from "react";
import {
  ChevronRight,
  Settings,
  Check,
  X,
  Loader2,
} from "lucide-react";
import { cn } from "@/lib/utils";

/**
 * ToolCall per docs/design/04-component-specs/agentic.md.
 *
 * Inline collapsible block within a ReasoningStream. Header carries the
 * tool name + duration + status; body collapsed by default. Args > ~40
 * chars are rendered as multi-line JSON (per spec — "the reader's eye
 * should never have to track sideways through long inline JSON").
 */

export type ToolCallStatus = "pending" | "complete" | "errored";

export interface ToolCallProps
  extends Omit<HTMLAttributes<HTMLDivElement>, "children"> {
  toolName: string;
  status: ToolCallStatus;
  /** Duration in ms (already measured by caller). */
  durationMs?: number;
  /** Tool args — pretty-printed when expanded. Pass any JSON-able value. */
  args?: unknown;
  /** Tool result — same. */
  result?: unknown;
  /** Error message, shown in body when status === "errored". */
  error?: string;
  /** Default-collapsed (true) or default-expanded (false). */
  defaultCollapsed?: boolean;
  /** Render extra body content after args+result. */
  footer?: ReactNode;
}

function fmtDuration(ms?: number): string | null {
  if (ms === undefined || ms === null) return null;
  if (ms < 1000) return `${ms.toFixed(0)}ms`;
  return `${(ms / 1000).toFixed(2)}s`;
}

function isLongArgs(args: unknown): boolean {
  if (args == null) return false;
  try {
    return JSON.stringify(args).length > 40;
  } catch {
    return false;
  }
}

function formatJSON(value: unknown, multiline: boolean): string {
  if (value === undefined) return "—";
  try {
    return multiline ? JSON.stringify(value, null, 2) : JSON.stringify(value);
  } catch {
    return String(value);
  }
}

export const ToolCall = forwardRef<HTMLDivElement, ToolCallProps>(
  (
    {
      toolName,
      status,
      durationMs,
      args,
      result,
      error,
      defaultCollapsed = true,
      footer,
      className,
      ...props
    },
    ref
  ) => {
    const [collapsed, setCollapsed] = useState(defaultCollapsed);
    const argsMultiline = isLongArgs(args);

    return (
      <div
        ref={ref}
        role="group"
        aria-label={`Tool call: ${toolName}`}
        data-status={status}
        className={cn(
          "rounded-sm border border-border-subtle bg-bg-raised",
          className
        )}
        {...props}
      >
        <button
          type="button"
          onClick={() => setCollapsed((c) => !c)}
          aria-expanded={!collapsed}
          className={cn(
            "w-full flex items-center gap-2 px-2 h-7 text-[11px] font-mono num-tabular",
            "text-fg-secondary hover:text-fg",
            "focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent-500"
          )}
        >
          <ChevronRight
            className={cn(
              "w-3 h-3 text-fg-muted transition-transform",
              !collapsed && "rotate-90"
            )}
            strokeWidth={1.5}
            aria-hidden
          />
          <Settings
            className={cn(
              "w-3 h-3",
              status === "pending" ? "text-accent-500 animate-spin" : "text-fg-muted"
            )}
            strokeWidth={1.5}
            aria-hidden
          />
          <span className="text-fg-muted">tool · </span>
          <span className="text-fg">{toolName}</span>
          <span className="flex-1" />
          {durationMs !== undefined && (
            <span className="text-fg-muted">{fmtDuration(durationMs)}</span>
          )}
          {status === "pending" && (
            <Loader2
              className="w-3 h-3 text-accent-500 animate-spin"
              strokeWidth={1.5}
              aria-hidden
            />
          )}
          {status === "complete" && (
            <Check
              className="w-3.5 h-3.5 text-bid-500"
              strokeWidth={2}
              aria-label="completed"
            />
          )}
          {status === "errored" && (
            <X
              className="w-3.5 h-3.5 text-ask-500"
              strokeWidth={2}
              aria-label="errored"
            />
          )}
        </button>

        {!collapsed && (
          <div className="border-t border-border-subtle p-2 flex flex-col gap-2">
            <Section label="args">
              <pre
                className={cn(
                  "text-[11px] font-mono text-fg-secondary",
                  argsMultiline ? "whitespace-pre" : "whitespace-pre-wrap"
                )}
              >
                {formatJSON(args, argsMultiline)}
              </pre>
            </Section>

            {status !== "errored" ? (
              <Section label="result">
                <pre className="text-[11px] font-mono text-fg-secondary whitespace-pre-wrap">
                  {formatJSON(result, true)}
                </pre>
              </Section>
            ) : (
              <Section label="error">
                <pre className="text-[11px] font-mono text-ask-300 whitespace-pre-wrap">
                  {error ?? "Unknown error"}
                </pre>
              </Section>
            )}

            {footer}
          </div>
        )}
      </div>
    );
  }
);
ToolCall.displayName = "ToolCall";

function Section({
  label,
  children,
}: {
  label: string;
  children: ReactNode;
}) {
  return (
    <div className="flex items-start gap-2">
      <span className="text-[10px] uppercase tracking-wider text-fg-muted w-12 shrink-0 mt-0.5 num-tabular">
        {label}
      </span>
      <div className="flex-1 min-w-0">{children}</div>
    </div>
  );
}

export default ToolCall;
