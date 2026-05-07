"use client";

import {
  forwardRef,
  useEffect,
  useMemo,
  useRef,
  useState,
  type HTMLAttributes,
  type KeyboardEvent,
} from "react";
import { AlertTriangle, ShieldAlert } from "lucide-react";
import { cn } from "@/lib/utils";
import { Button } from "@/components/primitives/Button";
import { Input } from "@/components/primitives/Input";
import { Toggle } from "@/components/primitives/Toggle";
import { Kbd } from "@/components/primitives/Kbd";

/**
 * OrderEntryPanel per docs/design/04-component-specs/trading-specific.md.
 *
 * Critical-path (per frontend/DESIGN.md): the kill-switch-armed state
 * MUST always render correctly — submit disabled, danger banner, no
 * way to bypass.
 *
 * Critical UX rule (per dYdX learnings): every input reachable in ≤3
 * keystrokes from any other. Tab order: side → size → price →
 * leverage → submit.
 *
 * Submit button adopts the CONSEQUENCE color — bid.500 for buy,
 * ask.500 for sell. This is the "color is meaning" contract for the
 * one most consequential action in the platform.
 */

export type OrderSide = "buy" | "sell";
export type OrderType = "limit" | "market" | "stop" | "twap";
export type OrderEntryState =
  | "ok"
  | "validating"
  | "risk-block"
  | "kill-switch-armed";

export interface OrderEntryPayload {
  symbol: string;
  side: OrderSide;
  type: OrderType;
  size: number;
  /** Undefined for market orders. */
  price?: number;
  leverage: number;
  reduceOnly: boolean;
  postOnly: boolean;
}

export interface OrderEntryPanelProps
  extends Omit<HTMLAttributes<HTMLDivElement>, "onSubmit" | "children"> {
  symbol: string;
  midPrice?: number;
  state?: OrderEntryState;
  riskBlockReason?: string;
  estimatedCost?: number;
  estimatedMargin?: number;
  quoteCurrency?: string;
  defaultSide?: OrderSide;
  defaultOrderType?: OrderType;
  defaultSize?: string;
  defaultPrice?: string;
  defaultLeverage?: number;
  minLeverage?: number;
  maxLeverage?: number;
  /** Available position size — backs the 25/50/75/100% size buttons. */
  availableSize?: number;
  density?: "compact" | "standard" | "comfortable";
  onSubmit?: (order: OrderEntryPayload) => void;
  onSideChange?: (side: OrderSide) => void;
  onOrderTypeChange?: (type: OrderType) => void;
}

const ORDER_TYPES: { key: OrderType; label: string }[] = [
  { key: "limit", label: "Limit" },
  { key: "market", label: "Market" },
  { key: "stop", label: "Stop" },
  { key: "twap", label: "TWAP" },
];

function fmt(v: number, digits: number): string {
  return v.toLocaleString(undefined, {
    minimumFractionDigits: digits,
    maximumFractionDigits: digits,
  });
}

export const OrderEntryPanel = forwardRef<HTMLDivElement, OrderEntryPanelProps>(
  (
    {
      symbol,
      midPrice,
      state = "ok",
      riskBlockReason,
      estimatedCost,
      estimatedMargin,
      quoteCurrency = "USDC",
      defaultSide = "buy",
      defaultOrderType = "limit",
      defaultSize = "0.0",
      defaultPrice,
      defaultLeverage = 5,
      minLeverage = 1,
      maxLeverage = 100,
      availableSize,
      density = "standard",
      onSubmit,
      onSideChange,
      onOrderTypeChange,
      className,
      ...props
    },
    ref
  ) => {
    const [side, setSide] = useState<OrderSide>(defaultSide);
    const [orderType, setOrderType] = useState<OrderType>(defaultOrderType);
    const [size, setSize] = useState(defaultSize);
    const [price, setPrice] = useState(
      defaultPrice ?? (midPrice !== undefined ? midPrice.toString() : "")
    );
    const [leverage, setLeverage] = useState(defaultLeverage);
    const [reduceOnly, setReduceOnly] = useState(false);
    const [postOnly, setPostOnly] = useState(false);

    const sizeRef = useRef<HTMLInputElement>(null);
    const priceRef = useRef<HTMLInputElement>(null);
    const leverageRef = useRef<HTMLInputElement>(null);
    const submitRef = useRef<HTMLButtonElement>(null);

    const setSideAndNotify = (s: OrderSide) => {
      setSide(s);
      onSideChange?.(s);
    };

    const setOrderTypeAndNotify = (t: OrderType) => {
      setOrderType(t);
      onOrderTypeChange?.(t);
    };

    const isMarket = orderType === "market";
    const numericSize = parseFloat(size) || 0;
    const numericPrice = parseFloat(price) || undefined;

    // Within X% of mid hint for the price input
    const priceHint = useMemo(() => {
      if (!midPrice || !numericPrice || isMarket) return undefined;
      const pct = Math.abs((numericPrice - midPrice) / midPrice) * 100;
      if (pct < 0.001) return "at mid";
      return `within ${pct.toFixed(2)}% of mid`;
    }, [numericPrice, midPrice, isMarket]);

    // Keyboard shortcuts: B/S toggle side, M switches to market.
    // Enter submits when valid. Per spec: ≤3 keystrokes to any input.
    const onKeyDown = (e: KeyboardEvent<HTMLDivElement>) => {
      // Ignore if focus is in a real text input — they need their letters.
      const target = e.target as HTMLElement;
      const isInputFocus =
        target.tagName === "INPUT" || target.tagName === "TEXTAREA";

      if (!isInputFocus) {
        if (e.key === "b" || e.key === "B") {
          e.preventDefault();
          setSideAndNotify("buy");
        } else if (e.key === "s" || e.key === "S") {
          e.preventDefault();
          setSideAndNotify("sell");
        } else if (e.key === "m" || e.key === "M") {
          e.preventDefault();
          setOrderTypeAndNotify("market");
        } else if (e.key === "Enter") {
          if (state === "ok" && submitRef.current) {
            e.preventDefault();
            submitRef.current.click();
          }
        }
      }
    };

    const handleSubmit = () => {
      if (state !== "ok") return;
      if (numericSize <= 0) return;
      if (!isMarket && (numericPrice === undefined || numericPrice <= 0)) return;
      onSubmit?.({
        symbol,
        side,
        type: orderType,
        size: numericSize,
        price: isMarket ? undefined : numericPrice,
        leverage,
        reduceOnly,
        postOnly,
      });
    };

    const sizePctClick = (pct: 25 | 50 | 75 | 100) => {
      if (availableSize === undefined) return;
      const next = (availableSize * pct) / 100;
      // 4 dp by default — caller can override by managing size externally.
      setSize(next.toFixed(4));
    };

    const submitDisabled =
      state === "kill-switch-armed" ||
      state === "risk-block" ||
      state === "validating" ||
      numericSize <= 0 ||
      (!isMarket && (numericPrice === undefined || numericPrice <= 0));

    const submitLabel = useMemo(() => {
      if (state === "validating") return "validating…";
      if (state === "kill-switch-armed") return "kill switch armed";
      const verb = side === "buy" ? "Buy" : "Sell";
      const sizeStr = numericSize > 0 ? fmt(numericSize, 4) : "—";
      if (isMarket) return `${verb} ${sizeStr} ${symbol} @ market`;
      const priceStr =
        numericPrice !== undefined ? fmt(numericPrice, 2) : "—";
      return `${verb} ${sizeStr} ${symbol} @ ${priceStr}`;
    }, [state, side, numericSize, symbol, isMarket, numericPrice]);

    // Submit button intent: per spec, the consequence color (bid for buy, ask for sell).
    // Disabled+kill-switch state shows danger style.
    const submitIntent: "bid" | "ask" | "danger" =
      state === "kill-switch-armed"
        ? "danger"
        : side === "buy"
          ? "bid"
          : "ask";

    const containerPad =
      density === "compact"
        ? "p-3 gap-3"
        : density === "comfortable"
          ? "p-5 gap-5"
          : "p-4 gap-4";

    return (
      <div
        ref={ref}
        role="form"
        aria-label={`Order entry for ${symbol}`}
        data-state={state}
        data-side={side}
        // tabIndex=-1 so the panel root can receive programmatic focus —
        // lets the per-surface keyboard map deliver shortcuts here even
        // when no descendant is focused.
        tabIndex={-1}
        onKeyDown={onKeyDown}
        className={cn(
          "flex flex-col bg-bg-panel border border-border-subtle rounded-md",
          "focus-within:border-border-strong",
          containerPad,
          className
        )}
        {...props}
      >
        {/* Order-type tabs */}
        <div role="tablist" className="flex items-center gap-1 border-b border-border-subtle -mx-1 px-1 pb-2">
          {ORDER_TYPES.map((t) => {
            const active = t.key === orderType;
            return (
              <button
                key={t.key}
                role="tab"
                type="button"
                aria-selected={active}
                aria-controls={`order-entry-tabpanel-${t.key}`}
                onClick={() => setOrderTypeAndNotify(t.key)}
                className={cn(
                  "px-2.5 h-7 text-[12px] rounded-sm transition-colors",
                  active
                    ? "text-fg border-b-2 border-accent-500 -mb-[2px]"
                    : "text-fg-muted hover:text-fg-secondary"
                )}
              >
                {t.label}
              </button>
            );
          })}
        </div>

        {/* Side: Buy / Sell radio — first in tab order */}
        <div role="radiogroup" aria-label="Order side" className="flex gap-2">
          <button
            type="button"
            role="radio"
            aria-checked={side === "buy"}
            onClick={() => setSideAndNotify("buy")}
            tabIndex={1}
            className={cn(
              "flex-1 h-9 rounded-sm border text-[13px] font-medium transition-colors",
              "focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent-500",
              side === "buy"
                ? "bg-bid-500/15 border-bid-500/60 text-bid-300"
                : "bg-transparent border-border-subtle text-fg-muted hover:text-fg-secondary hover:border-border-strong"
            )}
          >
            Buy <span className="text-fg-muted ml-1.5"><Kbd>B</Kbd></span>
          </button>
          <button
            type="button"
            role="radio"
            aria-checked={side === "sell"}
            onClick={() => setSideAndNotify("sell")}
            tabIndex={1}
            className={cn(
              "flex-1 h-9 rounded-sm border text-[13px] font-medium transition-colors",
              "focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent-500",
              side === "sell"
                ? "bg-ask-500/15 border-ask-500/60 text-ask-300"
                : "bg-transparent border-border-subtle text-fg-muted hover:text-fg-secondary hover:border-border-strong"
            )}
          >
            Sell <span className="text-fg-muted ml-1.5"><Kbd>S</Kbd></span>
          </button>
        </div>

        {/* Size + percentage buttons */}
        <div className="flex flex-col gap-1.5">
          <div className="flex items-end gap-2">
            <div className="flex-1">
              <Input
                ref={sizeRef}
                label="Size"
                value={size}
                onChange={(e) => setSize(e.target.value)}
                numeric
                density={density}
                tabIndex={2}
                aria-label="Order size"
              />
            </div>
            <div className="flex gap-1 mb-0.5">
              {([25, 50, 75, 100] as const).map((pct) => (
                <Button
                  key={pct}
                  size="xs"
                  intent="secondary"
                  onClick={() => sizePctClick(pct)}
                  disabled={availableSize === undefined}
                  aria-label={`Set size to ${pct}% of available`}
                >
                  {pct}%
                </Button>
              ))}
            </div>
          </div>
        </div>

        {/* Price (hidden for market) */}
        {!isMarket && (
          <div>
            <Input
              ref={priceRef}
              label="Price"
              value={price}
              onChange={(e) => setPrice(e.target.value)}
              numeric
              density={density}
              tabIndex={3}
              aria-label="Order price"
              hint={priceHint}
            />
          </div>
        )}

        {/* Leverage slider */}
        <div className="flex flex-col gap-2">
          <div className="flex items-center justify-between">
            <label htmlFor={`leverage-${symbol}`} className="text-xs font-medium text-fg-secondary">
              Leverage
            </label>
            <span className="num-tabular text-[13px] font-mono text-fg">
              {leverage}x
            </span>
          </div>
          <input
            ref={leverageRef}
            id={`leverage-${symbol}`}
            type="range"
            min={minLeverage}
            max={maxLeverage}
            step={1}
            value={leverage}
            onChange={(e) => setLeverage(parseInt(e.target.value, 10))}
            tabIndex={4}
            aria-label="Leverage"
            className={cn(
              "w-full h-1.5 appearance-none bg-neutral-700 rounded-full cursor-pointer",
              // We use background-image to render the filled portion in the side color.
              side === "buy"
                ? "[--fill:var(--color-bid-500)]"
                : "[--fill:var(--color-ask-500)]"
            )}
            style={{
              backgroundImage: `linear-gradient(to right, var(--fill) 0%, var(--fill) ${
                ((leverage - minLeverage) / (maxLeverage - minLeverage)) * 100
              }%, var(--color-neutral-700) ${
                ((leverage - minLeverage) / (maxLeverage - minLeverage)) * 100
              }%, var(--color-neutral-700) 100%)`,
            }}
          />
          <div className="flex justify-between text-[10px] text-fg-muted num-tabular">
            <span>{minLeverage}x</span>
            <span>{maxLeverage}x</span>
          </div>
        </div>

        {/* Reduce-only / Post-only */}
        <div className="flex items-center justify-between gap-3 text-[12px] text-fg-secondary">
          <span className="inline-flex items-center gap-2">
            <Toggle
              checked={reduceOnly}
              onCheckedChange={setReduceOnly}
              size="sm"
              label="Reduce-only"
            />
            <span>Reduce-only</span>
          </span>
          <span className="inline-flex items-center gap-2">
            <Toggle
              checked={postOnly}
              onCheckedChange={setPostOnly}
              size="sm"
              label="Post-only"
              disabled={isMarket}
            />
            <span className={isMarket ? "text-fg-disabled" : ""}>Post-only</span>
          </span>
        </div>

        {/* Cost / Margin readout */}
        <div className="flex items-center justify-between text-[11px] text-fg-muted num-tabular border-t border-border-subtle pt-3">
          <span>
            Cost:{" "}
            <span className="text-fg-secondary font-mono">
              {estimatedCost !== undefined
                ? `${fmt(estimatedCost, 2)} ${quoteCurrency}`
                : "—"}
            </span>
          </span>
          <span>
            Margin used:{" "}
            <span className="text-fg-secondary font-mono">
              {estimatedMargin !== undefined
                ? `${fmt(estimatedMargin, 2)} ${quoteCurrency}`
                : "—"}
            </span>
          </span>
        </div>

        {/* State banners */}
        {state === "risk-block" && (
          <div
            role="alert"
            data-testid="risk-block-banner"
            className="flex items-start gap-2 rounded-sm bg-warn-500/10 border border-warn-700/40 px-3 py-2 text-[12px] text-warn-400"
          >
            <AlertTriangle className="w-4 h-4 mt-0.5 shrink-0" strokeWidth={1.5} />
            <span>{riskBlockReason ?? "Order blocked by risk policy."}</span>
          </div>
        )}
        {state === "kill-switch-armed" && (
          <div
            role="alert"
            data-testid="kill-switch-banner"
            className="flex items-start gap-2 rounded-sm bg-danger-500/15 border border-danger-700/60 px-3 py-2 text-[12px] text-danger-500"
          >
            <ShieldAlert className="w-4 h-4 mt-0.5 shrink-0" strokeWidth={1.5} />
            <span>
              Kill switch armed — disarm at <span className="font-mono">/risk</span> to trade.
            </span>
          </div>
        )}

        {/* Submit */}
        <Button
          ref={submitRef}
          type="button"
          intent={submitIntent}
          size="lg"
          disabled={submitDisabled}
          loading={state === "validating"}
          onClick={handleSubmit}
          tabIndex={5}
          data-testid="order-submit"
          className="w-full justify-center"
          aria-label={submitLabel}
        >
          {submitLabel}
        </Button>
      </div>
    );
  }
);
OrderEntryPanel.displayName = "OrderEntryPanel";

export default OrderEntryPanel;
