import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { WeightEvolutionChart } from "./WeightEvolutionChart";

/**
 * F2 token-contract rewrite (registry row 62): pins the rendered data.
 * Recharts internals don't lay out under jsdom, so assertions target
 * the empty state and the panel header.
 */

const POINT = {
  agent_name: "ta",
  weight: 0.2,
  ewma_accuracy: 0.5,
  sample_count: 10,
  recorded_at: "2026-06-12T10:00:00Z",
};

describe("WeightEvolutionChart", () => {
  it("renders the empty panel when there is no history", () => {
    render(<WeightEvolutionChart data={[]} />);
    expect(
      screen.getByText(/No weight history available yet/)
    ).toBeInTheDocument();
  });

  it("renders the chart panel header when history exists", () => {
    render(<WeightEvolutionChart data={[POINT]} />);
    expect(screen.getByText("Weight Evolution")).toBeInTheDocument();
    // Empty state must be gone.
    expect(
      screen.queryByText(/No weight history available yet/)
    ).not.toBeInTheDocument();
  });
});
