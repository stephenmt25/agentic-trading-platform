"use client";

import { forwardRef, type HTMLAttributes, type SVGProps } from "react";
import { cva, type VariantProps } from "class-variance-authority";
import { cn } from "@/lib/utils";

/**
 * AgentAvatar per docs/design/04-component-specs/agentic.md.
 *
 * Per ADR-012, all six agent identities alias to --color-accent-500;
 * differentiation is by glyph + label + position only. Glyphs are
 * abstract (no faces, no AI clichés) and distinctive at 20×20 —
 * single-stroke 1.5px outlined per ADR-012 "Consequences".
 */

export type AgentKind =
  | "ta"
  | "regime"
  | "sentiment"
  | "slm"
  | "debate"
  | "analyst";

export type AgentStatus = "live" | "idle" | "errored" | "silenced";

const AGENT_LABELS: Record<AgentKind, string> = {
  ta: "ta_agent",
  regime: "regime_hmm",
  sentiment: "sentiment",
  slm: "slm_inference",
  debate: "debate",
  analyst: "analyst",
};

const ring = cva(
  [
    "relative inline-flex items-center justify-center shrink-0 rounded-full",
    "bg-bg-panel",
    // Per ADR-012, ring uses --color-agent-{name} which all alias to accent.
    "ring-[1.5px]",
  ],
  {
    variants: {
      size: {
        sm: "w-6 h-6",
        md: "w-8 h-8",
        lg: "w-10 h-10",
      },
    },
    defaultVariants: { size: "md" },
  }
);

interface GlyphProps extends SVGProps<SVGSVGElement> {
  size?: number;
}

/** Glyph: ta_agent — segmented bar (sparkline-like). */
function TAGlyph({ size = 16, ...props }: GlyphProps) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={1.5}
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden
      {...props}
    >
      <line x1="5" y1="16" x2="5" y2="13" />
      <line x1="9" y1="16" x2="9" y2="9" />
      <line x1="13" y1="16" x2="13" y2="11" />
      <line x1="17" y1="16" x2="17" y2="6" />
      <line x1="3.5" y1="18.5" x2="18.5" y2="18.5" />
    </svg>
  );
}

/** Glyph: regime_hmm — three connected nodes (state diagram). */
function RegimeGlyph({ size = 16, ...props }: GlyphProps) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={1.5}
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden
      {...props}
    >
      <circle cx="6" cy="8" r="1.75" />
      <circle cx="18" cy="8" r="1.75" />
      <circle cx="12" cy="17" r="1.75" />
      <line x1="7.5" y1="8" x2="16.5" y2="8" />
      <line x1="7" y1="9.5" x2="11" y2="15.5" />
      <line x1="17" y1="9.5" x2="13" y2="15.5" />
    </svg>
  );
}

/** Glyph: sentiment — wave shape. */
function SentimentGlyph({ size = 16, ...props }: GlyphProps) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={1.5}
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden
      {...props}
    >
      <path d="M3 14 C 6 9, 9 9, 12 14 S 18 19, 21 14" />
    </svg>
  );
}

/** Glyph: slm_inference — speech-bracket. */
function SLMGlyph({ size = 16, ...props }: GlyphProps) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={1.5}
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden
      {...props}
    >
      <path d="M7 6 L 4 9 L 4 15 L 7 18" />
      <path d="M17 6 L 20 9 L 20 15 L 17 18" />
      <line x1="9" y1="12" x2="11" y2="12" />
      <line x1="13" y1="12" x2="15" y2="12" />
    </svg>
  );
}

/** Glyph: debate — three radiating lines (synthesis). */
function DebateGlyph({ size = 16, ...props }: GlyphProps) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={1.5}
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden
      {...props}
    >
      <circle cx="12" cy="12" r="1.5" />
      <line x1="12" y1="3.5" x2="12" y2="8.5" />
      <line x1="4" y1="18.5" x2="8.5" y2="14.5" />
      <line x1="20" y1="18.5" x2="15.5" y2="14.5" />
    </svg>
  );
}

/** Glyph: analyst — pen-on-page. */
function AnalystGlyph({ size = 16, ...props }: GlyphProps) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={1.5}
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden
      {...props}
    >
      <path d="M5 19 L 14 10 L 17 13 L 8 22" transform="translate(0 -3)" />
      <line x1="14" y1="7" x2="17" y2="10" />
      <line x1="3.5" y1="20" x2="20.5" y2="20" />
    </svg>
  );
}

const GLYPHS: Record<AgentKind, (p: GlyphProps) => React.ReactElement> = {
  ta: TAGlyph,
  regime: RegimeGlyph,
  sentiment: SentimentGlyph,
  slm: SLMGlyph,
  debate: DebateGlyph,
  analyst: AnalystGlyph,
};

const STATUS_DOT_CX: Record<AgentStatus, string> = {
  live: "bg-bid-500",
  idle: "bg-neutral-500",
  errored: "bg-ask-500",
  silenced: "bg-neutral-700",
};

const STATUS_LABEL: Record<AgentStatus, string> = {
  live: "live",
  idle: "idle",
  errored: "errored",
  silenced: "silenced",
};

export interface AgentAvatarProps
  extends Omit<HTMLAttributes<HTMLSpanElement>, "size">,
    VariantProps<typeof ring> {
  kind: AgentKind;
  status?: AgentStatus;
  /** Show the agent's name to the right of the avatar. */
  withName?: boolean | "below";
  /** Override the default agent label. */
  nameOverride?: string;
}

export const AgentAvatar = forwardRef<HTMLSpanElement, AgentAvatarProps>(
  (
    { kind, size, status, withName, nameOverride, className, ...props },
    ref
  ) => {
    const Glyph = GLYPHS[kind];
    const label = nameOverride ?? AGENT_LABELS[kind];
    const glyphSize = size === "sm" ? 14 : size === "lg" ? 20 : 16;
    const dotSize = size === "sm" ? 6 : size === "lg" ? 9 : 7;

    const avatar = (
      <span
        ref={ref}
        aria-label={`${label} avatar${status ? `, ${STATUS_LABEL[status]}` : ""}`}
        className={cn(
          ring({ size }),
          "ring-accent-500 text-fg",
          className
        )}
        {...props}
      >
        <Glyph size={glyphSize} />
        {status && (
          <span
            aria-hidden
            data-status={status}
            className={cn(
              "absolute -right-0.5 -bottom-0.5 rounded-full ring-1 ring-bg-canvas",
              STATUS_DOT_CX[status],
              status === "live" && "animate-pulse"
            )}
            style={{ width: dotSize, height: dotSize }}
          />
        )}
      </span>
    );

    if (!withName) return avatar;
    if (withName === "below") {
      return (
        <span className="inline-flex flex-col items-center gap-1">
          {avatar}
          <span className="text-[10px] text-fg-secondary num-tabular tracking-tight">
            {label}
          </span>
        </span>
      );
    }
    return (
      <span className="inline-flex items-center gap-2">
        {avatar}
        <span className="text-[12px] text-fg-secondary num-tabular tracking-tight">
          {label}
        </span>
      </span>
    );
  }
);
AgentAvatar.displayName = "AgentAvatar";

export default AgentAvatar;
