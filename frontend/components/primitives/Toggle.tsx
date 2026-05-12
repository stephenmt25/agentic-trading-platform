"use client";

import { forwardRef, type ButtonHTMLAttributes } from "react";
import { cva, type VariantProps } from "class-variance-authority";
import { cn } from "@/lib/utils";

const track = cva(
  [
    "relative inline-flex shrink-0 items-center",
    "rounded-full",
    "transition-colors duration-150",
    "focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent-500",
    "disabled:cursor-not-allowed",
  ],
  {
    variants: {
      size: {
        sm: "h-4 w-7",
        md: "h-5 w-9",
      },
      tone: {
        accent:
          "bg-neutral-700 data-[state=on]:bg-accent-500 disabled:bg-neutral-800",
        bid: "bg-neutral-700 data-[state=on]:bg-bid-500 disabled:bg-neutral-800",
        danger:
          "bg-neutral-700 data-[state=on]:bg-danger-500 disabled:bg-neutral-800",
      },
    },
    defaultVariants: { size: "md", tone: "accent" },
  }
);

const thumb = cva(
  "block rounded-full bg-fg shadow-sm transition-transform duration-150 disabled:bg-neutral-500",
  {
    variants: {
      size: {
        sm: "h-3 w-3 translate-x-0.5 data-[state=on]:translate-x-3.5",
        md: "h-4 w-4 translate-x-0.5 data-[state=on]:translate-x-4",
      },
    },
    defaultVariants: { size: "md" },
  }
);

export interface ToggleProps
  extends Omit<ButtonHTMLAttributes<HTMLButtonElement>, "type" | "onChange">,
    VariantProps<typeof track> {
  checked: boolean;
  onCheckedChange: (next: boolean) => void;
  /** Accessible label for the switch when no visible label sits beside it */
  label?: string;
}

/**
 * Switch / toggle per primitives.md. role="switch" + aria-checked.
 * Tone variants:
 *   - accent (default): general settings
 *   - bid: opt-in (positive/affirmative)
 *   - danger: kill-switch arming (paired with confirmOnArm in the surface)
 *
 * The two-stage confirmation for kill-switch arming is a SURFACE concern
 * per the spec — implement that pattern at the call site, not here.
 */
export const Toggle = forwardRef<HTMLButtonElement, ToggleProps>(
  (
    {
      checked,
      onCheckedChange,
      size,
      tone,
      label,
      disabled,
      className,
      ...props
    },
    ref
  ) => {
    const state = checked ? "on" : "off";
    return (
      <button
        ref={ref}
        type="button"
        role="switch"
        aria-checked={checked}
        aria-label={label}
        data-state={state}
        disabled={disabled}
        onClick={() => onCheckedChange(!checked)}
        className={cn(track({ size, tone }), className)}
        {...props}
      >
        <span data-state={state} className={thumb({ size })} aria-hidden />
      </button>
    );
  }
);
Toggle.displayName = "Toggle";

export default Toggle;
