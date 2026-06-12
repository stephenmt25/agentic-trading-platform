import { describe, it, expect } from "vitest";
import { queryKeys } from "./hooks";

/**
 * Key-discipline contract (FE-W1): the umbrella ["risk"] prefix is for
 * invalidation only and must never be aliased by a live data key; new
 * per-resource keys nest under it or live in their own namespace.
 */
describe("queryKeys — key discipline", () => {
  it("new risk-truth keys nest under the ['risk'] prefix without aliasing it", () => {
    expect(queryKeys.riskPortfolio).toEqual(["risk", "portfolio"]);
    expect(queryKeys.decay).toEqual(["risk", "decay"]);
    // Never the bare umbrella.
    expect(queryKeys.riskPortfolio.length).toBeGreaterThan(1);
    expect(queryKeys.decay.length).toBeGreaterThan(1);
  });

  it("netOfCost keys by window so different windows coexist", () => {
    expect(queryKeys.netOfCost(168)).toEqual(["netOfCost", 168]);
    expect(queryKeys.netOfCost(24)).toEqual(["netOfCost", 24]);
  });

  it("existing keys are unchanged (regression guard)", () => {
    expect(queryKeys.killSwitch).toEqual(["killSwitch"]);
    expect(queryKeys.risk).toEqual(["risk"]);
    expect(queryKeys.allRisk).toEqual(["risk", "all"]);
    expect(queryKeys.riskFor("abc")).toEqual(["risk", "profile", "abc"]);
  });

  it("orders key (FE-W2) namespaces by symbol/profile/limit with 'all' fallbacks", () => {
    expect(queryKeys.orders("BTC-USDT", "p-1", 50)).toEqual([
      "orders",
      "BTC-USDT",
      "p-1",
      50,
    ]);
    // Undefined slots collapse to "all" so the key is always fully addressed.
    expect(queryKeys.orders(undefined, undefined, 50)).toEqual([
      "orders",
      "all",
      "all",
      50,
    ]);
    // Default limit is part of the key (different limits coexist).
    expect(queryKeys.orders("ETH-USDT")).toEqual(["orders", "ETH-USDT", "all", 50]);
    // Lives in its own namespace — must never alias the ["risk"] umbrella.
    expect(queryKeys.orders("BTC-USDT")[0]).not.toBe("risk");
  });

  it("FE-W2.1 keys are fully addressed with 'all'/null fallbacks", () => {
    expect(queryKeys.paperTradingStatus).toEqual(["paperTradingStatus"]);
    expect(queryKeys.agentStatus).toEqual(["agentStatus"]);
    expect(queryKeys.sessions).toEqual(["sessions"]);

    expect(queryKeys.decisions("p-1", "APPROVED", 100)).toEqual([
      "decisions",
      "p-1",
      "APPROVED",
      100,
    ]);
    expect(queryKeys.decisions()).toEqual(["decisions", "all", "all", 100]);

    expect(queryKeys.auditUserEvents("all", undefined, undefined, 200)).toEqual([
      "auditUserEvents",
      "all",
      null,
      null,
      200,
    ]);
    expect(queryKeys.auditUserEvents("kill_switch", 1, 2, 50)).toEqual([
      "auditUserEvents",
      "kill_switch",
      1,
      2,
      50,
    ]);

    expect(queryKeys.backtestHistory()).toEqual(["backtestHistory", 100]);
    expect(queryKeys.backtestResult("job-1")).toEqual([
      "backtestResult",
      "job-1",
    ]);

    expect(queryKeys.agentScores("BTC/USDT", "ta,sentiment", 2000)).toEqual([
      "agentScores",
      "BTC/USDT",
      "ta,sentiment",
      2000,
    ]);
    expect(queryKeys.agentScores("BTC/USDT")).toEqual([
      "agentScores",
      "BTC/USDT",
      "all",
      2000,
    ]);
    expect(queryKeys.agentWeights("BTC/USDT")).toEqual([
      "agentWeights",
      "BTC/USDT",
    ]);
    expect(queryKeys.gateAnalytics("BTC/USDT", "p-1", 500)).toEqual([
      "gateAnalytics",
      "BTC/USDT",
      "p-1",
      500,
    ]);
    expect(queryKeys.gateAnalytics("BTC/USDT")).toEqual([
      "gateAnalytics",
      "BTC/USDT",
      "all",
      500,
    ]);
  });

  it("no FE-W2.1 key aliases the ['risk'] invalidation umbrella", () => {
    const newKeys: ReadonlyArray<readonly unknown[]> = [
      queryKeys.paperTradingStatus,
      queryKeys.decisions("p", "o", 1),
      queryKeys.agentStatus,
      queryKeys.sessions,
      queryKeys.auditUserEvents("all"),
      queryKeys.backtestHistory(),
      queryKeys.backtestResult("j"),
      queryKeys.agentScores("s"),
      queryKeys.agentWeights("s"),
      queryKeys.gateAnalytics("s"),
    ];
    for (const key of newKeys) {
      expect(key[0]).not.toBe("risk");
    }
  });
});
