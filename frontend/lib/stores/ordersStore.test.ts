import { describe, it, expect, beforeEach } from "vitest";
import { useOrdersStore } from "./ordersStore";

beforeEach(() => {
  useOrdersStore.setState({ optimistic: [] });
});

describe("ordersStore — optimistic insert + reconcile", () => {
  it("beginSubmit inserts a 'submitting' entry and returns its tempId", () => {
    const id = useOrdersStore.getState().beginSubmit({
      profileId: "p1",
      symbol: "BTC-USDT",
      side: "BUY",
      type: "limit",
      quantity: "0.001",
      price: "80000",
    });
    const items = useOrdersStore.getState().optimistic;
    expect(items).toHaveLength(1);
    expect(items[0].tempId).toBe(id);
    expect(items[0].status).toBe("submitting");
    expect(items[0].orderId).toBeNull();
    expect(items[0].quantity).toBe("0.001");
  });

  it("confirmSubmit flips status and assigns the server orderId", () => {
    const id = useOrdersStore.getState().beginSubmit({
      profileId: "p1",
      symbol: "BTC-USDT",
      side: "BUY",
      type: "market",
      quantity: "0.001",
    });
    useOrdersStore.getState().confirmSubmit(id, "srv-123");
    const item = useOrdersStore.getState().optimistic[0];
    expect(item.status).toBe("confirmed");
    expect(item.orderId).toBe("srv-123");
  });

  it("rejectSubmit captures the reason; entry stays in the list until dropped", () => {
    const id = useOrdersStore.getState().beginSubmit({
      profileId: "p1",
      symbol: "BTC-USDT",
      side: "SELL",
      type: "limit",
      quantity: "0.001",
      price: "80000",
    });
    useOrdersStore.getState().rejectSubmit(id, "Kill switch is active");
    const item = useOrdersStore.getState().optimistic[0];
    expect(item.status).toBe("rejected");
    expect(item.rejectionReason).toBe("Kill switch is active");

    useOrdersStore.getState().drop(id);
    expect(useOrdersStore.getState().optimistic).toHaveLength(0);
  });

  it("reconcile drops confirmed entries whose orderId already appears server-side", () => {
    const id1 = useOrdersStore.getState().beginSubmit({
      profileId: "p1",
      symbol: "BTC-USDT",
      side: "BUY",
      type: "limit",
      quantity: "0.001",
      price: "80000",
    });
    const id2 = useOrdersStore.getState().beginSubmit({
      profileId: "p1",
      symbol: "ETH-USDT",
      side: "BUY",
      type: "limit",
      quantity: "0.05",
      price: "2300",
    });
    useOrdersStore.getState().confirmSubmit(id1, "srv-A");
    useOrdersStore.getState().confirmSubmit(id2, "srv-B");

    // Server has only A — B should remain.
    useOrdersStore.getState().reconcile(new Set(["srv-A"]));
    const remaining = useOrdersStore.getState().optimistic;
    expect(remaining.map((o) => o.orderId)).toEqual(["srv-B"]);
  });

  it("reconcile keeps 'submitting' and 'rejected' entries regardless of server", () => {
    const a = useOrdersStore.getState().beginSubmit({
      profileId: "p1",
      symbol: "BTC-USDT",
      side: "BUY",
      type: "limit",
      quantity: "0.001",
      price: "80000",
    });
    const b = useOrdersStore.getState().beginSubmit({
      profileId: "p1",
      symbol: "BTC-USDT",
      side: "SELL",
      type: "limit",
      quantity: "0.001",
      price: "81000",
    });
    useOrdersStore.getState().rejectSubmit(b, "fail");

    // Pretend the server has nothing — both should remain (one submitting, one rejected).
    useOrdersStore.getState().reconcile(new Set());
    const remaining = useOrdersStore.getState().optimistic;
    expect(remaining).toHaveLength(2);
    expect(remaining.map((o) => o.tempId).sort()).toEqual([a, b].sort());
  });
});
