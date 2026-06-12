import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { GateBlockAnalytics } from "./GateBlockAnalytics";

/**
 * F2 token-contract rewrite (registry row 62): pins the rendered data.
 * Recharts internals don't lay out under jsdom (zero-size container),
 * so assertions target the header, totals and the gate summary grid.
 */

const DATA = {
  total_decisions: 12,
  outcome_counts: { APPROVED: 5, BLOCKED_ABSTENTION: 7 },
  gate_details: {
    abstention: { passed: 9, blocked: 1, reasons: { choppy: 1 } },
    circuit_breaker: { passed: 6, blocked: 4, reasons: {} },
    blacklist: { passed: 1, blocked: 3, reasons: {} },
  },
};

describe("GateBlockAnalytics", () => {
  it("renders the empty panel when data is null", () => {
    render(<GateBlockAnalytics data={null} />);
    expect(screen.getByText("No decision data available yet")).toBeInTheDocument();
  });

  it("renders the empty panel when there are zero decisions", () => {
    render(
      <GateBlockAnalytics
        data={{ total_decisions: 0, outcome_counts: {}, gate_details: {} }}
      />
    );
    expect(screen.getByText("No decision data available yet")).toBeInTheDocument();
  });

  it("renders the header with the decision total", () => {
    render(<GateBlockAnalytics data={DATA} />);
    expect(screen.getByText("Decision Outcomes")).toBeInTheDocument();
    expect(screen.getByText("12 total")).toBeInTheDocument();
  });

  it("renders per-gate pass rates with semantic tone thresholds (>80 bid, >50 warn, else ask)", () => {
    render(<GateBlockAnalytics data={DATA} />);
    // abstention: 9/10 = 90%
    const ninety = screen.getByText("90%");
    expect(ninety.className).toContain("text-bid-400");
    // circuit breaker: 6/10 = 60%
    const sixty = screen.getByText("60%");
    expect(sixty.className).toContain("text-warn-400");
    // blacklist: 1/4 = 25%
    const twentyFive = screen.getByText("25%");
    expect(twentyFive.className).toContain("text-ask-400");
    // Gate names render with underscores replaced.
    expect(screen.getByText("circuit breaker")).toBeInTheDocument();
  });
});
