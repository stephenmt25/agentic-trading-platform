"use client";

import {
  forwardRef,
  useEffect,
  useMemo,
  useRef,
  useState,
  type HTMLAttributes,
  type ReactNode,
} from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { cn } from "@/lib/utils";

/**
 * ReasoningStream per docs/design/04-component-specs/agentic.md.
 *
 * A pane that progressively renders LLM tokens as they arrive. The
 * cursor lives at the bottom and the layout above does NOT reflow on
 * append (we add to the tail; the tail is what grows).
 *
 * Rendering modes:
 *   - prose: markdown via react-markdown (default)
 *   - json: monospace block, no markdown parsing
 *   - xml-tags: monospace, with <thinking> blocks rendered in an inset
 *
 * The component is controlled — caller passes `content` (the running
 * concatenated text) and a `state` describing where in the lifecycle
 * the stream is. The component does NOT manage the network connection
 * itself; that's the caller's job.
 */

export type ReasoningStreamState = "streaming" | "paused" | "done" | "errored";
export type ReasoningStreamMode = "prose" | "json" | "xml-tags";

export interface ReasoningStreamProps
  extends Omit<HTMLAttributes<HTMLDivElement>, "children"> {
  /** Current text content (caller appends as tokens arrive). */
  content: string;
  state: ReasoningStreamState;
  mode?: ReasoningStreamMode;
  /** Render as a single line + ellipsis (Hot Trading inline use). */
  inline?: boolean;
  /** Show the type-on cursor. Default true when state === "streaming". */
  liveCursor?: boolean;
  /** Meta line shown after `done`. e.g., "1.2s · 287 tokens · sonnet-4-6". */
  meta?: ReactNode;
  /** Error message when state === "errored". */
  error?: string;
  /** Auto-scroll to bottom on content change (default true). */
  autoScroll?: boolean;
  /** Optional fixed max height; the pane scrolls inside. */
  maxHeight?: number | string;
  /** When true, lock the cursor at the bottom edge instead of the
   *  end of content. Useful when content is short and would otherwise
   *  pull the cursor to the middle. */
  cursorAtBottom?: boolean;
  /** Resume action handler (called when paused state is clicked). */
  onResume?: () => void;
}

/**
 * Split text into a sequence of segments, separating <thinking>...</thinking>
 * blocks for special rendering. Used by mode="xml-tags".
 */
function splitThinking(text: string): Array<
  | { kind: "text"; value: string }
  | { kind: "thinking"; value: string }
  | { kind: "thinking-open"; value: string }
> {
  const parts: ReturnType<typeof splitThinking> = [];
  const re = /<thinking>([\s\S]*?)(<\/thinking>|$)/g;
  let lastIndex = 0;
  let m: RegExpExecArray | null;
  while ((m = re.exec(text)) !== null) {
    if (m.index > lastIndex) {
      parts.push({ kind: "text", value: text.slice(lastIndex, m.index) });
    }
    if (m[2] === "</thinking>") {
      parts.push({ kind: "thinking", value: m[1] });
    } else {
      // open but not yet closed (mid-stream)
      parts.push({ kind: "thinking-open", value: m[1] });
    }
    lastIndex = re.lastIndex;
  }
  if (lastIndex < text.length) {
    parts.push({ kind: "text", value: text.slice(lastIndex) });
  }
  return parts;
}

function ProseBody({ text }: { text: string }) {
  return (
    <div
      className={cn(
        "prose prose-invert prose-sm max-w-none",
        // tighten the rhythm — Reasoning is dense, not editorial
        "prose-p:my-1 prose-headings:my-2 prose-pre:my-2 prose-pre:bg-bg-raised prose-pre:rounded-sm",
        "prose-code:text-accent-300 prose-code:before:content-[''] prose-code:after:content-['']",
        "prose-strong:text-fg",
        "[&_pre_code]:bg-transparent [&_pre_code]:p-0 [&_pre_code]:text-fg-secondary"
      )}
    >
      <ReactMarkdown remarkPlugins={[remarkGfm]}>{text}</ReactMarkdown>
    </div>
  );
}

function JsonBody({ text }: { text: string }) {
  return (
    <pre className="text-[12px] font-mono text-fg-secondary whitespace-pre-wrap leading-relaxed bg-bg-raised rounded-sm p-2 overflow-x-auto">
      {text}
    </pre>
  );
}

function XmlTagsBody({ text }: { text: string }) {
  const parts = useMemo(() => splitThinking(text), [text]);
  return (
    <div className="text-[12px] font-mono text-fg-secondary leading-relaxed">
      {parts.map((p, i) => {
        if (p.kind === "text") {
          return (
            <span key={i} className="whitespace-pre-wrap">
              {p.value}
            </span>
          );
        }
        const open = p.kind === "thinking-open";
        return (
          <ThinkingBlock key={i} open={open} text={p.value} />
        );
      })}
    </div>
  );
}

function ThinkingBlock({ open, text }: { open: boolean; text: string }) {
  const [collapsed, setCollapsed] = useState(false);
  return (
    <div
      data-thinking={open ? "open" : "closed"}
      className={cn(
        "my-1 rounded-sm border-l-2 border-border-subtle bg-bg-raised/50",
        "px-2 py-1 text-fg-muted/90"
      )}
    >
      <button
        type="button"
        onClick={() => setCollapsed((c) => !c)}
        aria-expanded={!collapsed}
        className="text-[10px] uppercase tracking-wider text-fg-muted hover:text-fg-secondary"
      >
        {collapsed ? "▸" : "▾"} thinking{open ? " (in progress)" : ""}
      </button>
      {!collapsed && (
        <div className="whitespace-pre-wrap mt-1">{text}</div>
      )}
    </div>
  );
}

export const ReasoningStream = forwardRef<HTMLDivElement, ReasoningStreamProps>(
  (
    {
      content,
      state,
      mode = "prose",
      inline = false,
      liveCursor,
      meta,
      error,
      autoScroll = true,
      maxHeight,
      cursorAtBottom,
      onResume,
      className,
      ...props
    },
    ref
  ) => {
    const showCursor = liveCursor ?? state === "streaming";
    const innerRef = useRef<HTMLDivElement>(null);

    // Auto-scroll to bottom on content change while streaming.
    useEffect(() => {
      if (!autoScroll || !innerRef.current) return;
      if (state !== "streaming") return;
      innerRef.current.scrollTop = innerRef.current.scrollHeight;
    }, [content, autoScroll, state]);

    if (inline) {
      return (
        <div
          ref={ref}
          role="status"
          aria-live="polite"
          data-state={state}
          className={cn(
            "inline-flex items-center gap-1.5 max-w-full",
            "text-[12px] num-tabular text-fg-secondary",
            className
          )}
          {...props}
        >
          <span className="truncate">
            {content || (state === "streaming" ? "…" : "")}
          </span>
          {showCursor && (
            <span
              aria-hidden
              className="inline-block w-[1px] h-[12px] bg-accent-500 animate-pulse"
            />
          )}
        </div>
      );
    }

    const Body =
      mode === "json"
        ? JsonBody
        : mode === "xml-tags"
          ? XmlTagsBody
          : ProseBody;

    return (
      <div
        ref={ref}
        role="status"
        aria-live="polite"
        data-state={state}
        data-mode={mode}
        className={cn(
          "relative flex flex-col gap-1 rounded-sm border border-border-subtle bg-bg-panel",
          state === "errored" && "border-ask-700/40",
          className
        )}
        {...props}
      >
        <div
          ref={innerRef}
          className={cn(
            "flex flex-col gap-1 px-3 py-2 overflow-y-auto",
            cursorAtBottom && "min-h-20"
          )}
          style={
            maxHeight !== undefined
              ? {
                  maxHeight:
                    typeof maxHeight === "number" ? `${maxHeight}px` : maxHeight,
                }
              : undefined
          }
        >
          <Body text={content} />
          {showCursor && (
            <span
              aria-hidden
              className={cn(
                "inline-block w-[2px] h-[14px] bg-accent-500",
                state === "streaming" ? "animate-pulse" : "opacity-50"
              )}
            />
          )}
          {state === "errored" && error && (
            <p className="text-[11px] text-ask-300 mt-1">{error}</p>
          )}
        </div>
        {state === "paused" && (
          <button
            type="button"
            onClick={onResume}
            className={cn(
              "text-[11px] text-accent-300 hover:text-accent-200 px-3 py-1",
              "border-t border-border-subtle bg-bg-raised/50",
              "focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent-500"
            )}
          >
            paused — click to resume
          </button>
        )}
        {meta && state === "done" && (
          <div className="text-[10px] text-fg-muted px-3 py-1 border-t border-border-subtle font-mono num-tabular">
            {meta}
          </div>
        )}
      </div>
    );
  }
);
ReasoningStream.displayName = "ReasoningStream";

export default ReasoningStream;
