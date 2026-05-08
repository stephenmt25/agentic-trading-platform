"use client";

import {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import {
  Zap,
  Search,
  ShieldAlert,
  Shield,
  Loader2,
  X,
  Lock,
  Unlock,
} from "lucide-react";
import { toast } from "sonner";

import { Button, Input, Select, Tag, Tooltip } from "@/components/primitives";
import { Pill, StatusDot } from "@/components/data-display";
import {
  PriceChart,
  type PriceChartCandle,
  type PriceChartTimeframe,
  OrderBook,
  type OrderBookLevel,
  TapeRow,
  PositionRow,
  OrderEntryPanel,
  type OrderEntryPayload,
  PnLBadge,
} from "@/components/trading";
import {
  AgentSummaryPanel,
  type AgentTraceProps,
} from "@/components/agentic";
import { backendIdToKind } from "@/app/agents/observatory/_components/eventHelpers";
import {
  api,
  type ProfileResponse,
  type KillSwitchStatus,
} from "@/lib/api/client";
import { useAgentViewStore } from "@/lib/stores/agentViewStore";
import { useKillSwitchStore } from "@/lib/stores/killSwitchStore";
import { usePortfolioStore } from "@/lib/stores/portfolioStore";
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
 *   - Positions: api.positions.list, polled.
 *   - PnL: portfolioStore (populated by wsClient → pubsub:pnl_updates).
 *   - Kill switch: api.commands.killSwitchStatus, polled. Cmd+Shift+K modal local.
 *   - Agent summary: agentViewStore.globalFeed → up to 3 compact AgentTrace cards.
 *
 * Pending tags surface backend reality where it lags spec:
 *   - OrderBook live data (no orderbook channel on the WS feed).
 *   - TapeRow live trades (no trades channel on the WS feed).
 *   - Order submission (no api.orders.submit endpoint exposed).
 *   - Open Orders / Fills tabs (no endpoints — only Positions is wired).
 *   - Hard-arm kill switch state (backend is binary; same as /risk).
 *   - Drawing tools strip on PriceChart (deferred to v2 — see price-chart.md).
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
const KILL_POLL_MS = 10_000;
const AGENT_TRACE_CAP = 3;

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
  type Position = Awaited<ReturnType<typeof api.positions.list>>[number];
  const [positions, setPositions] = useState<Position[]>([]);

  const loadPositions = useCallback(async () => {
    try {
      const rows = await api.positions.list({ status: "open" });
      setPositions(rows);
    } catch {
      // swallow — header banner covers connectivity issues elsewhere
    }
  }, []);

  useEffect(() => {
    loadPositions();
    const id = window.setInterval(loadPositions, POSITION_POLL_MS);
    return () => window.clearInterval(id);
  }, [loadPositions]);

  const symbolPositions = useMemo(
    () => positions.filter((p) => p.symbol === symbol),
    [positions, symbol]
  );

  // ----- Data: PnL ---------------------------------------------------------
  const pnlData = usePortfolioStore((s) => s.pnlData);
  const totalNetPnl = useMemo(() => {
    let total = 0;
    for (const snap of Object.values(pnlData)) {
      total += snap.net_post_tax ?? 0;
    }
    return total;
  }, [pnlData]);

  // ----- Data: kill switch -------------------------------------------------
  const [killStatus, setKillStatus] = useState<KillSwitchStatus | null>(null);
  const setLocalKill = useKillSwitchStore((s) => s.setState);
  const loadKill = useCallback(async () => {
    try {
      const s = await api.commands.killSwitchStatus();
      setKillStatus(s);
      setLocalKill(s.active ? "soft" : "off");
    } catch {
      /* leave previous */
    }
  }, [setLocalKill]);
  useEffect(() => {
    loadKill();
    const id = window.setInterval(loadKill, KILL_POLL_MS);
    return () => window.clearInterval(id);
  }, [loadKill]);

  const armed = killStatus?.active === true;

  // ----- Data: agent traces (filtered to current symbol) ------------------
  const globalFeed = useAgentViewStore((s) => s.globalFeed);
  const agentTraces = useMemo<AgentTraceProps[]>(() => {
    // Surface the most recent N decision-trace / output-emitted events for
    // agentic kinds; map to AgentTraceProps for the AgentSummaryPanel.
    const out: AgentTraceProps[] = [];
    for (let i = globalFeed.length - 1; i >= 0 && out.length < AGENT_TRACE_CAP; i--) {
      const e = globalFeed[i];
      const kind = backendIdToKind(e.agent_id);
      if (!kind) continue;
      // Symbol filter: prefer events whose payload references this symbol;
      // fall back to all traces when there are no symbol-tagged emissions.
      const payloadSymbol = (e.payload?.symbol as string | undefined)?.toUpperCase();
      if (payloadSymbol && payloadSymbol !== symbol) continue;
      out.push({
        agent: kind,
        emittedAt: new Date(e.timestamp).getTime(),
        state: e.event_type === "error" ? "errored" : "complete",
        density: "compact",
      });
    }
    return out;
  }, [globalFeed, symbol]);

  // ----- Kill-switch modal (Cmd+Shift+K) ---------------------------------
  const [killModalOpen, setKillModalOpen] = useState(false);
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.shiftKey && e.key.toLowerCase() === "k") {
        e.preventDefault();
        setKillModalOpen((open) => !open);
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  // ----- Order entry shape ------------------------------------------------
  const lastClose = useMemo(() => {
    if (candles.length === 0) return undefined;
    return candles[candles.length - 1].close;
  }, [candles]);

  const handleSubmit = useCallback(
    (order: OrderEntryPayload) => {
      // No `api.orders.submit` endpoint is exposed in the redesign yet —
      // surface a Pending toast instead of pretending to place an order.
      toast.info(
        `Order entry not wired — Pending. ${order.side.toUpperCase()} ${order.size} ${
          order.symbol
        } at ${order.type}${order.price ? ` @ ${order.price}` : ""}`
      );
    },
    []
  );

  // ----- Symbol switcher --------------------------------------------------
  const symbolOptions = useMemo(
    () => [
      { value: "BTC-PERP", label: "BTC-PERP" },
      { value: "ETH-PERP", label: "ETH-PERP" },
      { value: "SOL-PERP", label: "SOL-PERP" },
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
        totalNetPnl={totalNetPnl}
        killArmed={armed}
        onOpenKillModal={() => setKillModalOpen(true)}
      />

      <div className="flex-1 min-h-0 flex overflow-hidden">
        {/* CENTER COLUMN ----------------------------------------------- */}
        <section className="flex-1 min-w-0 flex flex-col">
          {/* Top: PriceChart (60% h) */}
          <div className="flex-[3] min-h-0 px-3 pt-3">
            <PriceChart
              candles={candles}
              symbol={symbol}
              timeframe={timeframe}
              onTimeframeChange={setTimeframe}
              loading={candlesLoading}
              error={candlesError ?? undefined}
              withDrawingTools
              density="standard"
            />
          </div>

          {/* Mid: OrderBook | TapeRow (40% h, side-by-side) */}
          <div className="flex-[2] min-h-0 grid grid-cols-1 md:grid-cols-2 gap-3 px-3 pt-3">
            <OrderBookPanel symbol={symbol} midPrice={lastClose} />
            <TapePanel symbol={symbol} />
          </div>

          {/* Bottom: Positions / Orders / Fills tabs */}
          <BottomTabs
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
              state={armed ? "kill-switch-armed" : "ok"}
              onSubmit={handleSubmit}
              availableSize={1}
              density="compact"
            />
            <p className="text-[10px] text-fg-muted mt-2 flex items-center gap-1.5">
              <Tag intent="warn">Pending</Tag>
              <span>order submission endpoint</span>
            </p>
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

      {killModalOpen && (
        <KillSwitchModal
          armed={armed}
          onClose={() => setKillModalOpen(false)}
          onChanged={loadKill}
        />
      )}
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
  totalNetPnl: number;
  killArmed: boolean;
  onOpenKillModal: () => void;
}

function HotChrome({
  symbol,
  onSymbolChange,
  symbolOptions,
  profile,
  profiles,
  totalNetPnl,
  killArmed,
  onOpenKillModal,
}: HotChromeProps) {
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
              <span className="num-tabular text-fg-secondary">
                Profile:{" "}
                <span className="font-mono text-fg">
                  {profile.name}
                </span>
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
          className={cn(
            "inline-flex items-center gap-1.5 px-2.5 h-6 rounded-full border text-[11px] num-tabular font-medium",
            "focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent-500",
            killArmed
              ? "border-warn-700/50 bg-warn-700/15 text-warn-400 hover:bg-warn-700/25"
              : "border-border-subtle bg-bg-canvas text-fg-secondary hover:bg-bg-rowhover"
          )}
        >
          {killArmed ? (
            <ShieldAlert className="w-3 h-3" strokeWidth={1.5} aria-hidden />
          ) : (
            <Shield className="w-3 h-3" strokeWidth={1.5} aria-hidden />
          )}
          {killArmed ? "armed-soft" : "disarmed"}
        </button>
        <span className="text-fg-muted text-[12px] inline-flex items-center gap-1">
          <Tag intent="warn">Pending</Tag>
          <span>agent count</span>
        </span>
        <span className="ml-auto inline-flex items-center gap-2 num-tabular text-[12px] text-fg-muted">
          PnL{" "}
          <PnLBadge value={totalNetPnl} mode="absolute" size="prominent" signed />
        </span>
      </div>
    </header>
  );
}

/* -------------------------- OrderBook panel ------------------------------ */

function OrderBookPanel({
  symbol,
  midPrice,
}: {
  symbol: string;
  midPrice?: number;
}) {
  // Synthesize a small static book centered on midPrice so the panel renders
  // with believable structure. Live updates are Pending — no orderbook
  // WebSocket channel exists in lib/ws/client.ts as of this commit.
  const { bids, asks } = useMemo(() => {
    if (!midPrice) return { bids: [], asks: [] };
    const tick = midPrice * 0.0001;
    const bidsOut: OrderBookLevel[] = [];
    const asksOut: OrderBookLevel[] = [];
    for (let i = 0; i < 20; i++) {
      bidsOut.push({
        price: midPrice - tick * (i + 1),
        size: 0.4 + Math.abs(Math.sin(i + 1)) * 1.2,
      });
      asksOut.push({
        price: midPrice + tick * (i + 1),
        size: 0.4 + Math.abs(Math.cos(i + 1)) * 1.2,
      });
    }
    return { bids: bidsOut, asks: asksOut };
  }, [midPrice]);

  return (
    <div className="rounded-md border border-border-subtle bg-bg-panel flex flex-col overflow-hidden min-h-0">
      <header className="flex items-center gap-2 px-3 h-8 border-b border-border-subtle">
        <span className="text-[10px] uppercase tracking-wider text-fg-muted num-tabular">
          order book — {symbol}
        </span>
        <Tag intent="warn" className="ml-auto">
          Pending live data
        </Tag>
      </header>
      <div className="flex-1 min-h-0 overflow-hidden">
        {bids.length === 0 ? (
          <p className="px-3 py-3 text-[12px] text-fg-muted">
            No book data — awaiting feed.
          </p>
        ) : (
          <OrderBook bids={bids} asks={asks} depthRows={10} priceDigits={2} />
        )}
      </div>
    </div>
  );
}

/* -------------------------- Tape panel ---------------------------------- */

function TapePanel({ symbol }: { symbol: string }) {
  // Tape feed is Pending — render empty-state per spec §7. The synthetic
  // example row uses a stable timestamp so renders stay deterministic.
  return (
    <div className="rounded-md border border-border-subtle bg-bg-panel flex flex-col overflow-hidden min-h-0">
      <header className="flex items-center gap-2 px-3 h-8 border-b border-border-subtle">
        <span className="text-[10px] uppercase tracking-wider text-fg-muted num-tabular">
          tape — {symbol}
        </span>
        <Tag intent="warn" className="ml-auto">
          Pending live data
        </Tag>
      </header>
      <div className="flex-1 min-h-0 overflow-hidden">
        <p className="px-3 py-3 text-[12px] text-fg-muted">
          Awaiting trades — no public-trade WebSocket channel wired yet.
        </p>
        <div className="opacity-50 pointer-events-none">
          <TapeRow side="bid" time={SAMPLE_TAPE_TIME} size={0.123} price={0} />
        </div>
      </div>
    </div>
  );
}

// Stable timestamp for the synthetic tape row example (avoids Date.now() in
// render — react-hooks/purity rule flags impure calls inside components).
const SAMPLE_TAPE_TIME = Date.UTC(2026, 4, 8, 14, 0, 0);

/* -------------------------- Bottom tabs --------------------------------- */

type Position = Awaited<ReturnType<typeof api.positions.list>>[number];

function BottomTabs({
  symbolPositions,
  allPositionsCount,
}: {
  symbolPositions: Position[];
  allPositionsCount: number;
}) {
  const [tab, setTab] = useState<BottomTab>("positions");
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
        {tab === "orders" && (
          <PendingPanel
            label="Open orders"
            description="No /orders endpoint is exposed in the redesign API client yet. The legacy execution log lives in services/execution; surfacing it here lands with the order-submission wiring."
          />
        )}
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

/* -------------------------- Kill switch modal --------------------------- */

interface KillSwitchModalProps {
  armed: boolean;
  onClose: () => void;
  onChanged: () => Promise<void>;
}

function KillSwitchModal({ armed, onClose, onChanged }: KillSwitchModalProps) {
  const [reason, setReason] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const inputRef = useRef<HTMLInputElement | null>(null);

  useEffect(() => {
    inputRef.current?.focus();
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  const submit = useCallback(
    async (e: React.FormEvent) => {
      e.preventDefault();
      if (!reason.trim()) {
        setError("Reason is required.");
        return;
      }
      setSubmitting(true);
      setError(null);
      try {
        await api.commands.killSwitchToggle(!armed, reason.trim());
        await onChanged();
        toast.success(armed ? "Kill switch disarmed" : "Kill switch armed (soft)");
        onClose();
      } catch (e: unknown) {
        const msg = e instanceof Error ? e.message : "Could not change state";
        setError(msg);
      } finally {
        setSubmitting(false);
      }
    },
    [armed, reason, onChanged, onClose]
  );

  return (
    <div
      data-mode="calm"
      role="dialog"
      aria-modal="true"
      aria-labelledby="hot-kill-switch-title"
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm p-4"
      onClick={(e) => {
        if (e.target === e.currentTarget) onClose();
      }}
    >
      <div className="w-full max-w-md rounded-md border-2 border-warn-500 bg-bg-panel shadow-xl">
        <header className="px-5 py-4 border-b border-border-subtle flex items-start justify-between gap-2">
          <div>
            <h2
              id="hot-kill-switch-title"
              className="text-[15px] font-semibold text-fg"
            >
              {armed ? "Disarm kill switch?" : "Arm soft kill switch?"}
            </h2>
            <p className="text-[12px] text-fg-muted mt-1">
              {armed
                ? "Trading will resume immediately for all profiles."
                : "All new orders will be blocked across all profiles. Existing positions remain open."}
            </p>
          </div>
          <button
            type="button"
            onClick={onClose}
            aria-label="Close"
            className="text-fg-muted hover:text-fg"
          >
            <X className="w-4 h-4" strokeWidth={1.5} aria-hidden />
          </button>
        </header>
        <form onSubmit={submit} className="px-5 py-4 flex flex-col gap-3">
          <label className="flex flex-col gap-1.5">
            <span className="text-[11px] uppercase tracking-wider text-fg-muted num-tabular">
              reason (required)
            </span>
            <Input
              ref={inputRef}
              value={reason}
              onChange={(e) => setReason(e.target.value)}
              placeholder="why are you doing this?"
              aria-label="Reason"
              autoComplete="off"
            />
          </label>
          {error && (
            <p className="text-[12px] text-danger-500" role="alert">
              {error}
            </p>
          )}
          <div className="flex items-center justify-end gap-2 pt-2">
            <Button
              type="button"
              intent="secondary"
              size="sm"
              onClick={onClose}
              disabled={submitting}
            >
              Cancel
            </Button>
            <Button
              type="submit"
              intent={armed ? "primary" : "danger"}
              size="sm"
              leftIcon={
                submitting ? (
                  <Loader2 className="w-3.5 h-3.5 animate-spin" aria-hidden />
                ) : armed ? (
                  <Unlock className="w-3.5 h-3.5" strokeWidth={1.5} />
                ) : (
                  <Lock className="w-3.5 h-3.5" strokeWidth={1.5} />
                )
              }
              disabled={submitting}
            >
              {armed ? "Disarm" : "Arm soft"}
            </Button>
          </div>
        </form>
      </div>
    </div>
  );
}

