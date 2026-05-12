import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

/**
 * PriceChart tests focus on the React shell — header, tabs, slots, summary,
 * loading/empty/error treatments. The lightweight-charts canvas itself is
 * mocked out (jsdom can't paint canvases meaningfully and the library
 * mutates DOM imperatively in ways that don't add coverage value here).
 */

vi.mock("lightweight-charts", () => {
  const series = {
    setData: vi.fn(),
    update: vi.fn(),
    applyOptions: vi.fn(),
    priceScale: () => ({ applyOptions: vi.fn() }),
  };
  return {
    createChart: vi.fn(() => ({
      addSeries: vi.fn(() => series),
      applyOptions: vi.fn(),
      remove: vi.fn(),
    })),
    CandlestickSeries: "CandlestickSeries",
    HistogramSeries: "HistogramSeries",
  };
});

// ResizeObserver isn't in jsdom by default.
beforeEach(() => {
  (globalThis as { ResizeObserver?: unknown }).ResizeObserver = class {
    observe() {}
    unobserve() {}
    disconnect() {}
  };
});

import { PriceChart, type PriceChartCandle } from "./PriceChart";

const NOW = Date.UTC(2026, 4, 8, 12, 0, 0);
const HOUR = 3_600_000;

const CANDLES: PriceChartCandle[] = [
  { time: NOW - 3 * HOUR, open: 42_000, high: 42_500, low: 41_900, close: 42_300, volume: 1.2 },
  { time: NOW - 2 * HOUR, open: 42_300, high: 42_700, low: 42_200, close: 42_650, volume: 1.6 },
  { time: NOW - 1 * HOUR, open: 42_650, high: 42_900, low: 42_400, close: 42_500, volume: 1.0 },
  { time: NOW, open: 42_500, high: 42_800, low: 42_300, close: 42_750, volume: 0.9 },
];

describe("PriceChart", () => {
  it("renders all six timeframe tabs in a tablist", () => {
    render(
      <PriceChart
        candles={CANDLES}
        symbol="BTC-PERP"
        timeframe="1h"
      />
    );
    const tablist = screen.getByRole("tablist", { name: "Timeframe" });
    const tabs = within(tablist).getAllByRole("tab");
    expect(tabs.map((t) => t.textContent)).toEqual([
      "1m",
      "5m",
      "15m",
      "1h",
      "4h",
      "1d",
    ]);
    const active = tabs.find((t) => t.getAttribute("aria-selected") === "true");
    expect(active?.textContent).toBe("1h");
  });

  it("invokes onTimeframeChange when a tab is clicked", async () => {
    const onChange = vi.fn();
    render(
      <PriceChart
        candles={CANDLES}
        symbol="BTC-PERP"
        timeframe="1h"
        onTimeframeChange={onChange}
      />
    );
    const tablist = screen.getByRole("tablist");
    const tab15 = within(tablist).getByRole("tab", { name: "15m" });
    await userEvent.click(tab15);
    expect(onChange).toHaveBeenCalledWith("15m");
  });

  it("shows last-close summary with sign-tinted change", () => {
    render(
      <PriceChart
        candles={CANDLES}
        symbol="BTC-PERP"
        timeframe="1h"
      />
    );
    // Last close 42,750 vs prior 42,500 = +0.59%, rounded to +0.59%.
    expect(screen.getByText(/last/)).toBeInTheDocument();
    expect(screen.getByText(/\+0\.59%/)).toBeInTheDocument();
  });

  it("renders the live status pill by default", () => {
    render(
      <PriceChart
        candles={CANDLES}
        symbol="BTC-PERP"
        timeframe="1h"
      />
    );
    expect(screen.getByText("live")).toBeInTheDocument();
  });

  it("renders the replay status pill when mode is replay", () => {
    render(
      <PriceChart
        candles={CANDLES}
        symbol="BTC-PERP"
        timeframe="1h"
        mode="replay"
      />
    );
    expect(screen.getByText("replay")).toBeInTheDocument();
  });

  it("shows the empty-state message when no candles are provided", () => {
    render(
      <PriceChart
        candles={[]}
        symbol="BTC-PERP"
        timeframe="1h"
      />
    );
    expect(
      screen.getByText("No candles for this range.")
    ).toBeInTheDocument();
  });

  it("shows a loading indicator when loading", () => {
    render(
      <PriceChart
        candles={[]}
        symbol="BTC-PERP"
        timeframe="1h"
        loading
      />
    );
    expect(screen.getByText("Loading candles…")).toBeInTheDocument();
  });

  it("surfaces errors", () => {
    render(
      <PriceChart
        candles={[]}
        symbol="BTC-PERP"
        timeframe="1h"
        error="429 Too Many Requests"
      />
    );
    expect(screen.getByText("429 Too Many Requests")).toBeInTheDocument();
  });

  it("surfaces v2 Pending tag on the drawing-tools strip when enabled", () => {
    render(
      <PriceChart
        candles={CANDLES}
        symbol="BTC-PERP"
        timeframe="1h"
        withDrawingTools
      />
    );
    expect(screen.getByTitle("Drawing tools — Pending v2")).toBeInTheDocument();
    expect(screen.getByText("v2")).toBeInTheDocument();
  });

  it("hides the drawing-tools strip when withDrawingTools is false", () => {
    render(
      <PriceChart
        candles={CANDLES}
        symbol="BTC-PERP"
        timeframe="1h"
        withDrawingTools={false}
      />
    );
    expect(
      screen.queryByTitle("Drawing tools — Pending v2")
    ).not.toBeInTheDocument();
  });

  it("renders the depth-chart Pending strip when withDepthChart is set", () => {
    render(
      <PriceChart
        candles={CANDLES}
        symbol="BTC-PERP"
        timeframe="1h"
        withDepthChart
      />
    );
    expect(screen.getByText("DepthChart Pending")).toBeInTheDocument();
  });

  it("respects a caller-supplied symbol slot", () => {
    render(
      <PriceChart
        candles={CANDLES}
        symbol="BTC-PERP"
        timeframe="1h"
        symbolSlot={<span data-testid="symbol-slot">ETH-PERP</span>}
      />
    );
    expect(screen.getByTestId("symbol-slot")).toHaveTextContent("ETH-PERP");
  });

  it("respects a caller-supplied status slot", () => {
    render(
      <PriceChart
        candles={CANDLES}
        symbol="BTC-PERP"
        timeframe="1h"
        statusSlot={<span data-testid="status-slot">paused</span>}
      />
    );
    expect(screen.getByTestId("status-slot")).toHaveTextContent("paused");
    // Default 'live' / 'replay' pill should be replaced.
    expect(screen.queryByText("live")).not.toBeInTheDocument();
  });

  it("renders only the requested subset of timeframes", () => {
    render(
      <PriceChart
        candles={CANDLES}
        symbol="BTC-PERP"
        timeframe="1h"
        timeframes={["1h", "4h", "1d"]}
      />
    );
    const tabs = within(
      screen.getByRole("tablist")
    ).getAllByRole("tab");
    expect(tabs).toHaveLength(3);
    expect(tabs.map((t) => t.textContent)).toEqual(["1h", "4h", "1d"]);
  });
});
