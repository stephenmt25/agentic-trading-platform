import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { AgentAccuracyTable } from "./AgentAccuracyTable";

/**
 * F2 token-contract rewrite (registry row 62): these tests pin the
 * DATA the component renders so the legacy→Praxis token migration is
 * provably presentation-only.
 */

const WEIGHTS = {
  weights: { ta: 0.25, sentiment: 0.15, debate: 0.2 },
  trackers: {
    ta: { ewma: 0.62, samples: 41, last_updated: "2026-06-12T10:00:00Z" },
    sentiment: { ewma: null, samples: 0, last_updated: null },
    debate: { ewma: 0.1, samples: 7, last_updated: "2026-06-12T10:00:00Z" },
  },
};

describe("AgentAccuracyTable", () => {
  it("renders the empty panel when weights are null", () => {
    render(<AgentAccuracyTable weights={null} />);
    expect(screen.getByText("No weight data available")).toBeInTheDocument();
  });

  it("renders one row per agent with ewma %, samples, weights and delta", () => {
    render(<AgentAccuracyTable weights={WEIGHTS} />);

    // Agent labels (uppercase via CSS class, text content stays lowercase).
    for (const agent of ["ta", "sentiment", "debate"]) {
      expect(screen.getByText(agent)).toBeInTheDocument();
    }

    // ta: ewma 62.0%, 41 samples, weight 0.250, default 0.200, delta +0.050
    expect(screen.getByText("62.0%")).toBeInTheDocument();
    expect(screen.getByText("41")).toBeInTheDocument();
    expect(screen.getByText("+0.050")).toBeInTheDocument();

    // sentiment: null ewma coerces to 0 → "0.0%", samples 0, delta 0.000
    expect(screen.getByText("0.0%")).toBeInTheDocument();
    expect(screen.getByText("0.000")).toBeInTheDocument();

    // debate: weight 0.200 vs default 0.250 → delta -0.050
    expect(screen.getByText("-0.050")).toBeInTheDocument();
  });

  it("falls back to the default weight when the agent has no current weight", () => {
    render(
      <AgentAccuracyTable
        weights={{ weights: {}, trackers: {} }}
      />
    );
    // All three deltas are 0.000 (current == default for every agent).
    expect(screen.getAllByText("0.000")).toHaveLength(3);
  });

  it("uses the accent token for agent identity dots (ADR-012 — no per-agent hues)", () => {
    const { container } = render(<AgentAccuracyTable weights={WEIGHTS} />);
    const dots = container.querySelectorAll("span.w-2.h-2.rounded-full");
    expect(dots).toHaveLength(3);
    dots.forEach((dot) => expect(dot.className).toContain("bg-accent-500"));
  });
});
