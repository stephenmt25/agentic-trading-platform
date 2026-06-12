"use client";

import {
  useCallback,
  useEffect,
  useMemo,
  useState,
} from "react";
import dynamic from "next/dynamic";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import {
  Zap,
  Search,
  ShieldAlert,
  Shield,
  Loader2,
  X,
  FlaskConical,
  Beaker,
  AlertTriangle,
  ArrowUpRight,
} from "lucide-react";
import { toast } from "sonner";

import { Select, Tag, Tooltip } from "@/components/primitives";
import { Pill, StatusDot } from "@/components/data-display";
import {
  type PriceChartCandle,
  type PriceChartTimeframe,
  OrderBook,
  TapeRow,
  PositionRow,
  OrderEntryPanel,
  type OrderEntryPayload,
  PnLBadge,
} from "@/components/trading";
import { PriceChartSkeleton } from "./_components/PriceChartSkeleton";

/**
 * PriceChart is lazy-loaded (next/dynamic, ssr:false) so the rest of the
 * surface — order book, tape, positions, agent feed — paints immediately.
 * The chart's lightweight-charts bundle is large and its initial mount
 * causes ~170ms of forced reflow inside the library; deferring it moves
 * that cost off the critical paint path. The skeleton matches the chart's
 * outer dimensions to keep CLS at 0.
 */
const PriceChart = dynamic(
  () =>
    import("@/components/trading/PriceChart").then((m) => ({
      default: m.PriceChart,
    })),
  {
    ssr: false,
    loading: () => <PriceChartSkeleton />,
  },
);
import {
  AgentSummaryPanel,
  type AgentTraceProps,
} from "@/components/agentic";
import { backendIdToKind } from "@/app/agents/observatory/_components/eventHelpers";
import {
  api,
  type ProfileResponse,
} from "@/lib/api/client";
import { useOrders, usePositions } from "@/lib/api/hooks";
import { useAgentViewStore } from "@/lib/stores/agentViewStore";
import { useShallow } from "zustand/react/shallow";
import {
  severity,
  useKillSwitchStore,
  type HaltLevel,
} from "@/lib/stores/killSwitchStore";
import { useOrderBookStore } from "@/lib/stores/orderbookStore";
import { useOrdersStore, type OptimisticOrder } from "@/lib/stores/ordersStore";
import { usePortfolioStore } from "@/lib/stores/portfolioStore";
import { useTapeStore, type TradePrint } from "@/lib/stores/tapeStore";
import { useTradingModeStore } from "@/lib/stores/tradingModeStore";
import { cn } from "@/lib/utils";

/**
 * /hot/[symbol] — Hot Trading cockpit.
 * Surface spec: docs/design/05-surface-specs/01-hot-trading.md.
 *
 * Three-column HOT layout (left rail is the global LeftRail):
 *   center: chrome → PriceChart (60%) → OrderBook|TapeRow split → tabs
 *   right (360px): OrderEntryPanel + AgentSummaryPanel
 *
 * Wired:
 *   - PriceChart: api.marketData.candles(symbol, timeframe).
 *   - Positions: usePositions (React Query, 5s refetchInterval — stops on
 *     unmount, pauses while the tab is hidden).
 *   - PnL: portfolioStore (populated by wsClient → pubsub:pnl_updates).
 *   - Kill switch: killSwitchStore, mirrored from the single ["killSwitch"]
 *     poll mounted in RedesignShell — no page-local poller (FE-W2);
 *     modal + Cmd+Shift+K hotkey are global (RedesignShell + KillSwitchModal).
 *   - Agent summary: agentViewStore.globalFeed → up to 3 compact AgentTrace cards.
 *   - OrderBook: orderbookStore (populated by wsClient → pubsub:orderbook).
 *   - Tape: tapeStore (populated by wsClient → pubsub:trades).
 *   - Order submit: api.orders.submit → ordersStore (optimistic insert with
 *     rollback on HTTP error); reconciled against the useOrders query.
 *   - Open Orders tab: useOrders (React Query, 5s refetchInterval), merged
 *     with ordersStore optimistic entries.
 *
 * Pending tags surface backend reality where it lags spec:
 *   - Fills tab (no api.orders.fills or pubsub:fills channel yet).
 *   - Drawing tools strip on PriceChart (deferred to v2 — see price-chart.md).
 * (The kill-switch chrome is tiered as of FE-W2 — level verb + severity
 * styling from killSwitchStore.)
 *
 * Per ADR-006 + IA §7: at ≤1024px we drop the right column entirely
 * (monitor-only mode); the chrome still surfaces PnL, positions, and the
 * kill switch — the "user can't trade from a phone" stance.
 */

const TIMEFRAME_LIMIT: Record<PriceChartTimeframe, number> = {
  "1m": 240,
  "5m": 240,
  "15m": 240,
  "1h": 240,
  "4h": 240,
  "1d": 240,
};

const POSITION_POLL_MS = 5_000;
const AGENT_TRACE_CAP = 3;

// Stable empty references so memos don't churn while queries are pending.
const EMPTY_POSITIONS: Position[] = [];

// Server rows persist canonical slash-form symbols (BTC/USDT) — the gateway
// normalizes order submissions — while the URL param is the URL-safe dash
// form (BTC-USDT). Legacy dash-form rows still exist in the DB, so always
// normalize BOTH sides before comparing page symbol against server data.
const toCanonicalSymbol = (s: string) => s.replace(/-/g, "/");

type BottomTab = "positions" | "orders" | "fills";

export default function HotTradingPage() {
  const params = useParams<{ symbol: string }>();
  const router = useRouter();
  const symbol = decodeURIComponent(params.symbol).toUpperCase();

  // ----- Data: candles ----------------------------------------------------
  const [timeframe, setTimeframe] = useState<PriceChartTimeframe>("1m");
  const [candles, setCandles] = useState<PriceChartCandle[]>([]);
  const [candlesLoading, setCandlesLoading] = useState(true);
  const [candlesError, setCandlesError] = useState<string | null>(null);

  const loadCandles = useCallback(async () => {
    setCandlesLoading(true);
    setCandlesError(null);
    try {
      const rows = await api.marketData.candles(
        symbol,
        timeframe,
        TIMEFRAME_LIMIT[timeframe]
      );
      setCandles(
        rows.map((r) => ({
          time: r.time,
          open: r.open,
          high: r.high,
          low: r.low,
          close: r.close,
          volume: r.volume,
        }))
      );
    } catch (e) {
      const msg = e instanceof Error ? e.message : "Failed to load candles";
      setCandlesError(msg);
      setCandles([]);
    } finally {
      setCandlesLoading(false);
    }
  }, [symbol, timeframe]);

  useEffect(() => {
    loadCandles();
  }, [loadCandles]);

  // ----- Data: profiles + active --------------------------------------
  const [profiles, setProfiles] = useState<ProfileResponse[]>([]);
  const [activeProfile, setActiveProfile] = useState<ProfileResponse | null>(
    null
  );
  useEffect(() => {
    let cancelled = false;
    api.profiles
      .list()
      .then((all) => {
        if (cancelled) return;
        setProfiles(all);
        const active = all.find((p) => p.is_active) ?? all[0] ?? null;
        setActiveProfile(active);
      })
      .catch(() => {});
    return () => {
      cancelled = true;
    };
  }, []);

  // ----- Data: positions ---------------------------------------------------
  const activeProfileId = activeProfile?.profile_id;
  // React Query 5s poll — shared ["positions", profileId, "open"] cache,
  // stops refetching on unmount, pauses while the tab is hidden. Errors
  // keep the last good data (the header banner covers connectivity).
  const { data: positionsData } = usePositions(activeProfileId, {
    status: "open",
    refetchInterval: POSITION_POLL_MS,
    enabled: !!activeProfileId,
  });
  const positions = positionsData ?? EMPTY_POSITIONS;

  const symbolPositions = useMemo(() => {
    const canon = toCanonicalSymbol(symbol);
    return positions.filter((p) => toCanonicalSymbol(p.symbol) === canon);
  }, [positions, symbol]);

  // ----- Data: PnL ---------------------------------------------------------
  // pnlData is keyed by position_id (FE-W2 store contract): sum net_post_tax
  // over snapshots belonging to CURRENT open positions only; skip nulls.
  // null result = no contributing snapshot → chrome renders the honest "—"
  // empty state instead of a fake 0.
  const pnlData = usePortfolioStore((s) => s.pnlData);
  const totalNetPnl = useMemo<number | null>(() => {
    const openIds = new Set(positions.map((p) => p.position_id));
    let total = 0;
    let contributed = false;
    for (const snap of Object.values(pnlData)) {
      if (!openIds.has(snap.position_id)) continue;
      if (snap.net_post_tax == null) continue;
      total += snap.net_post_tax;
      contributed = true;
    }
    return contributed ? total : null;
  }, [pnlData, positions]);

  // ----- Data: kill switch -------------------------------------------------
  // No page-local poller (FE-W2): RedesignShell mounts the single 10s
  // ["killSwitch"] poll and mirrors it into killSwitchStore — reading the
  // store here costs zero extra network requests.
  const killLevel = useKillSwitchStore((s) => s.level);
  const openKillModal = useKillSwitchStore((s) => s.setModalOpen);

  // ----- Data: agent traces (filtered to current symbol) ------------------
  // Subscribe to the symbol-filtered, capped top-N events directly from the
  // store with shallow equality. The previous shape — `useAgentViewStore((s)
  // => s.globalFeed)` + useMemo — re-rendered the entire /hot subtree on
  // every ingested event (SSE telemetry flood), because globalFeed gets a
  // new array reference on every ingestEvent. With useShallow comparing the
  // *filtered* slice element-by-element against the prior result, the
  // component re-renders only when the top-N events for this symbol
  // actually change.
  const filteredEvents = useAgentViewStore(
    useShallow((s) => {
      const out: typeof s.globalFeed = [];
      for (
        let i = s.globalFeed.length - 1;
        i >= 0 && out.length < AGENT_TRACE_CAP;
        i--
      ) {
        const e = s.globalFeed[i];
        if (!backendIdToKind(e.agent_id)) continue;
        const payloadSymbol = (e.payload?.symbol as string | undefined)?.toUpperCase();
        if (payloadSymbol && payloadSymbol !== symbol) continue;
        out.push(e);
      }
      return out;
    })
  );
  const agentTraces = useMemo<AgentTraceProps[]>(() => {
    const out: AgentTraceProps[] = [];
    for (const e of filteredEvents) {
      const kind = backendIdToKind(e.agent_id);
      // Selector already filters by kind; the redundant guard keeps the
      // type narrowing local so this loop is self-contained.
      if (!kind) continue;
      out.push({
        agent: kind,
        emittedAt: new Date(e.timestamp).getTime(),
        state: e.event_type === "error" ? "errored" : "complete",
        density: "compact",
      });
    }
    return out;
  }, [filteredEvents]);

  // ----- Order entry shape ------------------------------------------------
  const lastClose = useMemo(() => {
    if (candles.length === 0) return undefined;
    return candles[candles.length - 1].close;
  }, [candles]);

  const beginSubmit = useOrdersStore((s) => s.beginSubmit);
  const confirmSubmit = useOrdersStore((s) => s.confirmSubmit);
  const rejectSubmit = useOrdersStore((s) => s.rejectSubmit);

  const handleSubmit = useCallback(
    async (order: OrderEntryPayload) => {
      if (!activeProfile) {
        toast.error("No active profile — set one in Pipeline Canvas first.");
        return;
      }
      if (order.type !== "limit" && order.type !== "market") {
        toast.error(`${order.type.toUpperCase()} orders aren't wired yet.`);
        return;
      }
      const tempId = beginSubmit({
        profileId: activeProfile.profile_id,
        symbol: order.symbol,
        side: order.side === "buy" ? "BUY" : "SELL",
        type: order.type,
        quantity: String(order.size),
        price: order.price !== undefined ? String(order.price) : undefined,
      });
      try {
        const res = await api.orders.submit({
          profile_id: activeProfile.profile_id,
          symbol: order.symbol,
          side: order.side === "buy" ? "BUY" : "SELL",
          type: order.type,
          quantity: String(order.size),
          price: order.price !== undefined ? String(order.price) : undefined,
        });
        confirmSubmit(tempId, res.order_id);
        toast.success(
          `${order.side.toUpperCase()} ${order.size} ${order.symbol} submitted`
        );
      } catch (e: unknown) {
        const reason = e instanceof Error ? e.message : "Submit failed";
        rejectSubmit(tempId, reason);
        toast.error(`Order rejected: ${reason}`);
      }
    },
    [activeProfile, beginSubmit, confirmSubmit, rejectSubmit]
  );

  // ----- Symbol switcher --------------------------------------------------
  // Mirrors the symbols ingestion currently publishes
  // (services/ingestion/src/main.py:47). Add new symbols there first.
  const symbolOptions = useMemo(
    () => [
      { value: "BTC-USDT", label: "BTC-USDT" },
      { value: "ETH-USDT", label: "ETH-USDT" },
    ],
    []
  );

  return (
    <div data-mode="hot" className="flex flex-col h-full bg-bg-canvas text-fg">
      <HotChrome
        symbol={symbol}
        onSymbolChange={(s) =>
          router.push(`/hot/${encodeURIComponent(s)}`)
        }
        symbolOptions={symbolOptions}
        profile={activeProfile}
        profiles={profiles}
        onProfileChange={(id) => {
          const next = profiles.find((p) => p.profile_id === id);
          if (next) setActiveProfile(next);
        }}
        totalNetPnl={totalNetPnl}
        killLevel={killLevel}
        onOpenKillModal={() => openKillModal(true)}
      />

      <div className="flex-1 min-h-0 flex overflow-hidden">
        {/* CENTER COLUMN ----------------------------------------------- */}
        <section className="flex-1 min-w-0 flex flex-col">
          {/* Top: PriceChart (60% h) — fluid so the chart follows the flex
              allocation instead of overflowing on smaller viewports. */}
          <div className="flex-[3] min-h-0 px-3 pt-3 flex flex-col">
            <PriceChart
              candles={candles}
              symbol={symbol}
              timeframe={timeframe}
              onTimeframeChange={setTimeframe}
              loading={candlesLoading}
              error={candlesError ?? undefined}
              withDrawingTools
              fluid
              className="flex-1 min-h-0"
            />
          </div>

          {/* Mid: OrderBook | TapeRow (40% h, side-by-side) */}
          <div className="flex-[2] min-h-0 grid grid-cols-1 md:grid-cols-2 gap-3 px-3 pt-3">
            <OrderBookPanel symbol={symbol} />
            <TapePanel symbol={symbol} />
          </div>

          {/* Bottom: Positions / Orders / Fills tabs */}
          <BottomTabs
            symbol={symbol}
            profileId={activeProfileId}
            symbolPositions={symbolPositions}
            allPositionsCount={positions.length}
          />
        </section>

        {/* RIGHT COLUMN — hidden in monitor-only mode (≤1024px) ---------- */}
        <aside
          className="hidden lg:flex w-[360px] shrink-0 border-l border-border-subtle flex-col overflow-hidden"
          aria-label="Trade and agents"
        >
          <div className="p-3 border-b border-border-subtle">
            <OrderEntryPanel
              symbol={symbol}
              midPrice={lastClose}
              haltLevel={killLevel}
              onSubmit={handleSubmit}
              availableSize={1}
              density="compact"
            />
          </div>
          <div className="p-3 flex-1 min-h-0 overflow-hidden">
            <AgentSummaryPanel
              traces={agentTraces}
              state={agentTraces.length === 0 ? "empty" : "default"}
              seeAllHref="/agents/observatory"
              maxItems={AGENT_TRACE_CAP}
            />
          </div>
        </aside>
      </div>

      {/* Monitor-only banner at narrow widths */}
      <div
        className="lg:hidden border-t border-warn-700/40 bg-warn-700/10 text-warn-400 text-[12px] px-4 py-2 flex items-center gap-2"
        role="status"
      >
        <ShieldAlert className="w-3.5 h-3.5 shrink-0" strokeWidth={1.5} aria-hidden />
        <span>
          Monitor-only mode — order entry is hidden below 1024px (per ADR-006).
        </span>
      </div>

    </div>
  );
}

/* -------------------------- Chrome --------------------------------------- */

interface HotChromeProps {
  symbol: string;
  onSymbolChange: (s: string) => void;
  symbolOptions: { value: string; label: string }[];
  profile: ProfileResponse | null;
  profiles: ProfileResponse[];
  onProfileChange: (profileId: string) => void;
  /** null = no contributing PnL snapshot → render the honest "—". */
  totalNetPnl: number | null;
  /** Tiered halt level (killSwitchStore) — chrome renders the level verb. */
  killLevel: HaltLevel;
  onOpenKillModal: () => void;
}

function HotChrome({
  symbol,
  onSymbolChange,
  symbolOptions,
  profile,
  profiles,
  onProfileChange,
  totalNetPnl,
  killLevel,
  onOpenKillModal,
}: HotChromeProps) {
  // Tiered chrome (FE-W2): danger tier for position-destructive verbs
  // (NEUTRALIZE/FLATTEN), warn tier for STOP_OPENING/DE_RISK, neutral when
  // NONE. Display only — the backend enforces the halt policy.
  const killSev = severity(killLevel);
  // Active-only — inactive profiles can't route orders, so showing them
  // in the switcher would let the user submit through a profile the
  // backend will silently drop. The "all profiles" link covers discovery
  // of inactive ones via the comparison grid.
  const activeProfileOptions = useMemo(
    () =>
      profiles
        .filter((p) => p.is_active)
        .map((p) => ({ value: p.profile_id, label: p.name })),
    [profiles]
  );
  const tradingMode = useTradingModeStore((s) => s.mode);
  // Per Phase 8.1 GAP-3 (real-money risk class): show the active mode next
  // to the kill-switch on /hot so a glance never misreads paper vs live.
  // The store is bootstrap-fetched by the chrome StatusPills.
  const modeMeta = tradingMode
    ? tradingMode === "PAPER"
      ? { Icon: FlaskConical, tone: "border-warn-700/50 bg-warn-700/15 text-warn-400" }
      : tradingMode === "TESTNET"
        ? { Icon: Beaker, tone: "border-accent-700/50 bg-accent-900/30 text-accent-400" }
        : { Icon: AlertTriangle, tone: "border-danger-700/50 bg-danger-700/15 text-danger-500" }
    : null;

  return (
    <header className="border-b border-border-subtle">
      {/* Breadcrumb row */}
      <div className="flex items-center justify-between gap-3 px-4 py-2">
        <div className="flex items-center gap-2 text-[12px] text-fg-muted min-w-0">
          <Link
            href="/hot"
            className="inline-flex items-center gap-1 hover:text-fg transition-colors focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent-500 rounded-sm"
          >
            <Zap className="w-3.5 h-3.5" strokeWidth={1.5} aria-hidden />
            Hot Trading
          </Link>
          <span aria-hidden>/</span>
          <Select
            options={symbolOptions}
            value={symbol}
            onValueChange={onSymbolChange}
            density="compact"
            aria-label="Symbol"
            className="w-32"
            searchable
            placeholder="Symbol"
          />
          {profile && (
            <>
              <span aria-hidden className="ml-2">·</span>
              <span className="num-tabular text-fg-secondary inline-flex items-center gap-1.5">
                Profile:{" "}
                {activeProfileOptions.length > 0 ? (
                  <Select
                    options={activeProfileOptions}
                    value={profile.profile_id}
                    onValueChange={onProfileChange}
                    density="compact"
                    aria-label="Active profile"
                    className="w-40"
                    searchable={activeProfileOptions.length > 6}
                  />
                ) : (
                  <Link
                    href={`/hot/profiles/${encodeURIComponent(profile.profile_id)}`}
                    className="font-mono text-fg inline-flex items-center gap-0.5 hover:text-accent-300 transition-colors focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent-500 rounded-sm"
                  >
                    {profile.name}
                    <ArrowUpRight className="w-3 h-3" strokeWidth={1.5} aria-hidden />
                  </Link>
                )}
                <span aria-hidden className="text-fg-muted">·</span>
                <Link
                  href="/hot/profiles"
                  className="text-fg-muted hover:text-fg-secondary transition-colors focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent-500 rounded-sm"
                >
                  all profiles
                </Link>
              </span>
            </>
          )}
          {profiles.length > 1 && profile && !profile.is_active && (
            <Tag intent="warn">no active profile</Tag>
          )}
        </div>
        <div className="flex items-center gap-2">
          <Tooltip content="Search markets — Cmd+K">
            <button
              className="text-fg-muted hover:text-fg p-1 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent-500 rounded-sm"
              aria-label="Search"
              type="button"
            >
              <Search className="w-3.5 h-3.5" strokeWidth={1.5} />
            </button>
          </Tooltip>
        </div>
      </div>

      {/* Status pills row */}
      <div className="flex items-center gap-2 px-4 pb-2 overflow-x-auto">
        <Pill intent="bid" icon={<StatusDot state="live" size={6} pulse />}>
          live
        </Pill>
        <span className="text-fg-muted text-[12px] inline-flex items-center gap-1">
          <Tag intent="warn">Pending</Tag>
          <span>regime</span>
        </span>
        <span className="text-fg-muted text-[12px] inline-flex items-center gap-1">
          <Tag intent="warn">Pending</Tag>
          <span>latency</span>
        </span>
        <button
          type="button"
          onClick={onOpenKillModal}
          aria-label="Open kill-switch modal (Cmd+Shift+K)"
          data-halt-level={killLevel}
          className={cn(
            "inline-flex items-center gap-1.5 px-2.5 h-6 rounded-full border text-[11px] num-tabular font-medium",
            "focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent-500",
            killSev === "danger"
              ? "border-danger-700/50 bg-danger-700/15 text-danger-500 hover:bg-danger-700/25"
              : killSev === "warn"
                ? "border-warn-700/50 bg-warn-700/15 text-warn-400 hover:bg-warn-700/25"
                : "border-border-subtle bg-bg-canvas text-fg-secondary hover:bg-bg-rowhover"
          )}
        >
          {killSev === "off" ? (
            <Shield className="w-3 h-3" strokeWidth={1.5} aria-hidden />
          ) : (
            <ShieldAlert className="w-3 h-3" strokeWidth={1.5} aria-hidden />
          )}
          {killSev === "off" ? "disarmed" : killLevel}
        </button>
        {modeMeta && tradingMode && (
          <span
            className={cn(
              "inline-flex items-center gap-1.5 px-2.5 h-6 rounded-full border text-[11px] num-tabular font-medium",
              modeMeta.tone
            )}
            aria-label={`Trading mode: ${tradingMode}`}
          >
            <modeMeta.Icon className="w-3 h-3" strokeWidth={1.5} aria-hidden />
            {tradingMode.toLowerCase()}
          </span>
        )}
        <span className="text-fg-muted text-[12px] inline-flex items-center gap-1">
          <Tag intent="warn">Pending</Tag>
          <span>agent count</span>
        </span>
        <span className="ml-auto inline-flex items-center gap-2 num-tabular text-[12px] text-fg-muted">
          PnL{" "}
          {totalNetPnl === null ? (
            <span
              className="text-2xl font-semibold tracking-tight text-fg-muted"
              aria-label="PnL unavailable — no live snapshot for open positions"
            >
              —
            </span>
          ) : (
            <PnLBadge value={totalNetPnl} mode="absolute" size="prominent" signed />
          )}
        </span>
      </div>
    </header>
  );
}

/* -------------------------- OrderBook panel ------------------------------ */

const STALE_AFTER_MS = 5_000;

function OrderBookPanel({ symbol }: { symbol: string }) {
  const snapshot = useOrderBookStore((s) => s.bySymbol[symbol]);
  // Tick once per second to recompute the staleness indicator without
  // re-rendering on every store update.
  const [now, setNow] = useState<number>(() => Date.now());
  useEffect(() => {
    const id = window.setInterval(() => setNow(Date.now()), 1_000);
    return () => window.clearInterval(id);
  }, []);

  // Staleness measures frontend receive time (receivedAtMs), NOT the
  // exchange-reported timestampMs — the latter can be 0 or clock-skewed, so
  // a badge wired to it lies in the always-stale direction (tech-debt row 32).
  const isStale =
    snapshot !== undefined && now - snapshot.receivedAtMs > STALE_AFTER_MS;
  const isEmpty = !snapshot || snapshot.bids.length === 0;

  return (
    <div className="rounded-md border border-border-subtle bg-bg-panel flex flex-col overflow-hidden min-h-0">
      <header className="flex items-center gap-2 px-3 h-8 border-b border-border-subtle">
        <span className="text-[10px] uppercase tracking-wider text-fg-muted num-tabular">
          order book — {symbol}
        </span>
        {snapshot && !isStale && (
          <Pill intent="bid" icon={<StatusDot state="live" size={6} pulse />}>
            live
          </Pill>
        )}
        {snapshot && isStale && (
          <Tag intent="warn" className="ml-auto">
            stale {Math.floor((now - snapshot.receivedAtMs) / 1000)}s
          </Tag>
        )}
      </header>
      <div className="flex-1 min-h-0 overflow-hidden">
        {isEmpty ? (
          <p className="px-3 py-3 text-[12px] text-fg-muted">
            No book data — awaiting feed.
          </p>
        ) : (
          <OrderBook
            bids={snapshot!.bids}
            asks={snapshot!.asks}
            depthRows={10}
            priceDigits={2}
          />
        )}
      </div>
    </div>
  );
}

/* -------------------------- Tape panel ---------------------------------- */

const TAPE_VISIBLE = 50;
// Stable empty-trades reference so the selector returns the same identity
// when the symbol has no data — avoids re-rendering on every unrelated
// store update (e.g. another symbol's trade arriving).
const EMPTY_TRADES: TradePrint[] = [];

function TapePanel({ symbol }: { symbol: string }) {
  const trades = useTapeStore((s) => s.bySymbol[symbol] ?? EMPTY_TRADES);
  const visible = useMemo(() => trades.slice(0, TAPE_VISIBLE), [trades]);

  return (
    <div className="rounded-md border border-border-subtle bg-bg-panel flex flex-col overflow-hidden min-h-0">
      <header className="flex items-center gap-2 px-3 h-8 border-b border-border-subtle">
        <span className="text-[10px] uppercase tracking-wider text-fg-muted num-tabular">
          tape — {symbol}
        </span>
        {trades.length > 0 ? (
          <Pill intent="bid" icon={<StatusDot state="live" size={6} pulse />}>
            live
          </Pill>
        ) : null}
      </header>
      <div className="flex-1 min-h-0 overflow-y-auto">
        {visible.length === 0 ? (
          <p className="px-3 py-3 text-[12px] text-fg-muted">
            Awaiting trades — no prints yet for this symbol.
          </p>
        ) : (
          visible.map((t, i) => (
            <TapeRow
              key={`${t.tradeId ?? t.timestampMs}-${i}`}
              side={t.side}
              time={t.timestampMs}
              size={t.size}
              price={t.price}
              density="compact"
            />
          ))
        )}
      </div>
    </div>
  );
}

/* -------------------------- Bottom tabs --------------------------------- */

type Position = Awaited<ReturnType<typeof api.positions.list>>[number];

function BottomTabs({
  symbol,
  profileId,
  symbolPositions,
  allPositionsCount,
}: {
  symbol: string;
  profileId: string | undefined;
  symbolPositions: Position[];
  allPositionsCount: number;
}) {
  const [tab, setTab] = useState<BottomTab>("positions");
  const orders = useOpenOrdersForSymbol(symbol, profileId);
  return (
    <section className="flex-[2] min-h-0 flex flex-col border-t border-border-subtle">
      <header className="flex items-center gap-0.5 px-2 h-9 border-b border-border-subtle">
        <TabButton active={tab === "positions"} onClick={() => setTab("positions")}>
          Positions
          <span className="text-fg-muted num-tabular ml-1">
            ({symbolPositions.length})
          </span>
        </TabButton>
        <TabButton active={tab === "orders"} onClick={() => setTab("orders")}>
          Open orders
          {orders.length > 0 && (
            <span className="text-fg-muted num-tabular ml-1">({orders.length})</span>
          )}
        </TabButton>
        <TabButton active={tab === "fills"} onClick={() => setTab("fills")}>
          Fills
        </TabButton>
        <span className="ml-auto text-[10px] text-fg-muted num-tabular">
          {allPositionsCount} total open
        </span>
      </header>
      <div className="flex-1 min-h-0 overflow-auto">
        {tab === "positions" && <PositionsList rows={symbolPositions} />}
        {tab === "orders" && <OrdersList rows={orders} />}
        {tab === "fills" && (
          <PendingPanel
            label="Fills"
            description="Fills auto-tab for 4s after each fill per spec §2 — needs an /orders/fills endpoint or pubsub:fills channel; neither is wired."
          />
        )}
      </div>
    </section>
  );
}

/* -------------------------- Open Orders --------------------------------- */

type ServerOrder = Awaited<ReturnType<typeof api.orders.list>>[number];

// Stable empty reference — keeps the merge memo from churning while the
// orders query is pending/disabled.
const EMPTY_SERVER_ORDERS: ServerOrder[] = [];

interface OpenOrderRow {
  /** Either the server order_id or the optimistic tempId. */
  rowKey: string;
  orderId: string | null;
  symbol: string;
  side: "BUY" | "SELL";
  quantity: string;
  price?: string;
  status: string;
  source: "optimistic" | "server";
  rejectionReason?: string;
  submittedAtMs: number;
  raw?: ServerOrder;
}

const OPEN_ORDER_STATUSES = new Set(["PENDING", "SUBMITTED"]);

function useOpenOrdersForSymbol(
  symbol: string,
  profileId: string | undefined
): OpenOrderRow[] {
  const optimistic = useOrdersStore((s) => s.optimistic);
  const reconcile = useOrdersStore((s) => s.reconcile);

  // Server rows are canonical slash-form; the page symbol is dash-form.
  const canonicalSymbol = toCanonicalSymbol(symbol);

  // React Query 5s poll (refetchInterval lives in useOrders). Enabled only
  // with both symbol and profile — mirrors the old guard that skipped the
  // fetch without a profileId. On error the last good data is kept; the
  // optimistic state still surfaces what the user saw.
  const { data: ordersData } = useOrders(
    { symbol: canonicalSymbol, profileId, limit: 50 },
    { enabled: !!profileId }
  );
  const serverRows = ordersData ?? EMPTY_SERVER_ORDERS;

  // Reconcile confirmed optimistic entries against each server snapshot —
  // exactly the call the old setInterval tick made. React Query's
  // structural sharing keeps `ordersData` referentially stable when the
  // payload is unchanged, so this effect fires only on real updates.
  useEffect(() => {
    if (!ordersData) return;
    reconcile(new Set(ordersData.map((r) => r.order_id)));
  }, [ordersData, reconcile]);

  return useMemo(() => {
    const out: OpenOrderRow[] = [];
    const claimed = new Set<string>();
    for (const o of optimistic) {
      if (toCanonicalSymbol(o.symbol) !== canonicalSymbol) continue;
      if (profileId && o.profileId !== profileId) continue;
      if (o.status === "confirmed" && o.orderId && serverRows.some((r) => r.order_id === o.orderId)) {
        // Server already shows it — skip the optimistic shadow.
        claimed.add(o.orderId);
        continue;
      }
      out.push(toOptimisticRow(o));
    }
    for (const r of serverRows) {
      if (!OPEN_ORDER_STATUSES.has(r.status)) continue;
      if (toCanonicalSymbol(r.symbol) !== canonicalSymbol) continue;
      if (claimed.has(r.order_id)) continue;
      out.push(toServerRow(r));
    }
    out.sort((a, b) => b.submittedAtMs - a.submittedAtMs);
    return out;
  }, [optimistic, serverRows, canonicalSymbol, profileId]);
}

function toOptimisticRow(o: OptimisticOrder): OpenOrderRow {
  return {
    rowKey: o.tempId,
    orderId: o.orderId,
    symbol: o.symbol,
    side: o.side,
    quantity: o.quantity,
    price: o.price,
    status: o.status === "submitting" ? "submitting" : o.status === "rejected" ? "rejected" : "PENDING",
    source: "optimistic",
    rejectionReason: o.rejectionReason,
    submittedAtMs: o.submittedAtMs,
  };
}

function toServerRow(r: ServerOrder): OpenOrderRow {
  return {
    rowKey: r.order_id,
    orderId: r.order_id,
    symbol: r.symbol,
    side: r.side,
    quantity: r.quantity,
    price: r.price,
    status: r.status,
    source: "server",
    submittedAtMs: Date.parse(r.created_at) || 0,
    raw: r,
  };
}

function OrdersList({ rows }: { rows: OpenOrderRow[] }) {
  const dropOptimistic = useOrdersStore((s) => s.drop);

  if (rows.length === 0) {
    return (
      <p className="px-4 py-3 text-[12px] text-fg-muted">
        No open orders for this symbol. Use the order entry panel on the right.
      </p>
    );
  }
  return (
    <ul className="divide-y divide-border-subtle">
      {rows.map((r) => (
        <li
          key={r.rowKey}
          className="px-4 py-2 flex items-center gap-3 text-[12px] num-tabular"
        >
          <Pill intent={r.side === "BUY" ? "bid" : "ask"}>
            {r.side}
          </Pill>
          <span className="font-mono text-fg">{r.quantity}</span>
          <span className="text-fg-muted">@</span>
          <span className="font-mono text-fg">{r.price ?? "mkt"}</span>
          <span className="ml-auto flex items-center gap-2">
            {r.status === "submitting" && (
              <Pill intent="warn" icon={<Loader2 className="w-3 h-3 animate-spin" aria-hidden />}>
                submitting
              </Pill>
            )}
            {r.status === "rejected" && (
              <>
                <Pill intent="ask">rejected</Pill>
                {r.rejectionReason && (
                  <span className="text-fg-muted truncate max-w-[240px]" title={r.rejectionReason}>
                    {r.rejectionReason}
                  </span>
                )}
                <button
                  type="button"
                  onClick={() => dropOptimistic(r.rowKey)}
                  aria-label="Dismiss"
                  className="text-fg-muted hover:text-fg p-0.5 rounded-sm focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent-500"
                >
                  <X className="w-3 h-3" strokeWidth={1.5} aria-hidden />
                </button>
              </>
            )}
            {r.status !== "submitting" && r.status !== "rejected" && (
              <Pill intent="neutral">{r.status.toLowerCase()}</Pill>
            )}
          </span>
        </li>
      ))}
    </ul>
  );
}

function TabButton({
  active,
  onClick,
  children,
}: {
  active: boolean;
  onClick: () => void;
  children: React.ReactNode;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      aria-pressed={active}
      className={cn(
        "h-7 px-3 text-[12px] font-medium num-tabular rounded-sm transition-colors",
        "focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent-500",
        active
          ? "text-fg border-b-2 border-accent-500 -mb-px"
          : "text-fg-muted hover:text-fg-secondary hover:bg-bg-rowhover"
      )}
    >
      {children}
    </button>
  );
}

function PositionsList({ rows }: { rows: Position[] }) {
  if (rows.length === 0) {
    return (
      <p className="px-4 py-3 text-[12px] text-fg-muted">
        No open positions for this symbol. Use the order entry panel to place
        your first order.
      </p>
    );
  }
  return (
    <ul className="divide-y divide-border-subtle">
      {rows.map((p) => (
        <li key={p.position_id}>
          <PositionRow
            symbol={p.symbol}
            side={p.side === "BUY" ? "long" : "short"}
            size={parseFloat(p.quantity)}
            entry={parseFloat(p.entry_price)}
            mark={p.mark_price ? parseFloat(p.mark_price) : parseFloat(p.entry_price)}
            unrealized={p.unrealized_net_pnl ?? 0}
            margin={p.profile_notional ? parseFloat(p.profile_notional) : 0}
            leverage={1}
            density="standard"
          />
        </li>
      ))}
    </ul>
  );
}

function PendingPanel({
  label,
  description,
}: {
  label: string;
  description: string;
}) {
  return (
    <div className="px-4 py-4 flex flex-col gap-2 text-[12px]">
      <div className="flex items-center gap-2">
        <Tag intent="warn">Pending</Tag>
        <span className="text-fg">{label}</span>
      </div>
      <p className="text-fg-muted">{description}</p>
    </div>
  );
}

