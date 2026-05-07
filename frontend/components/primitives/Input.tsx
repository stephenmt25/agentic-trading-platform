"use client";

import { forwardRef, useId, type InputHTMLAttributes, type ReactNode } from "react";
import { cva, type VariantProps } from "class-variance-authority";
import { cn } from "@/lib/utils";

const inputCx = cva(
  [
    "w-full bg-bg-raised text-fg",
    "border border-border-subtle rounded-md",
    "transition-colors duration-150",
    "placeholder:text-fg-muted",
    "focus:outline-none focus:border-accent-500 focus:ring-2 focus:ring-accent-500/20",
    "hover:border-border-strong",
    "disabled:bg-bg-panel disabled:text-fg-disabled disabled:cursor-not-allowed disabled:hover:border-border-subtle",
    "aria-[invalid=true]:border-ask-500 aria-[invalid=true]:focus:ring-ask-500/20 aria-[invalid=true]:focus:border-ask-500",
  ],
  {
    variants: {
      density: {
        compact: "h-7 px-2 text-xs",
        standard: "h-8 px-3 text-sm",
        comfortable: "h-10 px-3 text-sm",
      },
      mono: { true: "font-mono", false: "" },
      numeric: { true: "text-right num-tabular", false: "" },
    },
    defaultVariants: {
      density: "standard",
      mono: false,
      numeric: false,
    },
  }
);

export interface InputProps
  extends Omit<InputHTMLAttributes<HTMLInputElement>, "size">,
    VariantProps<typeof inputCx> {
  label?: string;
  hint?: string;
  error?: string;
  leftAdornment?: ReactNode;
  rightAdornment?: ReactNode;
}

/**
 * Text input per primitives.md. Always pair with a `label` (visible or
 * `aria-label`) — relying on `placeholder` alone fails screen readers
 * and dyslexia accessibility per the "Don't" list.
 *
 * `numeric` enables tabular numerals + right alignment + inputMode="decimal".
 * `mono` switches the value to mono font (API keys / hashes).
 */
export const Input = forwardRef<HTMLInputElement, InputProps>(
  (
    {
      label,
      hint,
      error,
      leftAdornment,
      rightAdornment,
      density,
      mono,
      numeric,
      id,
      className,
      ...props
    },
    ref
  ) => {
    const generatedId = useId();
    const inputId = id ?? generatedId;
    const hintId = `${inputId}-hint`;
    const errorId = `${inputId}-error`;
    const describedBy = error ? errorId : hint ? hintId : undefined;

    const inputEl = (
      <input
        ref={ref}
        id={inputId}
        aria-invalid={error ? true : undefined}
        aria-describedby={describedBy}
        inputMode={numeric ? "decimal" : props.inputMode}
        className={cn(
          inputCx({ density, mono, numeric }),
          leftAdornment ? "pl-9" : undefined,
          rightAdornment ? "pr-9" : undefined,
          className
        )}
        {...props}
      />
    );

    return (
      <div className="flex flex-col gap-1.5">
        {label && (
          <label
            htmlFor={inputId}
            className="text-xs font-medium text-fg-secondary"
          >
            {label}
          </label>
        )}
        {leftAdornment || rightAdornment ? (
          <div className="relative">
            {leftAdornment && (
              <div className="absolute left-3 top-1/2 -translate-y-1/2 flex items-center text-fg-muted pointer-events-none">
                {leftAdornment}
              </div>
            )}
            {inputEl}
            {rightAdornment && (
              <div className="absolute right-3 top-1/2 -translate-y-1/2 flex items-center text-fg-muted">
                {rightAdornment}
              </div>
            )}
          </div>
        ) : (
          inputEl
        )}
        {error ? (
          <p id={errorId} className="text-[11px] text-ask-500" role="alert">
            {error}
          </p>
        ) : hint ? (
          <p id={hintId} className="text-[11px] text-fg-muted">
            {hint}
          </p>
        ) : null}
      </div>
    );
  }
);
Input.displayName = "Input";

export default Input;
