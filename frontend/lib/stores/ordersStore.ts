"use client";

import { create } from "zustand";

/**
 * Local-only optimistic state for manual orders submitted from /hot. Only
 * "in flight" entries live here — once an order surfaces in the canonical
 * GET /orders response (services/api_gateway/src/routes/orders.py), the
 * surface reads from there instead and we drop the optimistic shadow.
 *
 * Lifecycle:
 *   submitting → confirmed (server returned 202) | rejected (HTTP error)
 *
 * "confirmed" here means the api_gateway accepted the submission and
 * published OrderApprovedEvent; the executor's terminal status (FILLED,
 * EXECUTED, REJECTED on-exchange) lands via api.orders.list polling.
 */
export type OptimisticStatus = "submitting" | "confirmed" | "rejected";

export interface OptimisticOrder {
  /** Server-generated when status flips to "confirmed". Matches DB order_id. */
  orderId: string | null;
  /** Stable client-side id used until orderId arrives. */
  tempId: string;
  profileId: string;
  symbol: string;
  side: "BUY" | "SELL";
  type: "market" | "limit";
  quantity: string;
  price?: string;
  status: OptimisticStatus;
  /** Filled when status === "rejected". */
  rejectionReason?: string;
  submittedAtMs: number;
}

interface OrdersStore {
  optimistic: OptimisticOrder[];
  /** Insert a new optimistic order. Returns its tempId. */
  beginSubmit: (
    init: Omit<OptimisticOrder, "tempId" | "status" | "submittedAtMs" | "orderId">
  ) => string;
  /** Mark an optimistic order as confirmed; assigns the server orderId. */
  confirmSubmit: (tempId: string, orderId: string) => void;
  /** Mark an optimistic order as rejected with a reason; the surface will
   *  show it briefly then drop on dismissReject. */
  rejectSubmit: (tempId: string, reason: string) => void;
  /** Drop a finished entry — used after the surface displays + dismisses
   *  the reject toast, or after api.orders.list has caught up to a
   *  confirmed entry. */
  drop: (tempId: string) => void;
  /** Drop all confirmed entries whose orderId already appears in the
   *  canonical list — single pass, idempotent. */
  reconcile: (knownOrderIds: ReadonlySet<string>) => void;
}

let _seq = 0;
const nextTempId = (): string => `tmp-${Date.now().toString(36)}-${(++_seq).toString(36)}`;

export const useOrdersStore = create<OrdersStore>((set) => ({
  optimistic: [],
  beginSubmit: (init) => {
    const tempId = nextTempId();
    set((state) => ({
      optimistic: [
        ...state.optimistic,
        {
          ...init,
          tempId,
          orderId: null,
          status: "submitting",
          submittedAtMs: Date.now(),
        },
      ],
    }));
    return tempId;
  },
  confirmSubmit: (tempId, orderId) =>
    set((state) => ({
      optimistic: state.optimistic.map((o) =>
        o.tempId === tempId ? { ...o, status: "confirmed", orderId } : o
      ),
    })),
  rejectSubmit: (tempId, reason) =>
    set((state) => ({
      optimistic: state.optimistic.map((o) =>
        o.tempId === tempId ? { ...o, status: "rejected", rejectionReason: reason } : o
      ),
    })),
  drop: (tempId) =>
    set((state) => ({
      optimistic: state.optimistic.filter((o) => o.tempId !== tempId),
    })),
  reconcile: (knownOrderIds) =>
    set((state) => ({
      optimistic: state.optimistic.filter(
        (o) => o.status !== "confirmed" || !o.orderId || !knownOrderIds.has(o.orderId)
      ),
    })),
}));
