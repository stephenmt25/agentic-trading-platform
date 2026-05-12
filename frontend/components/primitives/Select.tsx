"use client";

import {
  useEffect,
  useId,
  useRef,
  useState,
  type KeyboardEvent,
} from "react";
import { ChevronDown } from "lucide-react";
import { cn } from "@/lib/utils";

export interface SelectOption {
  value: string;
  label: string;
  disabled?: boolean;
}

export interface SelectProps {
  options: SelectOption[];
  value?: string;
  onValueChange?: (value: string) => void;
  placeholder?: string;
  label?: string;
  hint?: string;
  error?: string;
  disabled?: boolean;
  density?: "compact" | "standard" | "comfortable";
  className?: string;
  /** When true, disables typing-to-filter behavior (defaults to off for v1). */
  searchable?: boolean;
}

/**
 * Single-select dropdown per primitives.md. WAI-ARIA combobox pattern:
 * arrow keys navigate, Enter selects, Esc closes, typing filters when
 * `searchable` is on (v1: filter logic is a local string match).
 *
 * Multi-select and inline-search-affordance variants from the spec are
 * not implemented in v1 — flag as a known follow-up if a surface needs
 * them before Phase 6.
 */
export function Select({
  options,
  value,
  onValueChange,
  placeholder = "Select…",
  label,
  hint,
  error,
  disabled,
  density = "standard",
  className,
  searchable = false,
}: SelectProps) {
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");
  const [activeIndex, setActiveIndex] = useState<number>(-1);

  const triggerRef = useRef<HTMLButtonElement>(null);
  const listRef = useRef<HTMLUListElement>(null);

  const id = useId();
  const labelId = `${id}-label`;
  const listboxId = `${id}-listbox`;
  const hintId = `${id}-hint`;
  const errorId = `${id}-error`;

  const selected = options.find((o) => o.value === value);

  const filtered = searchable
    ? options.filter((o) =>
        o.label.toLowerCase().includes(query.trim().toLowerCase())
      )
    : options;

  // Sync activeIndex when opened
  useEffect(() => {
    if (open) {
      const initial = filtered.findIndex((o) => o.value === value);
      setActiveIndex(initial >= 0 ? initial : 0);
    } else {
      setQuery("");
    }
    // intentionally only react to open
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open]);

  // Close on outside click
  useEffect(() => {
    if (!open) return;
    const handle = (e: MouseEvent) => {
      const t = e.target as Node;
      if (!triggerRef.current?.contains(t) && !listRef.current?.contains(t)) {
        setOpen(false);
      }
    };
    document.addEventListener("mousedown", handle);
    return () => document.removeEventListener("mousedown", handle);
  }, [open]);

  const move = (delta: number) => {
    if (filtered.length === 0) return;
    const enabledIdx = filtered
      .map((o, i) => (o.disabled ? -1 : i))
      .filter((i) => i !== -1);
    if (enabledIdx.length === 0) return;
    const cur = enabledIdx.indexOf(activeIndex);
    const next = (cur + delta + enabledIdx.length) % enabledIdx.length;
    setActiveIndex(enabledIdx[next]);
  };

  const onTriggerKeyDown = (e: KeyboardEvent) => {
    if (e.key === "Enter" || e.key === " " || e.key === "ArrowDown") {
      e.preventDefault();
      setOpen(true);
    }
  };

  const onListKeyDown = (e: KeyboardEvent) => {
    if (e.key === "ArrowDown") {
      e.preventDefault();
      move(1);
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      move(-1);
    } else if (e.key === "Home") {
      e.preventDefault();
      setActiveIndex(0);
    } else if (e.key === "End") {
      e.preventDefault();
      setActiveIndex(filtered.length - 1);
    } else if (e.key === "Enter") {
      e.preventDefault();
      const opt = filtered[activeIndex];
      if (opt && !opt.disabled) {
        onValueChange?.(opt.value);
        setOpen(false);
        triggerRef.current?.focus();
      }
    } else if (e.key === "Escape") {
      e.preventDefault();
      setOpen(false);
      triggerRef.current?.focus();
    } else if (e.key === "Tab") {
      setOpen(false);
    }
  };

  const heightClass =
    density === "compact"
      ? "h-7 px-2 text-xs"
      : density === "comfortable"
        ? "h-10 px-3 text-sm"
        : "h-8 px-3 text-sm";

  return (
    <div className={cn("relative inline-flex flex-col gap-1.5", className)}>
      {label && (
        <span id={labelId} className="text-xs font-medium text-fg-secondary">
          {label}
        </span>
      )}
      <button
        ref={triggerRef}
        type="button"
        role="combobox"
        aria-haspopup="listbox"
        aria-expanded={open}
        aria-controls={listboxId}
        aria-labelledby={label ? labelId : undefined}
        aria-invalid={error ? true : undefined}
        aria-describedby={error ? errorId : hint ? hintId : undefined}
        disabled={disabled}
        onClick={() => setOpen((v) => !v)}
        onKeyDown={onTriggerKeyDown}
        className={cn(
          "inline-flex items-center justify-between gap-2 rounded-md text-left",
          "bg-bg-raised border border-border-subtle text-fg",
          "transition-colors duration-150 hover:border-border-strong",
          "focus:outline-none focus:border-accent-500 focus:ring-2 focus:ring-accent-500/20",
          "disabled:bg-bg-panel disabled:text-fg-disabled disabled:cursor-not-allowed",
          "aria-[invalid=true]:border-ask-500",
          heightClass
        )}
      >
        <span className={cn("truncate flex-1", !selected && "text-fg-muted")}>
          {selected?.label ?? placeholder}
        </span>
        <ChevronDown
          className="w-3.5 h-3.5 text-fg-muted shrink-0"
          strokeWidth={1.5}
          aria-hidden
        />
      </button>

      {open && (
        <div
          className="absolute left-0 right-0 z-40 mt-1 top-full"
          style={{ minWidth: triggerRef.current?.offsetWidth ?? "auto" }}
        >
          {searchable && (
            <div className="px-2 pt-2 pb-1 bg-bg-panel border border-b-0 border-border-subtle rounded-t-md">
              <input
                type="text"
                autoFocus
                value={query}
                onChange={(e) => {
                  setQuery(e.target.value);
                  setActiveIndex(0);
                }}
                onKeyDown={onListKeyDown}
                placeholder="Filter…"
                className="w-full bg-bg-raised border border-border-subtle rounded-sm h-7 px-2 text-xs text-fg placeholder:text-fg-muted focus:outline-none focus:border-accent-500"
                aria-label="Filter options"
              />
            </div>
          )}
          <ul
            ref={listRef}
            id={listboxId}
            role="listbox"
            tabIndex={-1}
            aria-labelledby={label ? labelId : undefined}
            onKeyDown={onListKeyDown}
            className={cn(
              "max-h-60 overflow-y-auto py-1",
              "border border-border-subtle bg-bg-panel shadow-lg",
              searchable ? "rounded-b-md" : "rounded-md"
            )}
          >
            {filtered.length === 0 ? (
              <li className="px-3 py-2 text-sm text-fg-muted">No results.</li>
            ) : (
              filtered.map((opt, i) => {
                const isSelected = opt.value === value;
                const isActive = i === activeIndex;
                return (
                  <li
                    key={opt.value}
                    role="option"
                    aria-selected={isSelected}
                    aria-disabled={opt.disabled || undefined}
                    onClick={() => {
                      if (opt.disabled) return;
                      onValueChange?.(opt.value);
                      setOpen(false);
                      triggerRef.current?.focus();
                    }}
                    onMouseEnter={() => setActiveIndex(i)}
                    className={cn(
                      "relative px-3 py-1.5 text-sm cursor-pointer flex items-center justify-between gap-3",
                      opt.disabled
                        ? "text-fg-disabled cursor-not-allowed"
                        : "text-fg-secondary hover:text-fg",
                      !opt.disabled && isActive && "bg-bg-rowhover",
                      !opt.disabled && isSelected && "bg-bg-raised text-fg"
                    )}
                  >
                    {isSelected && (
                      <span
                        className="absolute left-0 top-0 bottom-0 w-0.5 bg-accent-500"
                        aria-hidden
                      />
                    )}
                    <span className="truncate">{opt.label}</span>
                  </li>
                );
              })
            )}
          </ul>
        </div>
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

export default Select;
