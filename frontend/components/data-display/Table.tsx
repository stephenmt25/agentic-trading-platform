"use client";

import { useEffect, useState, type ReactNode } from "react";
import { ChevronUp, ChevronDown, ChevronsUpDown } from "lucide-react";
import { cn } from "@/lib/utils";

export type SortDirection = "asc" | "desc";

export interface TableColumn<T> {
  /** Column key — used for `aria-sort` and the sort callback. */
  key: string;
  header: ReactNode;
  align?: "left" | "right" | "center";
  /** Numeric column: right-aligns + applies tabular numerics + mono font. */
  numeric?: boolean;
  sortable?: boolean;
  /** Fixed width or grow factor (CSS value). */
  width?: string;
  /** Custom cell renderer. Defaults to `row[key]`. */
  render?: (row: T, index: number) => ReactNode;
}

export interface TableProps<T> {
  data: T[];
  columns: TableColumn<T>[];
  /** Stable key per row — used for selection, flash, React keys. */
  rowKey: (row: T) => string;
  density?: "compact" | "standard" | "comfortable";
  gridLines?: "none" | "horizontal" | "both";
  striping?: "none" | "every-other";
  selectable?: "none" | "single";
  selectedRowKey?: string | null;
  onRowSelect?: (row: T) => void;
  onRowClick?: (row: T) => void;
  /** Sort state controlled by caller. */
  sortKey?: string;
  sortDirection?: SortDirection;
  /** Called when a sortable header is clicked. Caller does the sort. */
  onSortChange?: (key: string, direction: SortDirection) => void;
  /** Row keys currently flashing (price tick). Visual decay handled internally. */
  flashRowKey?: string | null;
  flashDirection?: "bid" | "ask";
  emptyMessage?: ReactNode;
  className?: string;
  /** Render a footer (e.g., totals). */
  footer?: ReactNode;
}

/**
 * Dense table per data-display.md. Supports:
 *   - density (compact 24h / standard 28h / comfortable 36h)
 *   - gridLines (none / horizontal / both)
 *   - striping (none / every-other — Calm mode only per spec)
 *   - sortable headers with `aria-sort`
 *   - sticky header
 *   - single-row selection with 2px accent.500 left bar + bg-rowhover
 *   - tick-flash animation on a row (bid/ask, decays over --duration-snap)
 *
 * Multi-select, groupBy, and full ARIA grid keyboard navigation are
 * deferred — Phase 6 Hot Trading is the first surface that needs cell
 * navigation; we'll extend then.
 *
 * Don't wrap text in cells (per spec). Use `text-ellipsis` overflow and
 * surface the full value in a tooltip on hover when needed.
 */
export function Table<T>({
  data,
  columns,
  rowKey,
  density = "standard",
  gridLines = "horizontal",
  striping = "none",
  selectable = "none",
  selectedRowKey,
  onRowSelect,
  onRowClick,
  sortKey,
  sortDirection,
  onSortChange,
  flashRowKey,
  flashDirection,
  emptyMessage = "No data.",
  className,
  footer,
}: TableProps<T>) {
  const rowHeight =
    density === "compact" ? "h-6" : density === "comfortable" ? "h-9" : "h-7";
  const headerHeight =
    density === "compact" ? "h-7" : density === "comfortable" ? "h-10" : "h-8";
  const cellSize = density === "compact" ? "text-xs" : "text-[13px]";

  const cellPadding = "px-3";

  // Tick-flash decay — clear the highlight after --duration-snap (180ms)
  const [flashKey, setFlashKey] = useState<string | null>(null);
  useEffect(() => {
    if (flashRowKey) {
      setFlashKey(flashRowKey);
      const t = window.setTimeout(() => setFlashKey(null), 180);
      return () => window.clearTimeout(t);
    }
  }, [flashRowKey]);

  const handleSort = (col: TableColumn<T>) => {
    if (!col.sortable || !onSortChange) return;
    if (sortKey === col.key) {
      onSortChange(col.key, sortDirection === "asc" ? "desc" : "asc");
    } else {
      onSortChange(col.key, col.numeric ? "desc" : "asc");
    }
  };

  return (
    <div className={cn("w-full overflow-x-auto", className)}>
      <table
        className={cn(
          "w-full border-collapse text-fg-secondary",
          gridLines === "both" && "border border-border-subtle"
        )}
      >
        <thead className="sticky top-0 z-10 bg-bg-panel">
          <tr>
            {columns.map((col) => {
              const isSortable = !!col.sortable;
              const isSorted = sortKey === col.key;
              const ariaSort: "ascending" | "descending" | "none" | undefined =
                isSortable
                  ? isSorted
                    ? sortDirection === "asc"
                      ? "ascending"
                      : "descending"
                    : "none"
                  : undefined;

              return (
                <th
                  key={col.key}
                  scope="col"
                  aria-sort={ariaSort}
                  style={col.width ? { width: col.width } : undefined}
                  className={cn(
                    headerHeight,
                    cellPadding,
                    "text-[10px] font-semibold uppercase tracking-wider text-fg-muted num-tabular",
                    "border-b border-border-subtle",
                    gridLines === "both" && "border-r border-border-subtle last:border-r-0",
                    col.align === "right" || col.numeric
                      ? "text-right"
                      : col.align === "center"
                        ? "text-center"
                        : "text-left"
                  )}
                >
                  {isSortable ? (
                    <button
                      type="button"
                      onClick={() => handleSort(col)}
                      className={cn(
                        "inline-flex items-center gap-1",
                        col.numeric || col.align === "right"
                          ? "flex-row-reverse"
                          : "",
                        "hover:text-fg",
                        "focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent-500 rounded-sm"
                      )}
                    >
                      <span>{col.header}</span>
                      {isSorted ? (
                        sortDirection === "asc" ? (
                          <ChevronUp
                            className="w-3 h-3"
                            strokeWidth={1.5}
                            aria-hidden
                          />
                        ) : (
                          <ChevronDown
                            className="w-3 h-3"
                            strokeWidth={1.5}
                            aria-hidden
                          />
                        )
                      ) : (
                        <ChevronsUpDown
                          className="w-3 h-3 text-fg-muted/60"
                          strokeWidth={1.5}
                          aria-hidden
                        />
                      )}
                    </button>
                  ) : (
                    <span>{col.header}</span>
                  )}
                </th>
              );
            })}
          </tr>
        </thead>

        <tbody>
          {data.length === 0 ? (
            <tr>
              <td
                colSpan={columns.length}
                className="py-6 text-center text-sm text-fg-muted"
              >
                {emptyMessage}
              </td>
            </tr>
          ) : (
            data.map((row, rowIdx) => {
              const k = rowKey(row);
              const isSelected = selectedRowKey === k;
              const isFlashing = flashKey === k;
              const interactive =
                selectable !== "none" || !!onRowClick || !!onRowSelect;

              return (
                <tr
                  key={k}
                  onClick={() => {
                    if (selectable === "single") onRowSelect?.(row);
                    onRowClick?.(row);
                  }}
                  aria-selected={
                    selectable === "single" ? isSelected : undefined
                  }
                  className={cn(
                    "relative transition-colors",
                    interactive && "cursor-pointer",
                    striping === "every-other" &&
                      rowIdx % 2 === 1 &&
                      "bg-bg-panel/40",
                    !isSelected && interactive && "hover:bg-bg-rowhover",
                    isSelected && "bg-bg-rowhover",
                    isFlashing && flashDirection === "bid" && "bg-bid-900/30",
                    isFlashing && flashDirection === "ask" && "bg-ask-900/30"
                  )}
                >
                  {columns.map((col, colIdx) => {
                    const value = col.render
                      ? col.render(row, rowIdx)
                      : (row as Record<string, unknown>)[col.key] as ReactNode;
                    const isFirst = colIdx === 0;
                    return (
                      <td
                        key={col.key}
                        className={cn(
                          rowHeight,
                          cellPadding,
                          cellSize,
                          "truncate text-fg",
                          gridLines !== "none" &&
                            "border-b border-border-subtle",
                          gridLines === "both" &&
                            "border-r border-border-subtle last:border-r-0",
                          col.numeric && "font-mono num-tabular text-right",
                          !col.numeric && col.align === "right" && "text-right",
                          col.align === "center" && "text-center",
                          isFirst && "relative"
                        )}
                      >
                        {isFirst && isSelected && (
                          <span
                            className="absolute left-0 top-0 bottom-0 w-0.5 bg-accent-500"
                            aria-hidden
                          />
                        )}
                        {value as ReactNode}
                      </td>
                    );
                  })}
                </tr>
              );
            })
          )}
        </tbody>

        {footer && (
          <tfoot className="border-t border-border-subtle bg-bg-panel">
            {footer}
          </tfoot>
        )}
      </table>
    </div>
  );
}

export default Table;
