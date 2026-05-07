"use client";

import { forwardRef, type HTMLAttributes, type ReactNode } from "react";
import { cva, type VariantProps } from "class-variance-authority";
import { cn } from "@/lib/utils";

const wrapper = cva("", {
  variants: {
    layout: {
      inline: "flex items-baseline justify-between gap-3",
      stacked: "flex flex-col gap-0.5",
    },
  },
  defaultVariants: { layout: "inline" },
});

const labelCx = cva("text-fg-muted text-[11px] font-medium uppercase tracking-wider num-tabular leading-none", {
  variants: {
    weight: {
      "value-emphasis": "",
      equal: "text-fg-secondary",
    },
  },
  defaultVariants: { weight: "value-emphasis" },
});

const valueCx = cva("font-mono num-tabular leading-tight", {
  variants: {
    weight: {
      "value-emphasis": "text-fg font-semibold",
      equal: "text-fg font-medium",
    },
    align: {
      left: "text-left",
      right: "text-right",
    },
    tone: {
      default: "",
      bid: "text-bid-400",
      ask: "text-ask-500",
      muted: "text-fg-muted",
    },
  },
  defaultVariants: { weight: "value-emphasis", align: "right", tone: "default" },
});

interface KeyValueOwnProps {
  label: ReactNode;
  value: ReactNode;
  hint?: ReactNode;
}

export interface KeyValueProps
  extends Omit<HTMLAttributes<HTMLDivElement>, "children">,
    VariantProps<typeof wrapper>,
    VariantProps<typeof valueCx>,
    KeyValueOwnProps {}

/**
 * KeyValue per data-display.md. Renders a label/value pair, with the
 * value the protagonist (per Principle P1: "numbers are the protagonist").
 *
 * Layouts:
 *   - inline (default): label left, value right-aligned
 *   - stacked: label above value, both left-aligned
 *
 * For numeric values (PnL, position size, etc.), pass tone="bid" |
 * "ask" to color-code positive/negative cash-flow direction.
 */
export const KeyValue = forwardRef<HTMLDivElement, KeyValueProps>(
  (
    { label, value, hint, layout, weight, align, tone, className, ...props },
    ref
  ) => {
    const isStacked = layout === "stacked";
    return (
      <div
        ref={ref}
        className={cn(wrapper({ layout }), className)}
        {...props}
      >
        <span className={labelCx({ weight })}>{label}</span>
        <span className="flex flex-col items-end">
          <span
            className={valueCx({
              weight,
              align: isStacked ? "left" : align,
              tone,
            })}
          >
            {value}
          </span>
          {hint && (
            <span className="text-[10px] text-fg-muted num-tabular mt-0.5">
              {hint}
            </span>
          )}
        </span>
      </div>
    );
  }
);
KeyValue.displayName = "KeyValue";

export default KeyValue;
