import { describe, it, expect, beforeEach } from "vitest";
import { usePortfolioStore, PnLPositionSnapshot } from "./portfolioStore";

const makeSnapshot = (
  overrides: Partial<PnLPositionSnapshot> = {}
): PnLPositionSnapshot => ({
  position_id: "pos-1",
  profile_id: "prof-1",
  symbol: "BTC/USDT",
  gross_pnl: 125.5,
  fees: 3.25,
  net_pre_tax: 122.25,
  net_post_tax: 103.91,
  tax_estimate: 18.34,
  pct_return: 0.0207,
  timestamp_us: 1_700_000_000_000_000,
  ...overrides,
});

beforeEach(() => {
  usePortfolioStore.setState({ pnlData: {} });
});

describe("portfolioStore.applyPnlSnapshots", () => {
  it("keys snapshots by position_id — positions of one profile coexist", () => {
    // The old store keyed by profile_id: the second snapshot would have
    // clobbered the first and total-PnL sums lost data.
    usePortfolioStore.getState().applyPnlSnapshots([
      makeSnapshot({ position_id: "pos-1", profile_id: "prof-1" }),
      makeSnapshot({ position_id: "pos-2", profile_id: "prof-1", symbol: "ETH/USDT" }),
    ]);
    const pnlData = usePortfolioStore.getState().pnlData;
    expect(Object.keys(pnlData).sort()).toEqual(["pos-1", "pos-2"]);
    expect(pnlData["pos-2"].symbol).toBe("ETH/USDT");
  });

  it("applies a whole batch in ONE store write (single subscriber call)", () => {
    let notifications = 0;
    const unsubscribe = usePortfolioStore.subscribe(() => {
      notifications++;
    });
    usePortfolioStore.getState().applyPnlSnapshots([
      makeSnapshot({ position_id: "pos-1" }),
      makeSnapshot({ position_id: "pos-2" }),
      makeSnapshot({ position_id: "pos-3" }),
    ]);
    unsubscribe();
    expect(notifications).toBe(1);
    expect(Object.keys(usePortfolioStore.getState().pnlData)).toHaveLength(3);
  });

  it("last snapshot wins for a repeated position_id within a batch", () => {
    usePortfolioStore.getState().applyPnlSnapshots([
      makeSnapshot({ position_id: "pos-1", net_post_tax: 1 }),
      makeSnapshot({ position_id: "pos-1", net_post_tax: 2 }),
    ]);
    expect(usePortfolioStore.getState().pnlData["pos-1"].net_post_tax).toBe(2);
  });

  it("merges with existing snapshots instead of replacing the map", () => {
    usePortfolioStore
      .getState()
      .applyPnlSnapshots([makeSnapshot({ position_id: "pos-1" })]);
    usePortfolioStore
      .getState()
      .applyPnlSnapshots([makeSnapshot({ position_id: "pos-2" })]);
    expect(Object.keys(usePortfolioStore.getState().pnlData).sort()).toEqual([
      "pos-1",
      "pos-2",
    ]);
  });

  it("no-ops on an empty batch — pnlData reference is unchanged", () => {
    const before = usePortfolioStore.getState().pnlData;
    usePortfolioStore.getState().applyPnlSnapshots([]);
    expect(usePortfolioStore.getState().pnlData).toBe(before);
  });

  it("preserves null fields verbatim (consumers null-guard, not the store)", () => {
    usePortfolioStore.getState().applyPnlSnapshots([
      makeSnapshot({ position_id: "pos-1", fees: null, tax_estimate: null }),
    ]);
    const snapshot = usePortfolioStore.getState().pnlData["pos-1"];
    expect(snapshot.fees).toBeNull();
    expect(snapshot.tax_estimate).toBeNull();
  });
});
