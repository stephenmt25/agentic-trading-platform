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
});
