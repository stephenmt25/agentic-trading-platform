"use client";

import {
  cloneElement,
  isValidElement,
  useEffect,
  useId,
  useRef,
  useState,
  type ReactElement,
  type ReactNode,
} from "react";
import { useMode } from "@/components/providers/ModeProvider";
import { cn } from "@/lib/utils";

type Placement = "top" | "bottom" | "left" | "right";

export interface TooltipProps {
  content: ReactNode;
  placement?: Placement;
  /** Override the default mode-aware open delay (HOT 250ms, others 600ms). */
  openDelayMs?: number;
  /** When true, never show the tooltip. Useful for disabled triggers. */
  disabled?: boolean;
  children: ReactElement;
}

/**
 * Tooltip per primitives.md. Hover or focus to open after a mode-aware
 * delay (HOT mode 250ms; other modes 600ms). Closes 80ms after pointer
 * leaves or focus moves away.
 *
 * Tooltips are progressive disclosure — never put critical information
 * in them per the spec. Critical state belongs in visible chrome.
 */
export function Tooltip({
  content,
  placement = "top",
  openDelayMs,
  disabled,
  children,
}: TooltipProps) {
  const mode = useMode();
  const [isOpen, setIsOpen] = useState(false);
  const openTimer = useRef<number | null>(null);
  const closeTimer = useRef<number | null>(null);
  const id = useId();

  const openDelay = openDelayMs ?? (mode === "hot" ? 250 : 600);
  const closeDelay = 80;

  const open = () => {
    if (disabled) return;
    if (closeTimer.current) window.clearTimeout(closeTimer.current);
    if (openTimer.current) window.clearTimeout(openTimer.current);
    openTimer.current = window.setTimeout(() => setIsOpen(true), openDelay);
  };
  const close = () => {
    if (openTimer.current) window.clearTimeout(openTimer.current);
    if (closeTimer.current) window.clearTimeout(closeTimer.current);
    closeTimer.current = window.setTimeout(() => setIsOpen(false), closeDelay);
  };

  useEffect(
    () => () => {
      if (openTimer.current) window.clearTimeout(openTimer.current);
      if (closeTimer.current) window.clearTimeout(closeTimer.current);
    },
    []
  );

  if (!isValidElement(children)) return <>{children}</>;

  const childProps = (children.props ?? {}) as Record<string, unknown>;
  const trigger = cloneElement(children, {
    ...childProps,
    "aria-describedby": isOpen ? id : (childProps["aria-describedby"] as string | undefined),
    onMouseEnter: open,
    onMouseLeave: close,
    onFocus: open,
    onBlur: close,
  } as Record<string, unknown>);

  const placementClasses: Record<Placement, string> = {
    top: "bottom-full left-1/2 -translate-x-1/2 mb-1.5",
    bottom: "top-full left-1/2 -translate-x-1/2 mt-1.5",
    left: "right-full top-1/2 -translate-y-1/2 mr-1.5",
    right: "left-full top-1/2 -translate-y-1/2 ml-1.5",
  };

  return (
    <span className="relative inline-flex">
      {trigger}
      {isOpen && !disabled && (
        <span
          role="tooltip"
          id={id}
          className={cn(
            "absolute z-40 pointer-events-none",
            "px-2 py-1 rounded-sm",
            "bg-bg-raised border border-border-subtle shadow-lg",
            "text-[11px] text-fg whitespace-nowrap max-w-xs",
            placementClasses[placement]
          )}
        >
          {content}
        </span>
      )}
    </span>
  );
}

export default Tooltip;
