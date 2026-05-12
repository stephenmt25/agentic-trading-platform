import { describe, it, expect } from "vitest";
import { render, screen, within } from "@testing-library/react";
import { OrderBook, type OrderBookLevel } from "./OrderBook";

/**
 * Critical-path tests per frontend/DESIGN.md:
 * the OrderBook must virtualize, must NOT animate row insertion, and
 * must encode side via color contract (bid/ask family only — never
 * accent/warn/danger on data rows). The mid badge may use neutral or
 * warn (when wide).
 */

const BIDS: OrderBookLevel[] = [
  { price: 42318.27, size: 0.5 },
  { price: 42317.5, size: 1.2 },
  { price: 42316.0, size: 0.8 },
];
const ASKS: OrderBookLevel[] = [
  { price: 42319.0, size: 0.4 },
  { price: 42320.5, size: 0.9 },
  { price: 42322.0, size: 1.1 },
];

describe("OrderBook — critical-path", () => {
  it("renders bid and ask rows in cumulative-fill grid", () => {
    render(<OrderBook bids={BIDS} asks={ASKS} />);
    const grid = screen.getByRole("grid");
    expect(grid).toHaveAttribute("aria-label", "Order book");
    // 6 levels = 6 rows
    const rows = within(grid).getAllByRole("row");
    expect(rows).toHaveLength(6);
  });

  it("encodes side on each row via data-side attribute (color contract)", () => {
    render(<OrderBook bids={BIDS} asks={ASKS} />);
    const grid = screen.getByRole("grid");
    const rows = within(grid).getAllByRole("row");
    const sides = rows.map((r) => r.getAttribute("data-side"));
    expect(sides.every((s) => s === "bid" || s === "ask")).toBe(true);
    // We must have both
    expect(sides).toContain("bid");
    expect(sides).toContain("ask");
  });

  it("computes cumulative size per row in priority order", () => {
    render(<OrderBook bids={BIDS} asks={ASKS} />);
    const grid = screen.getByRole("grid");
    // best bid (highest price) is the first level cumulating
    // labels are "Bid <price>, size <size>, cumulative <cum>"
    const bestBidRow = within(grid).getByLabelText(
      /Bid 42,318.27, size 0.5000, cumulative 0.5000/
    );
    expect(bestBidRow).toBeInTheDocument();
    // second bid level cumulates: 0.5 + 1.2 = 1.7
    const secondBidRow = within(grid).getByLabelText(
      /Bid 42,317.50, size 1.2000, cumulative 1.7000/
    );
    expect(secondBidRow).toBeInTheDocument();
  });

  it("computes spread bps and shows mid bar", () => {
    render(<OrderBook bids={BIDS} asks={ASKS} />);
    const sep = screen.getByRole("separator");
    // best bid 42318.27, best ask 42319.00 → spread 0.73, mid 42318.635
    // bps = 0.73/42318.635 * 10000 ≈ 0.17
    expect(sep).toHaveAttribute("aria-label");
    // mid = (42318.27 + 42319.00) / 2 = 42318.635 (toLocaleString rounds 0.5 down via FP rep)
    expect(sep.getAttribute("aria-label")).toMatch(/Mid 42,318\.6[34]/);
    expect(sep.getAttribute("aria-label")).toMatch(/0\.[12] bps/);
  });

  it("marks mid bar as wide-spread when above threshold", () => {
    // huge ask gap to force wide spread
    const wideBids: OrderBookLevel[] = [{ price: 100, size: 1 }];
    const wideAsks: OrderBookLevel[] = [{ price: 110, size: 1 }];
    render(<OrderBook bids={wideBids} asks={wideAsks} wideSpreadBps={50} />);
    const sep = screen.getByRole("separator");
    expect(sep).toHaveAttribute("data-wide-spread", "true");
  });

  it("does NOT use motion-affecting animation classes on rows (snap-only per spec)", () => {
    render(<OrderBook bids={BIDS} asks={ASKS} />);
    const grid = screen.getByRole("grid");
    const rows = within(grid).getAllByRole("row");
    for (const r of rows) {
      const cls = r.className;
      // The spec says: SNAP, don't animate row insertion. Reject any
      // transition / animate utility on the row container.
      expect(cls).not.toMatch(/\btransition-/);
      expect(cls).not.toMatch(/\banimate-/);
    }
  });

  it("uses ARIA grid for keyboard navigation contract", () => {
    render(<OrderBook bids={BIDS} asks={ASKS} />);
    const grid = screen.getByRole("grid");
    // grid is keyboard-focusable
    expect(grid.getAttribute("tabindex")).toBe("0");
    const rowgroups = within(grid).getAllByRole("rowgroup");
    expect(rowgroups.length).toBeGreaterThanOrEqual(2);
  });
});
