"use client";

import { type HTMLAttributes, forwardRef } from "react";
import { cva, type VariantProps } from "class-variance-authority";
import { cn } from "@/lib/utils";

const dot = cva(
  "inline-block rounded-full",
  {
    variants: {
      state: {
        live: "bg-bid-500",
        idle: "bg-neutral-400",
        warn: "bg-warn-500",
        error: "bg-ask-500",
        armed: "bg-danger-500",
      },
      size: {
        6: "w-1.5 h-1.5",
        8: "w-2 h-2",
        10: "w-2.5 h-2.5",
      },
    },
    defaultVariants: { state: "idle", size: 8 },
  }
);

export interface StatusDotProps
  extends Omit<HTMLAttributes<HTMLSpanElement>, "color">,
    VariantProps<typeof dot> {
  /** Add a 1.4s pulse. Per spec: only allowed for `live` and `armed`. */
  pulse?: boolean;
}

/**
 * Status dot per data-display.md. The pulse is restricted to "live" and
 * "armed" states by spec — pulsing on idle/error would be a noise pattern.
 */
export const StatusDot = forwardRef<HTMLSpanElement, StatusDotProps>(
  ({ state, size, pulse, className, "aria-label": ariaLabel, ...props }, ref) => {
    const allowPulse = pulse && (state === "live" || state === "armed");
    return (
      <span
        ref={ref}
        role="status"
        aria-label={ariaLabel ?? `Status: ${state ?? "idle"}`}
        className={cn(
          "relative inline-flex items-center justify-center",
          className
        )}
        {...props}
      >
        <span className={dot({ state, size })} aria-hidden />
        {allowPulse && (
          <span
            className={cn(
              dot({ state, size }),
              "absolute inset-0 m-auto opacity-60 animate-ping"
            )}
            aria-hidden
          />
        )}
      </span>
    );
  }
);
StatusDot.displayName = "StatusDot";

export default StatusDot;
