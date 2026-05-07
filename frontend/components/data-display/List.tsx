"use client";

import {
  forwardRef,
  type HTMLAttributes,
  type ReactNode,
  type ButtonHTMLAttributes,
} from "react";
import { cva, type VariantProps } from "class-variance-authority";
import { cn } from "@/lib/utils";

const list = cva("flex flex-col w-full", {
  variants: {
    spacing: {
      compact: "gap-1",
      standard: "gap-2",
      comfortable: "gap-3",
    },
    dividers: {
      none: "",
      between: "gap-0 divide-y divide-border-subtle",
    },
  },
  defaultVariants: { spacing: "standard", dividers: "none" },
});

const itemCx = cva(
  "flex items-center gap-3 w-full text-left",
  {
    variants: {
      interactive: {
        true: "rounded-md px-2 hover:bg-bg-rowhover transition-colors cursor-pointer focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent-500",
        false: "",
      },
      dense: {
        true: "py-1",
        false: "py-2",
      },
      withDividers: {
        true: "py-2 first:pt-0 last:pb-0",
        false: "",
      },
    },
    defaultVariants: { interactive: false, dense: false, withDividers: false },
  }
);

export interface ListProps
  extends HTMLAttributes<HTMLDivElement>,
    VariantProps<typeof list> {
  children: ReactNode;
}

export interface ListItemProps
  extends Omit<ButtonHTMLAttributes<HTMLButtonElement>, "type"> {
  leading?: ReactNode;
  meta?: ReactNode;
  action?: ReactNode;
  interactive?: boolean;
  dense?: boolean;
  withDividers?: boolean;
  children: ReactNode;
}

/**
 * List per data-display.md. A vertical stack of items with leading
 * (avatar/icon), content, meta, and optional action.
 *
 * Per spec "Don't": don't mix interactive and non-interactive items in
 * the same list — choose one mode per list. The component doesn't
 * enforce this; callers should pick consistent values.
 */
export const List = forwardRef<HTMLDivElement, ListProps>(
  ({ spacing, dividers, className, children, ...props }, ref) => {
    return (
      <div
        ref={ref}
        role="list"
        className={cn(list({ spacing, dividers }), className)}
        {...props}
      >
        {children}
      </div>
    );
  }
);
List.displayName = "List";

export const ListItem = forwardRef<HTMLButtonElement, ListItemProps>(
  (
    { leading, meta, action, interactive, dense, withDividers, children, className, ...props },
    ref
  ) => {
    const Component = interactive ? "button" : "div";
    const componentProps = interactive
      ? { ...props, ref, type: "button" as const }
      : ({} as Record<string, unknown>);

    return (
      <Component
        // @ts-expect-error — element-type union
        role="listitem"
        className={cn(itemCx({ interactive, dense, withDividers }), className)}
        {...(componentProps as ButtonHTMLAttributes<HTMLButtonElement>)}
      >
        {leading && (
          <span className="shrink-0 flex items-center" aria-hidden={!interactive}>
            {leading}
          </span>
        )}
        <span className="flex-1 min-w-0 text-sm text-fg truncate">
          {children}
        </span>
        {meta && (
          <span className="shrink-0 text-xs text-fg-muted num-tabular">
            {meta}
          </span>
        )}
        {action && <span className="shrink-0 ml-1">{action}</span>}
      </Component>
    );
  }
);
ListItem.displayName = "ListItem";
