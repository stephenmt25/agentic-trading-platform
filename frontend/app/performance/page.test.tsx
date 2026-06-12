import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import PerformancePage from "./page";
import { queryKeys } from "@/lib/api/hooks";

/**
 * F2 (registry rows 40/62): /performance token rewrite + the 60s
 * setInterval → React Query poller migration. These tests pin that the
 * same four datasets render after the migration and that the surface
 * root declares COOL mode.
 */

const weightsMock = vi.fn();
const gateAnalyticsMock = vi.fn();
const weightHistoryMock = vi.fn();
const attributionMock = vi.fn();

vi.mock("@/lib/api/client", () => ({
  api: {
    agentPerformance: {
      weights: (...a: unknown[]) => weightsMock(...a),
      gateAnalytics: (...a: unknown[]) => gateAnalyticsMock(...a),
      weightHistory: (...a: unknown[]) => weightHistoryMock(...a),
      attribution: (...a: unknown[]) => attributionMock(...a),
    },
  },
}));

const WEIGHTS = {
  weights: { ta: 0.25 },
  trackers: { ta: { ewma: 0.62, samples: 41, last_updated: null } },
};
const GATE = {
  total_decisions: 12,
  outcome_counts: { APPROVED: 5, BLOCKED_ABSTENTION: 7 },
  gate_details: {},
};
const HISTORY = [
  {
    agent_name: "ta",
    weight: 0.2,
    ewma_accuracy: 0.5,
    sample_count: 10,
    recorded_at: "2026-06-12T10:00:00Z",
  },
];
const ATTRIBUTION = [
  {
    event_id: "ev-1",
    symbol: "BTC/USDT",
    outcome: "APPROVED",
    input_price: 75037.5,
    agents: null,
    created_at: null,
  },
];

function renderPage() {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={client}>
      <PerformancePage />
    </QueryClientProvider>
  );
}

beforeEach(() => {
  vi.clearAllMocks();
  weightsMock.mockResolvedValue(WEIGHTS);
  gateAnalyticsMock.mockResolvedValue(GATE);
  weightHistoryMock.mockResolvedValue(HISTORY);
  attributionMock.mockResolvedValue(ATTRIBUTION);
});

describe("PerformancePage", () => {
  it("registers its query key in the shared queryKeys map (key discipline)", () => {
    expect(queryKeys.agentPerformance("BTC/USDT")).toEqual([
      "agentPerformance",
      "BTC/USDT",
    ]);
    // Own namespace — never aliases the ["risk"] umbrella.
    expect(queryKeys.agentPerformance("BTC/USDT")[0]).not.toBe("risk");
  });

  it("declares COOL mode on the surface root", () => {
    const { container } = renderPage();
    expect(container.querySelector('[data-mode="cool"]')).not.toBeNull();
  });

  it("shows the loading panel, then renders all four sections from the bundled fetch", async () => {
    renderPage();
    expect(screen.getByText("Loading performance data...")).toBeInTheDocument();

    await waitFor(() =>
      expect(screen.getByText("Agent Accuracy & Weights")).toBeInTheDocument()
    );
    expect(screen.getByText("Decision Outcomes")).toBeInTheDocument();
    expect(screen.getByText("Weight Evolution")).toBeInTheDocument();
    expect(screen.getByText("Trade Attribution")).toBeInTheDocument();

    // The four endpoints were hit once each for the default symbol.
    expect(weightsMock).toHaveBeenCalledWith("BTC/USDT");
    expect(gateAnalyticsMock).toHaveBeenCalledWith("BTC/USDT");
    expect(weightHistoryMock).toHaveBeenCalledWith("BTC/USDT", {
      agents: "ta,sentiment,debate",
      limit: 1000,
    });
    expect(attributionMock).toHaveBeenCalledWith("BTC/USDT", 100);
  });

  it("refetches for the selected symbol when the toggle changes", async () => {
    renderPage();
    await waitFor(() =>
      expect(screen.getByText("Agent Accuracy & Weights")).toBeInTheDocument()
    );

    await userEvent.click(screen.getByRole("button", { name: "ETH" }));
    await waitFor(() => expect(weightsMock).toHaveBeenCalledWith("ETH/USDT"));
  });

  it("renders the error panel when the bundled fetch fails", async () => {
    weightsMock.mockRejectedValue(new Error("gateway unreachable"));
    renderPage();
    await waitFor(() =>
      expect(screen.getByText("gateway unreachable")).toBeInTheDocument()
    );
  });
});
