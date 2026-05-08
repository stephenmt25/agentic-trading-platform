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
      appearance: { solid: "", subtle: "" },
    },
    compoundVariants: [
      {
        intent: "neutral",
        appearance: "solid",
        className: "bg-neutral-700 text-fg border-transparent",
      },
      {
        intent: "neutral",
        appearance: "subtle",
        className: "bg-neutral-800 text-fg-secondary border-border-subtle",
      },
      {
        intent: "accent",
        appearance: "solid",
        className: "bg-accent-500 text-white border-transparent",
      },
      {
        intent: "accent",
        appearance: "subtle",
        className:
          "bg-accent-900/40 text-accent-300 border-accent-700/50",
      },
      {
        intent: "bid",
        appearance: "solid",
        className: "bg-bid-500 text-neutral-950 border-transparent",
      },
      {
        intent: "bid",
        appearance: "subtle",
        className: "bg-bid-900/40 text-bid-300 border-bid-700/50",
      },
      {
        intent: "ask",
        appearance: "solid",
        className: "bg-ask-500 text-white border-transparent",
      },
      {
        intent: "ask",
        appearance: "subtle",
        className: "bg-ask-900/40 text-ask-300 border-ask-700/50",
      },
      {
        intent: "warn",
        appearance: "solid",
        className: "bg-warn-500 text-neutral-950 border-transparent",
      },
      {
        intent: "warn",
        appearance: "subtle",
        className:
          "bg-warn-700/30 text-warn-400 border-warn-700/50",
      },
      {
        intent: "danger",
        appearance: "solid",
        className: "bg-danger-500 text-white border-transparent",
      },
      {
        intent: "danger",
        appearance: "subtle",
        className:
          "bg-danger-700/30 text-danger-500 border-danger-700/50",
      },
      // agent intent — per ADR-012 aliases to accent
      {
        intent: "agent",
        appearance: "solid",
        className: "bg-accent-500 text-white border-transparent",
      },
      {
        intent: "agent",
        appearance: "subtle",
        className:
          "bg-accent-900/40 text-accent-300 border-accent-700/50",
      },
    ],
    defaultVariants: { intent: "neutral", appearance: "subtle" },
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
 * ADR-012). subtle is the default appearance; solid is for emphasis.
 *
 * The CVA variant is named `appearance` (not `style`) to avoid colliding
 * with React's standard `style` prop on HTMLAttributes — see
 * docs/design/REPLICATION-PLAYBOOK.md §6.2.
 */
export const Tag = forwardRef<HTMLSpanElement, TagProps>(
  ({ intent, appearance, dot, onDismiss, children, className, ...props }, ref) => {
    return (
      <span ref={ref} className={cn(tag({ intent, appearance }), className)} {...props}>
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
