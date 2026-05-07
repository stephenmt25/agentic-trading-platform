"use client";

import { forwardRef, type HTMLAttributes, type ReactNode, type ButtonHTMLAttributes, type Ref } from "react";
import { cva, type VariantProps } from "class-variance-authority";
import { X } from "lucide-react";
import { cn } from "@/lib/utils";

const pill = cva(
  [
    "inline-flex items-center gap-1.5 h-6 px-2.5 rounded-full",
    "text-[11px] font-medium num-tabular leading-none",
    "border whitespace-nowrap",
  ],
  {
    variants: {
      intent: {
        neutral: "bg-bg-canvas border-border-subtle text-fg-secondary",
        accent: "bg-accent-900/40 text-accent-300 border-accent-700/50",
        bid: "bg-bid-900/40 text-bid-300 border-bid-700/50",
        ask: "bg-ask-900/40 text-ask-300 border-ask-700/50",
        warn: "bg-warn-700/15 text-warn-400 border-warn-700/50",
        danger: "bg-danger-700/15 text-danger-500 border-danger-700/50",
      },
      active: {
        true: "bg-accent-500/15 text-accent-300 border-accent-500/40",
        false: "",
      },
    },
    defaultVariants: { intent: "neutral", active: false },
  }
);

interface PillBase extends VariantProps<typeof pill> {
  icon?: ReactNode;
  children: ReactNode;
}

interface StaticPillProps extends Omit<HTMLAttributes<HTMLSpanElement>, "color">, PillBase {
  as?: "static";
}

interface ClickablePillProps extends Omit<ButtonHTMLAttributes<HTMLButtonElement>, "color">, PillBase {
  as: "clickable";
}

interface RemovablePillProps extends Omit<HTMLAttributes<HTMLSpanElement>, "color">, PillBase {
  as: "removable";
  onRemove: () => void;
}

export type PillProps = StaticPillProps | ClickablePillProps | RemovablePillProps;

/**
 * Pill per data-display.md. 24h fixed, fully rounded. Three variants:
 *   - static: chrome status (e.g., "regime: choppy")
 *   - clickable: opens a drawer/popover; gets a hover ring
 *   - removable: filter chips; renders an x with `onRemove`
 *
 * `active` (filter selected, etc.) lifts intent to accent.500/15 fill
 * + accent.300 fg per spec.
 */
export const Pill = forwardRef<HTMLElement, PillProps>((props, ref) => {
  const { intent, active, icon, children, className, ...rest } = props;

  if (rest.as === "clickable") {
    const { as: _as, ...buttonProps } = rest;
    return (
      <button
        ref={ref as Ref<HTMLButtonElement>}
        type="button"
        className={cn(
          pill({ intent, active }),
          "transition-colors",
          "hover:ring-1 hover:ring-border-strong",
          "focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent-500",
          className
        )}
        {...(buttonProps as ButtonHTMLAttributes<HTMLButtonElement>)}
      >
        {icon && <span className="flex items-center" aria-hidden>{icon}</span>}
        <span>{children}</span>
      </button>
    );
  }

  if (rest.as === "removable") {
    const { as: _as, onRemove, ...spanProps } = rest;
    return (
      <span
        ref={ref as Ref<HTMLSpanElement>}
        className={cn(pill({ intent, active }), className)}
        {...(spanProps as HTMLAttributes<HTMLSpanElement>)}
      >
        {icon && <span className="flex items-center" aria-hidden>{icon}</span>}
        <span>{children}</span>
        <button
          type="button"
          onClick={onRemove}
          aria-label="Remove filter"
          className="ml-0.5 -mr-0.5 hover:text-fg focus-visible:outline-1 focus-visible:outline-current rounded-full"
        >
          <X className="w-3 h-3" strokeWidth={1.5} aria-hidden />
        </button>
      </span>
    );
  }

  const { as: _as, ...spanProps } = rest as StaticPillProps;
  return (
    <span
      ref={ref as Ref<HTMLSpanElement>}
      className={cn(pill({ intent, active }), className)}
      {...(spanProps as HTMLAttributes<HTMLSpanElement>)}
    >
      {icon && <span className="flex items-center" aria-hidden>{icon}</span>}
      <span>{children}</span>
    </span>
  );
});
Pill.displayName = "Pill";

export default Pill;
