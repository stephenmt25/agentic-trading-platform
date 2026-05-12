"use client";

import { forwardRef, type HTMLAttributes, type ReactNode } from "react";
import { cva, type VariantProps } from "class-variance-authority";
import { Cog, Bot } from "lucide-react";
import { cn } from "@/lib/utils";

const avatar = cva(
  [
    "relative inline-flex items-center justify-center shrink-0 select-none",
    "rounded-full bg-bg-raised text-fg-secondary",
    "border border-border-subtle overflow-hidden",
    "font-medium leading-none",
  ],
  {
    variants: {
      size: {
        sm: "w-6 h-6 text-[10px]",
        md: "w-8 h-8 text-xs",
        lg: "w-10 h-10 text-sm",
      },
    },
    defaultVariants: { size: "md" },
  }
);

const statusDot = cva("absolute -bottom-0.5 -right-0.5 rounded-full ring-2 ring-bg-canvas", {
  variants: {
    size: {
      sm: "w-2 h-2",
      md: "w-2.5 h-2.5",
      lg: "w-3 h-3",
    },
    status: {
      active: "bg-bid-500",
      idle: "bg-neutral-500",
      errored: "bg-ask-500",
    },
  },
  defaultVariants: { size: "md", status: "idle" },
});

interface AvatarBase
  extends Omit<HTMLAttributes<HTMLSpanElement>, "children">,
    VariantProps<typeof avatar> {
  status?: "active" | "idle" | "errored";
}

interface UserAvatarProps extends AvatarBase {
  kind?: "user";
  src?: string;
  name?: string;
  alt?: string;
}

interface AgentAvatarProps extends AvatarBase {
  kind: "agent";
  glyph?: ReactNode;
  /** Reserved for future per-agent treatment; today all agents alias to accent (ADR-012). */
  agent?: "ta" | "regime" | "sentiment" | "slm" | "debate" | "analyst";
}

interface SystemAvatarProps extends AvatarBase {
  kind: "system";
}

export type AvatarProps = UserAvatarProps | AgentAvatarProps | SystemAvatarProps;

function initials(name: string | undefined): string {
  if (!name) return "??";
  const parts = name.split(" ").filter(Boolean);
  return parts
    .map((p) => p[0])
    .join("")
    .toUpperCase()
    .slice(0, 2);
}

/**
 * Avatar primitive per primitives.md. Three kinds:
 *   - user: image or initials
 *   - agent: glyph + accent ring (per ADR-012, all agents share the
 *     accent identity color; differentiation is by glyph + position)
 *   - system: gear glyph
 *
 * Status dot (active/idle/errored) is reserved for Observatory and
 * audit views per the spec — don't show in HOT mode.
 */
export const Avatar = forwardRef<HTMLSpanElement, AvatarProps>((props, ref) => {
  const { size, status, className, ...rest } = props;
  const kind = (rest as { kind?: "user" | "agent" | "system" }).kind ?? "user";

  let content: ReactNode;
  let extraClass = "";

  if (kind === "agent") {
    const ag = rest as AgentAvatarProps;
    extraClass = "ring-1 ring-accent-500/60";
    content = ag.glyph ?? <Bot className="w-1/2 h-1/2" strokeWidth={1.5} aria-hidden />;
  } else if (kind === "system") {
    content = <Cog className="w-1/2 h-1/2" strokeWidth={1.5} aria-hidden />;
  } else {
    const user = rest as UserAvatarProps;
    if (user.src) {
      content = (
        // eslint-disable-next-line @next/next/no-img-element
        <img
          src={user.src}
          alt={user.alt ?? user.name ?? ""}
          className="w-full h-full object-cover"
        />
      );
    } else {
      content = <span>{initials(user.name)}</span>;
    }
  }

  // Strip kind-specific props from the DOM spread
  const {
    kind: _kind,
    src: _src,
    name: _name,
    alt: _alt,
    glyph: _glyph,
    agent: _agent,
    ...domProps
  } = rest as Record<string, unknown>;

  return (
    <span
      ref={ref}
      className={cn(avatar({ size }), extraClass, className)}
      {...(domProps as HTMLAttributes<HTMLSpanElement>)}
    >
      {content}
      {status && (
        <span
          className={statusDot({ size, status })}
          aria-label={`Status: ${status}`}
        />
      )}
    </span>
  );
});
Avatar.displayName = "Avatar";

export default Avatar;
