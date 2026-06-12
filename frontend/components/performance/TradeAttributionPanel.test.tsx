import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { TradeAttributionPanel } from "./TradeAttributionPanel";

/**
 * F2 token-contract rewrite (registry row 62): pins the rendered data
 * so the legacy→Praxis token migration is provably presentation-only.
 */

function entry(i: number, overrides: Partial<Parameters<typeof TradeAttributionPanel>[0]["data"][number]> = {}) {
  return {
    event_id: `ev-${i}`,
    symbol: "BTC/USDT",
    outcome: "APPROVED",
    input_price: 75037.5,
    agents: {
      ta: { score: 0.8, weight: 0.2, adjustment: 0.05 },
      sentiment: { score: 0.1, weight: 0.15, adjustment: -0.02 },
      debate: { score: 0, weight: 0.25, adjustment: 0 },
      confidence_before: 0.5,
      confidence_after: 0.53,
    },
    created_at: "2026-06-12T10:00:00Z",
    ...overrides,
  };
}

describe("TradeAttributionPanel", () => {
  it("renders the empty panel when there are no trades", () => {
    render(<TradeAttributionPanel data={[]} />);
    expect(
      screen.getByText("No approved trades yet for attribution analysis")
    ).toBeInTheDocument();
  });

  it("renders price, confidences and signed per-agent adjustments", () => {
    render(<TradeAttributionPanel data={[entry(1)]} />);
    expect(screen.getByText("Trade Attribution")).toBeInTheDocument();
    expect(screen.getByText(`$${(75037.5).toLocaleString()}`)).toBeInTheDocument();
    expect(screen.getByText("0.500")).toBeInTheDocument();
    expect(screen.getByText("0.530")).toBeInTheDocument();
    // Signed adjustments with semantic tones.
    const pos = screen.getByText("+0.050");
    expect(pos.className).toContain("text-bid-400");
    const neg = screen.getByText("-0.020");
    expect(neg.className).toContain("text-ask-400");
    const zero = screen.getByText("0.000");
    expect(zero.className).toContain("text-fg-muted");
  });

  it("renders dashes for missing price/confidence/timestamp", () => {
    render(
      <TradeAttributionPanel
        data={[entry(1, { input_price: null, agents: null, created_at: null })]}
      />
    );
    // date, time, price, conf before, conf after all dash out.
    expect(screen.getAllByText("—")).toHaveLength(5);
  });

  it("caps the table at 20 rows and reports the full count", () => {
    const rows = Array.from({ length: 25 }, (_, i) => entry(i));
    render(<TradeAttributionPanel data={rows} />);
    expect(screen.getByText("Showing 20 of 25 trades")).toBeInTheDocument();
    // 20 body rows + 1 header row
    expect(screen.getAllByRole("row")).toHaveLength(21);
  });
});
