"use client";

import { forwardRef, type HTMLAttributes, type ReactNode } from "react";
import { cva, type VariantProps } from "class-variance-authority";
import { X } from "lucide-react";
import { cn } from "@/lib/utils";

const tag = cva(
  [
    "inline-flex items-center gap-1 h-5 px-1.5 rounded-sm",
    "text-[11px] font-medium num-tabular leading-none",
    "border",
  ],
  {
    variants: {
      intent: {
        neutral: "",
        accent: "",
        bid: "",
        ask: "",
        warn: "",
        danger: "",
        agent: "",
      },
      style: { solid: "", subtle: "" },
    },
    compoundVariants: [
      {
        intent: "neutral",
        style: "solid",
        className: "bg-neutral-700 text-fg border-transparent",
      },
      {
        intent: "neutral",
        style: "subtle",
        className: "bg-neutral-800 text-fg-secondary border-border-subtle",
      },
      {
        intent: "accent",
        style: "solid",
        className: "bg-accent-500 text-white border-transparent",
      },
      {
        intent: "accent",
        style: "subtle",
        className:
          "bg-accent-900/40 text-accent-300 border-accent-700/50",
      },
      {
        intent: "bid",
        style: "solid",
        className: "bg-bid-500 text-neutral-950 border-transparent",
      },
      {
        intent: "bid",
        style: "subtle",
        className: "bg-bid-900/40 text-bid-300 border-bid-700/50",
      },
      {
        intent: "ask",
        style: "solid",
        className: "bg-ask-500 text-white border-transparent",
      },
      {
        intent: "ask",
        style: "subtle",
        className: "bg-ask-900/40 text-ask-300 border-ask-700/50",
      },
      {
        intent: "warn",
        style: "solid",
        className: "bg-warn-500 text-neutral-950 border-transparent",
      },
      {
        intent: "warn",
        style: "subtle",
        className:
          "bg-warn-700/30 text-warn-400 border-warn-700/50",
      },
      {
        intent: "danger",
        style: "solid",
        className: "bg-danger-500 text-white border-transparent",
      },
      {
        intent: "danger",
        style: "subtle",
        className:
          "bg-danger-700/30 text-danger-500 border-danger-700/50",
      },
      // agent intent — per ADR-012 aliases to accent
      {
        intent: "agent",
        style: "solid",
        className: "bg-accent-500 text-white border-transparent",
      },
      {
        intent: "agent",
        style: "subtle",
        className:
          "bg-accent-900/40 text-accent-300 border-accent-700/50",
      },
    ],
    defaultVariants: { intent: "neutral", style: "subtle" },
  }
);

export interface TagProps
  extends HTMLAttributes<HTMLSpanElement>,
    VariantProps<typeof tag> {
  dot?: boolean;
  onDismiss?: () => void;
  children: ReactNode;
}

/**
 * Tag / Badge per primitives.md. Fixed 20px height, 11px num-tabular
 * label. Six chromatic intents + agent (which aliases to accent per
 * ADR-012). subtle is the default style; solid is for emphasis.
 */
export const Tag = forwardRef<HTMLSpanElement, TagProps>(
  ({ intent, style, dot, onDismiss, children, className, ...props }, ref) => {
    return (
      <span ref={ref} className={cn(tag({ intent, style }), className)} {...props}>
        {dot && <span className="w-1.5 h-1.5 rounded-full bg-current" aria-hidden />}
        <span>{children}</span>
        {onDismiss && (
          <button
            type="button"
            onClick={onDismiss}
            aria-label="Dismiss"
            className="ml-0.5 -mr-0.5 hover:text-fg focus-visible:outline-1 focus-visible:outline-current rounded-sm"
          >
            <X className="w-3 h-3" strokeWidth={1.5} aria-hidden />
          </button>
        )}
      </span>
    );
  }
);
Tag.displayName = "Tag";

export default Tag;
