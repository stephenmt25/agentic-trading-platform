"use client";

import { useEffect, type ReactNode } from "react";
import { X } from "lucide-react";
import { cn } from "@/lib/utils";

interface DetailDrawerProps {
  open: boolean;
  onClose: () => void;
  title: string;
  subtitle?: ReactNode;
  /** Right-aligned slot for actions (e.g. an "open in chrome" link). */
  actions?: ReactNode;
  children: ReactNode;
  /** Test hook for telemetry; rendered into the root data attribute. */
  kind?: string;
}

/**
 * Master-detail right-side drawer for table row drill-through. 400px wide
 * on desktop, full-width on small viewports. Backdrop click + Esc dismisses.
 *
 * Selection state is owned by the consumer (typically a URL query param so
 * detail views are shareable). The drawer just renders the open/closed
 * affordance and the body container.
 */
export function DetailDrawer({
  open,
  onClose,
  title,
  subtitle,
  actions,
  children,
  kind,
}: DetailDrawerProps) {
  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        e.preventDefault();
        onClose();
      }
    };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [open, onClose]);

  if (!open) return null;

  return (
    <div
      data-drawer-kind={kind}
      className="fixed inset-0 z-30 flex justify-end"
      role="dialog"
      aria-modal="true"
      aria-label={title}
    >
      <button
        type="button"
        aria-label="Close detail"
        onClick={onClose}
        className="absolute inset-0 bg-bg-canvas/50 backdrop-blur-[1px] cursor-default"
      />
      <aside
        className={cn(
          "relative h-full w-full sm:w-[420px] flex flex-col",
          "bg-bg-panel border-l border-border-subtle shadow-2xl",
          "animate-in slide-in-from-right duration-150"
        )}
      >
        <header className="shrink-0 flex items-start gap-2 border-b border-border-subtle px-4 py-3">
          <div className="min-w-0 flex-1">
            <h2 className="text-[13px] font-medium text-fg truncate">
              {title}
            </h2>
            {subtitle && (
              <div className="text-[11px] text-fg-muted truncate mt-0.5">
                {subtitle}
              </div>
            )}
          </div>
          {actions && (
            <div className="flex items-center gap-1.5 shrink-0">{actions}</div>
          )}
          <button
            type="button"
            onClick={onClose}
            aria-label="Close"
            className={cn(
              "shrink-0 h-7 w-7 rounded-md flex items-center justify-center",
              "text-fg-muted hover:text-fg hover:bg-bg-raised",
              "focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent-500"
            )}
          >
            <X className="w-4 h-4" strokeWidth={1.5} aria-hidden />
          </button>
        </header>
        <div className="flex-1 min-h-0 overflow-auto">{children}</div>
      </aside>
    </div>
  );
}
