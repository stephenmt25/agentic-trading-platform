"use client";

import { forwardRef, type ButtonHTMLAttributes, type ReactNode } from "react";
import { cva, type VariantProps } from "class-variance-authority";
import { Loader2 } from "lucide-react";
import { cn } from "@/lib/utils";

const button = cva(
  [
    "inline-flex items-center justify-center gap-2",
    "font-medium tracking-tight whitespace-nowrap",
    "transition-colors duration-150",
    "focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent-500",
    "disabled:cursor-not-allowed",
  ],
  {
    variants: {
      intent: {
        primary:
          "bg-accent-500 text-white hover:bg-accent-600 active:bg-accent-700 disabled:bg-bg-raised disabled:text-fg-disabled",
        secondary:
          "bg-transparent border border-border-subtle text-fg hover:bg-bg-raised hover:border-border-strong active:bg-bg-panel disabled:text-fg-disabled disabled:hover:bg-transparent disabled:hover:border-border-subtle",
        danger:
          "bg-danger-500 text-white hover:bg-danger-600 active:bg-danger-700 disabled:bg-bg-raised disabled:text-fg-disabled",
        bid: "bg-bid-500 text-neutral-950 hover:bg-bid-600 active:bg-bid-700 disabled:bg-bg-raised disabled:text-fg-disabled",
        ask: "bg-ask-500 text-white hover:bg-ask-600 active:bg-ask-700 disabled:bg-bg-raised disabled:text-fg-disabled",
      },
      size: {
        xs: "h-6 px-2 text-[11px] rounded-sm",
        sm: "h-7 px-2.5 text-xs rounded-sm",
        md: "h-8 px-3 text-sm rounded-md",
        lg: "h-10 px-4 text-sm rounded-md",
      },
      iconOnly: {
        true: "px-0 aspect-square",
        false: "",
      },
    },
    defaultVariants: {
      intent: "secondary",
      size: "md",
      iconOnly: false,
    },
  }
);

export interface ButtonProps
  extends ButtonHTMLAttributes<HTMLButtonElement>,
    VariantProps<typeof button> {
  loading?: boolean;
  leftIcon?: ReactNode;
  rightIcon?: ReactNode;
  /** Right-side keyboard hint (use Kbd) */
  shortcut?: ReactNode;
}

/**
 * Button primitive per docs/design/04-component-specs/primitives.md.
 *
 * Anatomy: [icon? | label | shortcut?]. Default intent is "secondary"
 * (ghost) per the spec's default state. Use intent="primary" for the
 * one obvious action per visible viewport. intent="danger" is reserved
 * for kill-switch / hard-violation territory; use "secondary" with
 * confirmation for ordinary destructive actions.
 */
export const Button = forwardRef<HTMLButtonElement, ButtonProps>(
  (
    {
      intent,
      size,
      iconOnly,
      loading,
      leftIcon,
      rightIcon,
      shortcut,
      children,
      className,
      disabled,
      type,
      ...props
    },
    ref
  ) => {
    return (
      <button
        ref={ref}
        type={type ?? "button"}
        disabled={disabled || loading}
        aria-busy={loading || undefined}
        className={cn(button({ intent, size, iconOnly }), className)}
        {...props}
      >
        {loading ? (
          <Loader2 className="w-3.5 h-3.5 animate-spin" aria-hidden />
        ) : (
          leftIcon && <span aria-hidden>{leftIcon}</span>
        )}
        {!iconOnly && children}
        {!iconOnly && rightIcon && <span aria-hidden>{rightIcon}</span>}
        {!iconOnly && shortcut && <span className="ml-1">{shortcut}</span>}
      </button>
    );
  }
);
Button.displayName = "Button";

export default Button;
