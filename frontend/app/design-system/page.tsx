"use client";

import { useEffect, useRef, useState } from "react";
import { Plus, Search, Eye, EyeOff } from "lucide-react";
import {
  Button,
  Input,
  Select,
  Toggle,
  Tag,
  Kbd,
  Tooltip,
  Avatar,
  type SelectOption,
} from "@/components/primitives";
import {
  Table,
  List,
  ListItem,
  KeyValue,
  Sparkline,
  Pill,
  StatusDot,
  type TableColumn,
  type SortDirection,
} from "@/components/data-display";
import {
  PnLBadge,
  PositionRow,
  TapeRow,
  RiskMeter,
  DepthChart,
  OrderBook,
  OrderEntryPanel,
  type DepthLevel,
  type OrderBookLevel,
} from "@/components/trading";
import {
  AgentAvatar,
  ConfidenceBar,
  ToolCall,
  ReasoningStream,
  AgentTrace,
  DebatePanel,
  AgentSummaryPanel,
  type AgentKind,
  type AgentTraceProps,
  type DebateContribution,
} from "@/components/agentic";
import {
  Node,
  Edge,
  NodePalette,
  MiniMap,
  NodeInspector,
  RunControlBar,
  type MiniMapNode,
} from "@/components/canvas";
import { AlertTriangle } from "lucide-react";

/**
 * /design-system — internal route exercising every primitive variant
 * across HOT / COOL / CALM modes. Not in the IA, not linked from the
 * left rail. Used during Phase 5–6 to catch visual regressions when
 * adding primitives or refactoring tokens.
 */
export default function DesignSystemPage() {
  const [text, setText] = useState("");
  const [errorText, setErrorText] = useState("not-an-email");
  const [selectVal, setSelectVal] = useState<string | undefined>("aggressive");
  const [searchableVal, setSearchableVal] = useState<string | undefined>();
  const [toggleA, setToggleA] = useState(false);
  const [toggleB, setToggleB] = useState(true);
  const [toggleArm, setToggleArm] = useState(false);
  const [tagDismissed, setTagDismissed] = useState(false);

  const profileOptions: SelectOption[] = [
    { value: "aggressive", label: "Aggressive-v3" },
    { value: "conservative", label: "Conservative-v1" },
    { value: "experimental", label: "Experimental-v0" },
    { value: "archived", label: "Archived-v0", disabled: true },
  ];

  const symbolOptions: SelectOption[] = [
    { value: "BTC-PERP", label: "BTC-PERP" },
    { value: "ETH-PERP", label: "ETH-PERP" },
    { value: "SOL-PERP", label: "SOL-PERP" },
    { value: "ARB-PERP", label: "ARB-PERP" },
    { value: "OP-PERP", label: "OP-PERP" },
    { value: "AVAX-PERP", label: "AVAX-PERP" },
  ];

  return (
    <div className="min-h-full px-8 py-10 max-w-5xl mx-auto">
      <header className="mb-10">
        <h1 className="text-2xl font-semibold tracking-tight text-fg">
          Praxis primitives
        </h1>
        <p className="text-sm text-fg-muted mt-1">
          Visual catalog for{" "}
          <code className="text-fg-secondary">frontend/components/primitives/</code>
          . Variants render in HOT mode by default; mode-scoped sections override
          via <code className="text-fg-secondary">data-mode</code>.
        </p>
      </header>

      {/* BUTTON */}
      <Section title="Button" tokens="--color-accent-{500,600,700}, --bg-panel, --bg-raised">
        <Row label="Intents (md)">
          <Button intent="primary">Primary</Button>
          <Button intent="secondary">Secondary</Button>
          <Button intent="danger">Danger</Button>
          <Button intent="bid">Buy</Button>
          <Button intent="ask">Sell</Button>
          <Button intent="secondary" disabled>
            Disabled
          </Button>
        </Row>
        <Row label="Sizes">
          <Button size="xs">xs</Button>
          <Button size="sm">sm</Button>
          <Button size="md">md</Button>
          <Button size="lg">lg</Button>
        </Row>
        <Row label="With icon / shortcut / loading">
          <Button leftIcon={<Plus className="w-3.5 h-3.5" strokeWidth={1.5} />}>
            New profile
          </Button>
          <Button intent="secondary" shortcut={<Kbd keys="mod+k" />}>
            Search
          </Button>
          <Button loading>Submitting</Button>
          <Button iconOnly aria-label="Toggle visibility" intent="secondary">
            <Eye className="w-4 h-4" strokeWidth={1.5} />
          </Button>
        </Row>
      </Section>

      {/* INPUT */}
      <Section title="Input" tokens="--bg-raised, --border-{subtle,strong}, --color-accent-500, --color-ask-500">
        <Row label="Default + label + hint">
          <div className="w-72">
            <Input
              label="API endpoint"
              value={text}
              onChange={(e) => setText(e.target.value)}
              placeholder="https://api.example.com"
              hint="Production endpoint without trailing slash"
            />
          </div>
        </Row>
        <Row label="Error state">
          <div className="w-72">
            <Input
              label="Email"
              value={errorText}
              onChange={(e) => setErrorText(e.target.value)}
              error={errorText.includes("@") ? undefined : "Must include @"}
            />
          </div>
        </Row>
        <Row label="Numeric + adornment + density">
          <div className="w-48">
            <Input
              label="Size"
              numeric
              defaultValue="0.0125"
              rightAdornment={<span className="text-xs">BTC</span>}
              density="compact"
            />
          </div>
          <div className="w-72">
            <Input
              label="API key"
              mono
              defaultValue="sk-praxis-3a92f4..."
              leftAdornment={<Search className="w-3.5 h-3.5" strokeWidth={1.5} />}
            />
          </div>
        </Row>
        <Row label="Disabled">
          <div className="w-72">
            <Input label="Read-only" defaultValue="locked" disabled />
          </div>
        </Row>
      </Section>

      {/* SELECT */}
      <Section title="Select" tokens="Input tokens + --shadow-popover, --bg-panel, --z-popover">
        <Row label="Single + label">
          <Select
            label="Active profile"
            options={profileOptions}
            value={selectVal}
            onValueChange={setSelectVal}
            className="w-56"
          />
        </Row>
        <Row label="Searchable">
          <Select
            label="Symbol"
            options={symbolOptions}
            value={searchableVal}
            onValueChange={setSearchableVal}
            placeholder="Pick a symbol…"
            searchable
            className="w-56"
          />
        </Row>
        <Row label="Disabled + density">
          <Select
            label="Locked"
            options={profileOptions}
            value="aggressive"
            disabled
            className="w-56"
          />
          <Select
            label="Compact"
            options={profileOptions}
            value="conservative"
            density="compact"
            className="w-56"
          />
        </Row>
      </Section>

      {/* TOGGLE */}
      <Section title="Toggle" tokens="--color-neutral-700, --color-accent-500, --color-bid-500, --color-danger-500">
        <Row label="Tones">
          <LabeledToggle label="Notifications">
            <Toggle checked={toggleA} onCheckedChange={setToggleA} label="Notifications" />
          </LabeledToggle>
          <LabeledToggle label="Opt in to live data">
            <Toggle
              checked={toggleB}
              onCheckedChange={setToggleB}
              tone="bid"
              label="Opt in to live data"
            />
          </LabeledToggle>
          <LabeledToggle label="Arm kill switch (soft)">
            <Toggle
              checked={toggleArm}
              onCheckedChange={setToggleArm}
              tone="danger"
              label="Arm kill switch"
            />
          </LabeledToggle>
        </Row>
        <Row label="Sizes / disabled">
          <Toggle checked={true} onCheckedChange={() => {}} size="sm" label="small" />
          <Toggle checked={true} onCheckedChange={() => {}} size="md" label="medium" />
          <Toggle checked={false} onCheckedChange={() => {}} disabled label="off disabled" />
          <Toggle checked={true} onCheckedChange={() => {}} disabled label="on disabled" />
        </Row>
      </Section>

      {/* TAG */}
      <Section title="Tag" tokens="intent colors at 100/200 (subtle bg) and 700/800 (subtle fg); 500 for solid">
        <Row label="Subtle (default)">
          <Tag intent="neutral">Neutral</Tag>
          <Tag intent="accent">Accent</Tag>
          <Tag intent="bid" dot>
            Bid
          </Tag>
          <Tag intent="ask" dot>
            Ask
          </Tag>
          <Tag intent="warn">Warn</Tag>
          <Tag intent="danger" dot>
            Danger
          </Tag>
          <Tag intent="agent">Agent</Tag>
        </Row>
        <Row label="Solid">
          <Tag intent="neutral" style="solid">
            Neutral
          </Tag>
          <Tag intent="accent" style="solid">
            Accent
          </Tag>
          <Tag intent="bid" style="solid">
            Bid
          </Tag>
          <Tag intent="ask" style="solid">
            Ask
          </Tag>
          <Tag intent="warn" style="solid">
            Warn
          </Tag>
          <Tag intent="danger" style="solid">
            Danger
          </Tag>
        </Row>
        <Row label="Dismissable">
          {!tagDismissed && (
            <Tag intent="accent" onDismiss={() => setTagDismissed(true)}>
              Filter: aggressive
            </Tag>
          )}
          {tagDismissed && (
            <Button size="xs" onClick={() => setTagDismissed(false)}>
              Reset
            </Button>
          )}
        </Row>
      </Section>

      {/* KBD */}
      <Section title="Kbd" tokens="--font-mono, --bg-raised, --border-subtle, --radius-xs">
        <Row label="Modifier-aware (Mac vs. Win/Linux)">
          <Kbd keys="mod+k" />
          <Kbd keys="shift+enter" />
          <Kbd keys="alt+ctrl+s" />
          <Kbd>Esc</Kbd>
          <Kbd>1</Kbd>
        </Row>
      </Section>

      {/* TOOLTIP */}
      <Section title="Tooltip" tokens="--bg-raised, scale.caption, --radius-sm, --duration-tick">
        <Row label="Hover or focus">
          <Tooltip content="Place market order">
            <Button intent="primary">Buy</Button>
          </Tooltip>
          <Tooltip content="Cancel all open orders" placement="bottom">
            <Button intent="secondary">Cancel all</Button>
          </Tooltip>
          <Tooltip
            content={
              <span className="inline-flex items-center gap-1.5">
                Toggle visibility <Kbd>V</Kbd>
              </span>
            }
            placement="right"
          >
            <Button iconOnly aria-label="Toggle visibility" intent="secondary">
              <EyeOff className="w-4 h-4" strokeWidth={1.5} />
            </Button>
          </Tooltip>
        </Row>
      </Section>

      {/* AVATAR */}
      <Section title="Avatar" tokens="--bg-raised, --border-subtle; agent ring uses --color-accent-500">
        <Row label="Kinds">
          <Avatar name="Wrench Thomas" />
          <Avatar
            name="Wrench Thomas"
            src="https://api.dicebear.com/9.x/initials/svg?seed=WT&backgroundColor=27272a"
          />
          <Avatar kind="agent" />
          <Avatar kind="system" />
        </Row>
        <Row label="Sizes + status">
          <Avatar size="sm" name="A B" />
          <Avatar size="md" name="C D" status="active" />
          <Avatar size="lg" name="E F" status="errored" />
          <Avatar size="md" kind="agent" status="idle" />
        </Row>
      </Section>

      {/* STATUS DOT */}
      <Section title="StatusDot" tokens="bg-{bid,ask,warn,danger,neutral}-{400,500}; pulse animation">
        <Row label="States (size 8)">
          <span className="inline-flex items-center gap-1.5 text-sm text-fg-secondary">
            <StatusDot state="live" pulse /> live (pulse)
          </span>
          <span className="inline-flex items-center gap-1.5 text-sm text-fg-secondary">
            <StatusDot state="idle" /> idle
          </span>
          <span className="inline-flex items-center gap-1.5 text-sm text-fg-secondary">
            <StatusDot state="warn" /> warn
          </span>
          <span className="inline-flex items-center gap-1.5 text-sm text-fg-secondary">
            <StatusDot state="error" /> error
          </span>
          <span className="inline-flex items-center gap-1.5 text-sm text-fg-secondary">
            <StatusDot state="armed" pulse /> armed (pulse)
          </span>
        </Row>
        <Row label="Sizes">
          <StatusDot state="live" size={6} pulse />
          <StatusDot state="live" size={8} pulse />
          <StatusDot state="live" size={10} pulse />
        </Row>
      </Section>

      {/* PILL */}
      <Section title="Pill" tokens="--radius-full, intent colors at subtle; active uses accent.500/15 bg + accent.300 fg">
        <Row label="Static (chrome)">
          <Pill icon={<StatusDot state="live" size={6} pulse />}>live</Pill>
          <Pill intent="warn" icon={<AlertTriangle className="w-3 h-3" strokeWidth={1.5} />}>
            regime: choppy
          </Pill>
          <Pill intent="neutral">
            <span className="num-tabular">12 ms</span>
          </Pill>
          <Pill intent="bid">
            <span className="num-tabular">+0.84%</span>
          </Pill>
        </Row>
        <Row label="Clickable">
          <PillToggleDemo />
        </Row>
        <Row label="Removable (filter chips)">
          <FilterChipDemo />
        </Row>
      </Section>

      {/* KEY VALUE */}
      <Section title="KeyValue" tokens="--fg-muted (label), --fg-primary (value); type scale.{label,body-dense}">
        <Row label="Inline + tones">
          <div className="w-72 flex flex-col gap-2 bg-bg-canvas border border-border-subtle rounded-md p-3">
            <KeyValue label="Equity" value="$42,318.27" />
            <KeyValue label="PnL (today)" value="+234.56 USDC" tone="bid" />
            <KeyValue label="Drawdown" value="-12.40 USDC" tone="ask" />
            <KeyValue label="Trades" value="42" />
            <KeyValue label="Win rate" value="58%" />
          </div>
        </Row>
        <Row label="Stacked + hint">
          <div className="flex gap-6 bg-bg-canvas border border-border-subtle rounded-md p-3">
            <KeyValue layout="stacked" label="Position size" value="0.0125 BTC" hint="≈ $812.50" />
            <KeyValue layout="stacked" label="Entry" value="$64,920" hint="2h ago" />
            <KeyValue layout="stacked" label="Target" value="$68,000" tone="bid" />
          </div>
        </Row>
      </Section>

      {/* SPARKLINE */}
      <Section title="Sparkline" tokens="stroke --color-bid-500 / --color-ask-500 / --color-neutral-400; auto trend detect">
        <Row label="Trend tones (auto-detect)">
          <Sparkline values={[100, 102, 99, 105, 108, 110, 112]} />
          <Sparkline values={[100, 96, 94, 98, 92, 90, 87]} />
          <Sparkline values={[100, 100.2, 99.8, 100.1, 99.9, 100.05]} tone="neutral" />
        </Row>
        <Row label="With area">
          <Sparkline area values={[100, 102, 99, 105, 108, 110, 112]} width={120} height={28} />
          <Sparkline area values={[100, 96, 94, 98, 92, 90, 87]} width={120} height={28} />
        </Row>
        <Row label="With midline">
          <Sparkline withMid values={[100, 105, 102, 108, 99, 110, 106]} width={120} height={28} />
        </Row>
      </Section>

      {/* LIST */}
      <Section title="List" tokens="--space-{1,2,3} (compact/standard/comfortable); --border-subtle (between)">
        <Row label="Interactive + dividers">
          <div className="w-80 bg-bg-canvas border border-border-subtle rounded-md p-2">
            <List dividers="between">
              <ListItem
                interactive
                withDividers
                leading={<Avatar size="sm" name="Aggressive v3" />}
                meta={<StatusDot state="live" pulse />}
              >
                Aggressive-v3
              </ListItem>
              <ListItem
                interactive
                withDividers
                leading={<Avatar size="sm" name="Conservative v1" />}
                meta="paused"
              >
                Conservative-v1
              </ListItem>
              <ListItem
                interactive
                withDividers
                leading={<Avatar size="sm" name="Experimental v0" />}
                meta="6d ago"
              >
                Experimental-v0
              </ListItem>
            </List>
          </div>
        </Row>
        <Row label="Dense static">
          <div className="w-80 bg-bg-canvas border border-border-subtle rounded-md p-2">
            <List spacing="compact">
              <ListItem dense meta="14 nodes">Aggressive-v3</ListItem>
              <ListItem dense meta="6 nodes">Conservative-v1</ListItem>
              <ListItem dense meta="9 nodes">Experimental-v0</ListItem>
            </List>
          </div>
        </Row>
      </Section>

      {/* TABLE */}
      <Section title="Table" tokens="--bg-{canvas,row-hover}, --border-subtle, sortable headers, tick-flash on update">
        <TableDemo />
      </Section>

      {/* ─── Trading-specific (Phase 5.3) ─────────────────────────────── */}
      <header className="mt-16 mb-8">
        <h2 className="text-lg font-semibold text-fg">Trading-specific</h2>
        <p className="text-sm text-fg-muted mt-1">
          Domain components from{" "}
          <code className="text-fg-secondary">
            frontend/components/trading/
          </code>
          . Per spec, these compose primitives + data-display and are HOT-mode
          first. OrderEntryPanel and OrderBook are critical-path.
        </p>
      </header>

      {/* PnL BADGE */}
      <Section
        title="PnLBadge"
        tokens="--color-bid-{400,500,tick-flash}, --color-ask-{400,500,tick-flash}, --font-tabular"
      >
        <Row label="Modes (inline)">
          <PnLBadge value={234.56} mode="absolute" currency="USDC" />
          <PnLBadge value={-134.4} mode="absolute" currency="USDC" />
          <PnLBadge value={2.34} mode="pct" />
          <PnLBadge value={-0.42} mode="pct" />
          <PnLBadge value={45} mode="bps" />
          <PnLBadge value={1.2} mode="r-multiple" />
          <PnLBadge value={0} mode="absolute" currency="USDC" />
        </Row>
        <Row label="Prominent (chrome)">
          <PnLBadge value={1234.56} size="prominent" mode="absolute" currency="USDC" />
          <PnLBadge value={-487.2} size="prominent" mode="absolute" currency="USDC" />
          <PnLBadge value={4.32} size="prominent" mode="pct" />
        </Row>
        <Row label="Flash on change (click to tick)">
          <FlashingPnLDemo />
        </Row>
      </Section>

      {/* TAPE ROW */}
      <Section
        title="TapeRow"
        tokens="--color-{bid,ask}-500/10% (row tint), --font-mono, --space-{1,2}"
      >
        <Row label="Streaming feed sample">
          <div className="w-80 bg-bg-canvas border border-border-subtle rounded-md overflow-hidden">
            {SAMPLE_TAPE.map((t, i) => (
              <TapeRow
                key={i}
                side={t.side}
                time={t.time}
                size={t.size}
                price={t.price}
                largePrint={t.largePrint}
                sizeDigits={4}
                priceDigits={2}
              />
            ))}
          </div>
        </Row>
      </Section>

      {/* POSITION ROW */}
      <Section
        title="PositionRow"
        tokens="Table tokens + bid/ask + warn/danger; 2-click confirm only modal-equivalent in HOT"
      >
        <Row label="Default + states">
          <div className="w-full bg-bg-canvas border border-border-subtle rounded-md overflow-x-auto">
            <PositionRow
              symbol="BTC-PERP"
              side="long"
              size={0.0125}
              entry={64920}
              mark={65310}
              unrealized={487.5}
              margin={42.32}
              leverage={5}
              onClosePartial={() => {}}
              onEditStop={() => {}}
              onTraceCanvas={() => {}}
            />
            <PositionRow
              symbol="ETH-PERP"
              side="long"
              size={0.42}
              entry={3120}
              mark={3088}
              unrealized={-134.4}
              margin={62.84}
              leverage={3}
              onClosePartial={() => {}}
              onEditStop={() => {}}
            />
            <PositionRow
              symbol="SOL-PERP"
              side="short"
              size={12.0}
              entry={145.2}
              mark={158.7}
              unrealized={-162.0}
              margin={75.0}
              leverage={10}
              state="near-liq"
              onClosePartial={() => {}}
            />
            <PositionRow
              symbol="ARB-PERP"
              side="long"
              size={850}
              entry={0.812}
              mark={0.598}
              unrealized={-181.9}
              margin={45.0}
              leverage={20}
              state="liquidating"
              onClosePartial={() => {}}
            />
          </div>
        </Row>
      </Section>

      {/* RISK METER */}
      <Section
        title="RiskMeter"
        tokens="--color-bid-500/30, --color-warn-500/30, --color-danger-500/30, segment dividers --border-strong"
      >
        <Row label="By kind (full)">
          <div className="w-72">
            <RiskMeter kind="leverage" value={3.2} max={10} />
          </div>
          <div className="w-72">
            <RiskMeter kind="portfolio-var" value={68} max={100} />
          </div>
          <div className="w-72">
            <RiskMeter kind="drawdown" value={92} max={100} />
          </div>
        </Row>
        <Row label="Compact (no thresholds)">
          <div className="w-48">
            <RiskMeter kind="concentration" value={45} max={100} compact />
          </div>
          <div className="w-48">
            <RiskMeter kind="concentration" value={72} max={100} compact />
          </div>
          <div className="w-48">
            <RiskMeter kind="concentration" value={95} max={100} compact />
          </div>
        </Row>
      </Section>

      {/* DEPTH CHART */}
      <Section
        title="DepthChart"
        tokens="strokes --color-{bid,ask}-500, fills 22%→4% gradient, mid --color-neutral-400 dotted; NO gridlines per spec"
      >
        <Row label="Linear, ±0.5%">
          <div className="bg-bg-canvas border border-border-subtle rounded-md p-3">
            <DepthChart
              bids={SAMPLE_DEPTH_BIDS}
              asks={SAMPLE_DEPTH_ASKS}
              width={360}
              height={140}
              range={0.005}
              showMidLabel
            />
          </div>
        </Row>
        <Row label="Wider zoom, fit">
          <div className="bg-bg-canvas border border-border-subtle rounded-md p-3">
            <DepthChart
              bids={SAMPLE_DEPTH_BIDS}
              asks={SAMPLE_DEPTH_ASKS}
              width={360}
              height={140}
              range="fit"
            />
          </div>
        </Row>
      </Section>

      {/* ORDER BOOK */}
      <Section
        title="OrderBook (critical-path)"
        tokens="bid/ask 12% cumulative-fill; mid badge neutral or warn.500 when wide; ARIA grid"
      >
        <Row label="Split style (default)">
          <div className="w-[420px]">
            <OrderBook
              bids={SAMPLE_BOOK_BIDS}
              asks={SAMPLE_BOOK_ASKS}
              wideSpreadBps={50}
            />
          </div>
        </Row>
        <Row label="Stacked style">
          <div className="w-[320px]">
            <OrderBook
              bids={SAMPLE_BOOK_BIDS}
              asks={SAMPLE_BOOK_ASKS}
              style="stacked"
              wideSpreadBps={50}
            />
          </div>
        </Row>
      </Section>

      {/* ORDER ENTRY */}
      <Section
        title="OrderEntryPanel (critical-path)"
        tokens="submit adopts side color (bid/ask); kill-switch state shows danger banner"
      >
        <Row label="Buy / limit (default)">
          <div className="w-80">
            <OrderEntryPanel
              symbol="BTC-PERP"
              midPrice={42318.27}
              defaultSide="buy"
              defaultOrderType="limit"
              defaultSize="0.005"
              defaultPrice="42318.27"
              estimatedCost={211.59}
              estimatedMargin={42.32}
              availableSize={0.05}
            />
          </div>
        </Row>
        <Row label="Sell / market">
          <div className="w-80">
            <OrderEntryPanel
              symbol="ETH-PERP"
              midPrice={3088}
              defaultSide="sell"
              defaultOrderType="market"
              defaultSize="0.42"
              estimatedCost={1296.96}
              estimatedMargin={129.7}
              availableSize={1.0}
            />
          </div>
        </Row>
        <Row label="Risk-block / Kill-switch states">
          <div className="w-80">
            <OrderEntryPanel
              symbol="BTC-PERP"
              midPrice={42318.27}
              defaultSide="buy"
              defaultOrderType="limit"
              defaultSize="2.5"
              defaultPrice="42318.27"
              state="risk-block"
              riskBlockReason="Would exceed max position size of 1.0 BTC"
              availableSize={0.05}
            />
          </div>
          <div className="w-80">
            <OrderEntryPanel
              symbol="BTC-PERP"
              midPrice={42318.27}
              defaultSide="buy"
              defaultOrderType="limit"
              defaultSize="0.005"
              defaultPrice="42318.27"
              state="kill-switch-armed"
              availableSize={0.05}
            />
          </div>
        </Row>
      </Section>

      {/* ─── Agentic (Phase 5.4) ───────────────────────────────────── */}
      <header className="mt-16 mb-8">
        <h2 className="text-lg font-semibold text-fg">Agentic</h2>
        <p className="text-sm text-fg-muted mt-1">
          Domain components from{" "}
          <code className="text-fg-secondary">
            frontend/components/agentic/
          </code>
          . Per ADR-012 all six agent identities alias to accent — visual
          differentiation is by glyph + label + position only. Trace bodies
          stay neutral so multiple traces coexist on screen without becoming
          a Christmas tree.
        </p>
      </header>

      {/* AGENT AVATAR */}
      <Section
        title="AgentAvatar"
        tokens="--color-agent-{ta,regime,sentiment,slm,debate,analyst} (all alias to --color-accent-500 per ADR-012)"
      >
        <Row label="Six agent glyphs (md)">
          {(["ta", "regime", "sentiment", "slm", "debate", "analyst"] as const).map(
            (k) => (
              <AgentAvatar key={k} kind={k} size="md" withName="below" />
            )
          )}
        </Row>
        <Row label="Sizes">
          <AgentAvatar kind="ta" size="sm" />
          <AgentAvatar kind="ta" size="md" />
          <AgentAvatar kind="ta" size="lg" />
        </Row>
        <Row label="With status dots">
          <AgentAvatar kind="ta" status="live" />
          <AgentAvatar kind="regime" status="idle" />
          <AgentAvatar kind="sentiment" status="errored" />
          <AgentAvatar kind="slm" status="silenced" />
        </Row>
        <Row label="With name (inline)">
          <AgentAvatar kind="debate" status="live" withName />
          <AgentAvatar kind="analyst" status="idle" withName />
        </Row>
      </Section>

      {/* CONFIDENCE BAR */}
      <Section
        title="ConfidenceBar"
        tokens="bid/neutral/ask for direction outputs; accent shades for multi-modal regime outputs (ADR-012)"
      >
        <Row label="Direction (long/neutral/short)">
          <div className="w-80">
            <ConfidenceBar
              title="Direction prediction"
              subtitle="ta_agent · 14:32:01"
              segments={[
                { label: "long", probability: 0.62, tone: "bid" },
                { label: "neutral", probability: 0.18, tone: "neutral" },
                { label: "short", probability: 0.2, tone: "ask" },
              ]}
            />
          </div>
        </Row>
        <Row label="Regime (3 accent shades)">
          <div className="w-80">
            <ConfidenceBar
              title="Regime distribution"
              subtitle="regime_hmm · 14:32:01"
              segments={[
                { label: "trending", probability: 0.18, tone: "accent-weak" },
                { label: "choppy", probability: 0.71, tone: "accent" },
                { label: "reversal", probability: 0.11, tone: "accent-strong" },
              ]}
            />
          </div>
        </Row>
        <Row label="Compact (legend below)">
          <div className="w-80">
            <ConfidenceBar
              density="compact"
              segments={[
                { label: "long", probability: 0.45, tone: "bid" },
                { label: "neutral", probability: 0.3, tone: "neutral" },
                { label: "short", probability: 0.25, tone: "ask" },
              ]}
            />
          </div>
        </Row>
        <Row label="With historic (1h ago, faded backdrop)">
          <div className="w-80">
            <ConfidenceBar
              title="Direction (with historic backdrop)"
              segments={[
                { label: "long", probability: 0.62, tone: "bid" },
                { label: "neutral", probability: 0.18, tone: "neutral" },
                { label: "short", probability: 0.2, tone: "ask" },
              ]}
              historic={[
                { label: "long", probability: 0.4, tone: "bid" },
                { label: "neutral", probability: 0.35, tone: "neutral" },
                { label: "short", probability: 0.25, tone: "ask" },
              ]}
            />
          </div>
        </Row>
      </Section>

      {/* TOOL CALL */}
      <Section
        title="ToolCall"
        tokens="--bg-raised, scale.caption mono, --color-bid-500 (success), --color-ask-500 (error)"
      >
        <Row label="States">
          <div className="w-96 flex flex-col gap-2">
            <ToolCall
              toolName="query_market_data"
              status="complete"
              durationMs={23}
              args={{ symbol: "BTC-PERP", lookback: "1h" }}
              result={{ rows: 3600, latest: 42318.27 }}
              defaultCollapsed={false}
            />
            <ToolCall
              toolName="run_strategy_eval"
              status="pending"
              args={{
                profile: "aggressive-v3",
                features: ["rsi", "macd", "atr"],
              }}
            />
            <ToolCall
              toolName="commit_order"
              status="errored"
              durationMs={812}
              args={{ side: "buy", size: 0.005, type: "limit" }}
              error="ValidationError: order size below minimum (0.001)"
              defaultCollapsed={false}
            />
          </div>
        </Row>
      </Section>

      {/* REASONING STREAM */}
      <Section
        title="ReasoningStream"
        tokens="scale.body-dense, --font-sans (prose) / --font-mono (json), cursor --color-accent-500"
      >
        <Row label="Streaming demo (live cursor)">
          <StreamingDemo />
        </Row>
        <Row label="JSON mode (done)">
          <div className="w-96">
            <ReasoningStream
              mode="json"
              state="done"
              meta="0.4s · 47 tokens · sonnet-4-6"
              content={`{
  "regime": "choppy",
  "p_trending": 0.18,
  "p_choppy": 0.71,
  "p_reversal": 0.11,
  "decision_horizon_s": 30
}`}
            />
          </div>
        </Row>
        <Row label="With thinking (xml-tags)">
          <div className="w-[28rem]">
            <ReasoningStream
              mode="xml-tags"
              state="done"
              content={`<thinking>
The 1m candles show 240 bars; 2-state HMM converged at iter 7.
Probability of choppy at 0.71 vs trending 0.18 vs reversal 0.11.
</thinking>

regime: choppy
p(trending)=0.18  p(choppy)=0.71  p(reversal)=0.11`}
              meta="1.1s · 312 tokens · sonnet-4-6"
            />
          </div>
        </Row>
        <Row label="Inline (Hot Trading Cmd+K result)">
          <ReasoningStream
            inline
            state="streaming"
            content="checking liquidity at the 42,300 level"
          />
        </Row>
        <Row label="Errored">
          <div className="w-96">
            <ReasoningStream
              state="errored"
              content={"...the model timed out before"}
              error="LLM gateway timeout after 8s — retry or fall back to cached"
            />
          </div>
        </Row>
      </Section>

      {/* AGENT TRACE */}
      <Section
        title="AgentTrace"
        tokens="--color-accent-500 (avatar ring + section header underline); body neutral"
      >
        <Row label="Standard density (default)">
          <div className="w-[34rem]">
            <AgentTrace
              agent="regime"
              emittedAt={Date.UTC(2026, 4, 7, 14, 32, 1, 234)}
              state="complete"
              input={
                <span className="font-mono text-[11px]">
                  candles: BTC-PERP 1m × 240 · features: returns, rv
                </span>
              }
              reasoning={
                <span className="font-mono text-[11px] text-fg-muted">
                  ▸ probability shift detected: trending → choppy
                </span>
              }
              output={
                <span className="font-mono text-[11px]">
                  regime: choppy · p(trending)=0.18 · p(choppy)=0.71 ·
                  p(reversal)=0.11
                </span>
              }
              downstream={[
                { label: "strategy_eval (canvas node #4)" },
                { label: "debate (next round)" },
              ]}
              linkable
            />
          </div>
        </Row>
        <Row label="Streaming + Errored states">
          <div className="w-[34rem] flex flex-col gap-2">
            <AgentTrace
              agent="ta"
              emittedAt={Date.UTC(2026, 4, 7, 14, 32, 5, 12)}
              state="streaming"
              input={<span className="font-mono text-[11px]">… reading</span>}
              output={
                <span className="font-mono text-[11px]">
                  trend: up · momentum: positive · confidence: 0.62
                </span>
              }
            />
            <AgentTrace
              agent="slm"
              emittedAt={Date.UTC(2026, 4, 7, 14, 32, 9, 482)}
              state="errored"
              input={
                <span className="font-mono text-[11px]">
                  prompt: classify_market_state @ 1m
                </span>
              }
              output={null}
              error="LLM gateway timeout after 8s"
            />
          </div>
        </Row>
        <Row label="Compact density (Hot Trading inline)">
          <div className="w-[34rem]">
            <AgentTrace
              agent="sentiment"
              emittedAt={Date.UTC(2026, 4, 7, 14, 31, 58, 901)}
              state="complete"
              density="compact"
              output={
                <span className="font-mono text-[11px]">
                  sentiment: +0.32 (weak) · sources: 1,422 · novelty: 0.04
                </span>
              }
            />
          </div>
        </Row>
      </Section>

      {/* DEBATE PANEL */}
      <Section
        title="DebatePanel"
        tokens="stance colors: for=bid.400, against=ask.400, neutral=neutral.400, synthesis=accent.300"
      >
        <Row label="Live debate (round 3/5)">
          <div className="w-[40rem]">
            <DebatePanel
              topic="should we open BTC-PERP long now?"
              round={3}
              totalRounds={5}
              state="live"
              decisionDelaySec={3}
              contributions={SAMPLE_DEBATE}
              onOpenRound={() => {}}
              onPause={() => {}}
              onOverride={() => {}}
            />
          </div>
        </Row>
        <Row label="Embedded (compact for Hot Trading)">
          <div className="w-80">
            <DebatePanel
              topic="should we open BTC-PERP long now?"
              round={3}
              totalRounds={5}
              state="live"
              embedded
              decisionDelaySec={3}
              contributions={SAMPLE_DEBATE}
              onOverride={() => {}}
            />
          </div>
        </Row>
      </Section>

      {/* AGENT SUMMARY PANEL */}
      <Section
        title="AgentSummaryPanel"
        tokens="composite — composes AgentTrace (compact) + embedded DebatePanel; ≤300px tall"
      >
        <Row label="Default (3 traces + 1 debate)">
          <div className="w-[28rem]">
            <AgentSummaryPanel
              traces={SAMPLE_RECENT_TRACES}
              debate={{
                topic: "BTC-PERP long?",
                round: 3,
                totalRounds: 5,
                state: "live",
                contributions: SAMPLE_DEBATE.slice(0, 3),
                interventionEnabled: false,
              }}
              onSeeAll={() => {}}
            />
          </div>
        </Row>
        <Row label="Empty">
          <div className="w-80">
            <AgentSummaryPanel
              traces={[]}
              state="empty"
              onSeeAll={() => {}}
            />
          </div>
        </Row>
        <Row label="Service degraded">
          <div className="w-80">
            <AgentSummaryPanel
              traces={[]}
              state="service-degraded"
              degradedSinceText="3m ago"
              onSeeAll={() => {}}
            />
          </div>
        </Row>
      </Section>

      {/* ─── Canvas (Phase 5.5) ────────────────────────────────────── */}
      <header className="mt-16 mb-8">
        <h2 className="text-lg font-semibold text-fg">Canvas</h2>
        <p className="text-sm text-fg-muted mt-1">
          Pipeline-canvas components from{" "}
          <code className="text-fg-secondary">
            frontend/components/canvas/
          </code>
          . Per ADR-003 the canvas is the source of truth for trading
          profiles — these components are the editor, not just a
          visualization. All nodes are rectangles per spec; kind is
          differentiated by icon + color accent + content, never by shape.
        </p>
      </header>

      {/* NODE */}
      <Section
        title="Node"
        tokens="--bg-panel, kind-specific border tints; running uses agent identity (collapses to accent per ADR-012)"
      >
        <Row label="Kinds (medium, idle)">
          <Node
            title="ta_agent"
            kind="agent"
            agent="ta"
            inputSummary="candles 1m × 240"
            outputSummary="signal {long|short|hold}"
            stats="idle · last 23ms"
          />
          <Node
            title="ingestion"
            kind="data-source"
            inputSummary="—"
            outputSummary="market_data stream"
            stats="streaming · 48 msg/s"
          />
          <Node
            title="strategy_eval"
            kind="decision"
            inputSummary="signals × 3"
            outputSummary="order intent"
            stats="idle"
          />
          <Node
            title="execution"
            kind="sink"
            sinkSide="bid"
            inputSummary="order intent"
            outputSummary="—"
            stats="0 in flight"
          />
          <Node
            title="ta_indicator"
            kind="transform"
            inputSummary="candles"
            outputSummary="rsi/ema/atr"
            stats="42ms last"
          />
        </Row>
        <Row label="States">
          <Node
            title="ta_agent"
            kind="agent"
            agent="ta"
            state="running"
            inputSummary="candles 1m × 240"
            outputSummary="signal {long|short|hold}"
            stats="running · 23ms · 1.2k qps"
          />
          <Node
            title="regime_hmm"
            kind="agent"
            agent="regime"
            state="paused"
            inputSummary="candles 1m × 240"
            outputSummary="regime {trending|choppy|reversal}"
            stats="paused"
          />
          <Node
            title="slm_inference"
            kind="agent"
            agent="slm"
            state="errored"
            inputSummary="prompt"
            outputSummary="—"
            lastError="LLM gateway timeout after 8s"
          />
          <Node
            title="strategy_eval"
            kind="decision"
            state="selected"
            inputSummary="signals × 3"
            outputSummary="order intent"
            stats="selected"
            onInfoClick={() => {}}
            onMenuClick={() => {}}
          />
        </Row>
        <Row label="Sizes">
          <Node title="ta_agent" kind="agent" agent="ta" size="small" />
          <Node
            title="ta_agent"
            kind="agent"
            agent="ta"
            size="medium"
            inputSummary="candles 1m × 240"
            outputSummary="signal {long|short|hold}"
            stats="running · 23ms"
            state="running"
          />
        </Row>
      </Section>

      {/* EDGE */}
      <Section
        title="Edge"
        tokens="bezier curve only (NO orthogonal); 1.5px stroke; agent edges in accent at ~60% sat per ADR-012"
      >
        <Row label="States and kinds (live mode = animated dot)">
          <svg
            width={520}
            height={180}
            className="bg-bg-canvas rounded-md border border-border-subtle"
            aria-label="Edge variants demo"
          >
            {/* Static endpoint markers */}
            {[
              { x: 60, y: 30 },
              { x: 60, y: 80 },
              { x: 60, y: 130 },
              { x: 460, y: 30 },
              { x: 460, y: 80 },
              { x: 460, y: 130 },
            ].map((p, i) => (
              <circle
                key={i}
                cx={p.x}
                cy={p.y}
                r={3}
                fill="var(--color-neutral-700)"
              />
            ))}
            <Edge
              source={{ x: 60, y: 30 }}
              target={{ x: 460, y: 30 }}
              kind="agent"
              flowing
            />
            <Edge
              source={{ x: 60, y: 80 }}
              target={{ x: 460, y: 80 }}
              kind="data"
              flowing
            />
            <Edge
              source={{ x: 60, y: 130 }}
              target={{ x: 460, y: 130 }}
              kind="decision"
              state="selected"
              flowing
            />
          </svg>
        </Row>
        <Row label="Errored / inactive-branch (no flow)">
          <svg
            width={520}
            height={120}
            className="bg-bg-canvas rounded-md border border-border-subtle"
            aria-label="Edge state demo"
          >
            <Edge
              source={{ x: 60, y: 40 }}
              target={{ x: 460, y: 40 }}
              kind="agent"
              state="errored"
            />
            <Edge
              source={{ x: 60, y: 90 }}
              target={{ x: 460, y: 90 }}
              kind="data"
              state="inactive-branch"
            />
          </svg>
        </Row>
      </Section>

      {/* NODE PALETTE */}
      <Section
        title="NodePalette"
        tokens="--bg-panel, search via Input primitive, fixed registry order"
      >
        <Row label="Default registry">
          <div className="w-72 h-[420px]">
            <NodePalette
              onEntryClick={() => {}}
              onEntryDragStart={() => {}}
            />
          </div>
        </Row>
      </Section>

      {/* MINIMAP */}
      <Section
        title="MiniMap"
        tokens="160×120; --color-accent-500 at 8% (viewport rect); off-screen running/errored nodes pulse"
      >
        <Row label="Sample layout (drag the indigo rect)">
          <div className="bg-bg-canvas border border-border-subtle rounded-md p-3 inline-block">
            <MiniMapDemo />
          </div>
        </Row>
        <Row label="Collapsed (chevron only)">
          <MiniMap
            nodes={[]}
            viewport={{ x: 0, y: 0, width: 100, height: 100 }}
            defaultCollapsed
          />
        </Row>
      </Section>

      {/* NODE INSPECTOR */}
      <Section
        title="NodeInspector"
        tokens="380px right drawer; collapsible sections; primitive form controls"
      >
        <Row label="Static demo (drawer pinned in place)">
          <div className="h-[520px] flex bg-bg-canvas border border-border-subtle rounded-md overflow-hidden">
            <div className="flex-1 p-6 text-fg-muted text-sm flex items-start justify-center">
              <span>
                ← Inspector pinned to the right. In real Pipeline Canvas
                use, this slides over the canvas without dimming it.
              </span>
            </div>
            <NodeInspector
              open
              nodeTitle="regime_hmm"
              nodeKind="agent"
              running
              onTitleChange={() => {}}
              onRunningChange={() => {}}
              inputs={[
                {
                  id: "candles",
                  label: "candles",
                  connection: "ingestion → BTC-PERP 1m",
                },
              ]}
              outputs={[
                {
                  id: "regime",
                  label: "regime",
                  connection: "→ strategy_eval (canvas #4)",
                },
                {
                  id: "regime",
                  label: "regime",
                  connection: "→ debate (round 4)",
                },
              ]}
              configuration={
                <>
                  <Input label="Lookback bars" defaultValue="240" numeric />
                  <Input label="Hidden states" defaultValue="3" numeric />
                  <Input
                    label="EM iterations"
                    defaultValue="20"
                    numeric
                    density="compact"
                  />
                </>
              }
              liveActivity={
                <KeyValue
                  label="last 100 emissions"
                  value="p̄(choppy) = 0.68"
                />
              }
              onOpenObservatory={() => {}}
              tests={
                <p className="text-[12px] text-fg-muted">
                  Sample-input runner — wire up in Phase 6.3.
                </p>
              }
              onClose={() => {}}
            />
          </div>
        </Row>
      </Section>

      {/* RUN CONTROL BAR */}
      <Section
        title="RunControlBar"
        tokens="--color-bid-500 (paper-active), --color-accent-500 (live primary), warn (dirty)"
      >
        <Row label="Idle, saved">
          <div className="w-full">
            <RunControlBar
              profileOptions={[
                { value: "agg-v3", label: "Aggressive-v3" },
                { value: "cons-v1", label: "Conservative-v1" },
              ]}
              activeProfileId="agg-v3"
              savedAtText="saved 3m ago"
              onRunPaper={() => {}}
              onRunLive={() => {}}
              onRunBacktest={() => {}}
            />
          </div>
        </Row>
        <Row label="Dirty (unsaved)">
          <div className="w-full">
            <RunControlBar
              profileOptions={[{ value: "agg-v3", label: "Aggressive-v3" }]}
              activeProfileId="agg-v3"
              dirty
              onSave={() => {}}
              onRunPaper={() => {}}
              onRunLive={() => {}}
              onRunBacktest={() => {}}
            />
          </div>
        </Row>
        <Row label="Paper running">
          <div className="w-full">
            <RunControlBar
              profileOptions={[{ value: "agg-v3", label: "Aggressive-v3" }]}
              activeProfileId="agg-v3"
              activity="paper-active"
              savedAtText="saved 3m ago"
              onRunPaper={() => {}}
              onRunLive={() => {}}
              onRunBacktest={() => {}}
            />
          </div>
        </Row>
        <Row label="Backtest in progress">
          <div className="w-full">
            <RunControlBar
              profileOptions={[{ value: "agg-v3", label: "Aggressive-v3" }]}
              activeProfileId="agg-v3"
              activity="backtesting-active"
              savedAtText="saved 3m ago"
              onRunPaper={() => {}}
              onRunLive={() => {}}
              onRunBacktest={() => {}}
              onCancelBacktest={() => {}}
            />
          </div>
        </Row>
      </Section>

      {/* MODE-SCOPED PREVIEW */}
      <Section
        title="Mode preview (HOT vs. COOL vs. CALM)"
        tokens="data-mode resolves --bg-canvas / --bg-panel / --bg-raised / --fg-* aliases"
      >
        <p className="text-xs text-fg-muted mb-4 leading-relaxed">
          Surface colors are intentionally close between modes. The bigger
          differentiators per <code className="text-fg-secondary">01-design-philosophy.md</code> §2
          are <strong className="text-fg">density</strong> (font sizes,
          row heights) and <strong className="text-fg">motion budget</strong>{" "}
          (≤180ms HOT, ≤220ms COOL, ≤320ms CALM). The introspection rows below
          show the actual computed CSS values per mode — that&apos;s where the
          color shifts are.
        </p>
        <div className="grid grid-cols-3 gap-4">
          {(["hot", "cool", "calm"] as const).map((m) => (
            <ModePreviewBlock key={m} mode={m} />
          ))}
        </div>
      </Section>
    </div>
  );
}

/** Renders one mode block + introspects the resolved CSS variables so the
 *  reader can SEE that data-mode actually re-scopes them, even when the
 *  on-screen difference is intentionally subtle. */
function ModePreviewBlock({ mode }: { mode: "hot" | "cool" | "calm" }) {
  const ref = useRef<HTMLDivElement>(null);
  const [resolved, setResolved] = useState<Record<string, string> | null>(null);

  useEffect(() => {
    if (!ref.current) return;
    const styles = getComputedStyle(ref.current);
    const get = (name: string) => styles.getPropertyValue(name).trim() || "—";
    setResolved({
      "--bg-canvas": get("--bg-canvas"),
      "--bg-panel": get("--bg-panel"),
      "--bg-raised": get("--bg-raised"),
      "--fg-primary": get("--fg-primary"),
      "--fg-secondary": get("--fg-secondary"),
      "--fg-muted": get("--fg-muted"),
      "--motion-default": get("--motion-default"),
    });
  }, [mode]);

  // Per philosophy §2: HOT 12–13px, COOL 13–14px, CALM 14–15px.
  const bodySize =
    mode === "hot" ? "text-[13px]" : mode === "cool" ? "text-[14px]" : "text-[15px]";
  const rowHeight =
    mode === "hot" ? "h-7" : mode === "cool" ? "h-9" : "h-11";

  return (
    <div
      ref={ref}
      data-mode={mode}
      className="rounded-md border border-border-subtle bg-bg-canvas p-4 flex flex-col gap-3"
    >
      <div className="flex items-center justify-between">
        <p className="text-[11px] uppercase tracking-widest text-fg-muted num-tabular">
          {mode}
        </p>
        <Tag intent={mode === "hot" ? "ask" : mode === "cool" ? "accent" : "neutral"} style="subtle">
          {mode === "hot" ? "cockpit" : mode === "cool" ? "laboratory" : "office"}
        </Tag>
      </div>

      {/* Surface swatches — three steps */}
      <div className="flex gap-1">
        <div className="flex-1 h-6 rounded-sm bg-bg-canvas border border-border-subtle" title="bg-canvas" />
        <div className="flex-1 h-6 rounded-sm bg-bg-panel border border-border-subtle" title="bg-panel" />
        <div className="flex-1 h-6 rounded-sm bg-bg-raised border border-border-subtle" title="bg-raised" />
      </div>

      {/* Density sample */}
      <div className="rounded-sm border border-border-subtle bg-bg-panel">
        <div className={`${rowHeight} ${bodySize} flex items-center px-2 border-b border-border-subtle text-fg`}>
          <span className="num-tabular">42,318.27</span>
        </div>
        <div className={`${rowHeight} ${bodySize} flex items-center px-2 border-b border-border-subtle text-fg-secondary`}>
          <span className="num-tabular">38,002.44</span>
        </div>
        <div className={`${rowHeight} ${bodySize} flex items-center px-2 text-fg-muted`}>
          <span className="num-tabular">36,114.10</span>
        </div>
      </div>

      <div className="flex flex-col gap-2">
        <Button intent="primary" size="sm">Primary</Button>
        <Button intent="secondary" size="sm">Secondary</Button>
      </div>

      {/* Resolved CSS variable introspection */}
      <div className="rounded-sm bg-bg-panel border border-border-subtle p-2">
        <p className="text-[10px] uppercase tracking-widest text-fg-muted mb-1 num-tabular">
          Resolved
        </p>
        {resolved ? (
          <ul className="text-[10px] font-mono num-tabular flex flex-col gap-0.5 text-fg-secondary">
            {Object.entries(resolved).map(([k, v]) => (
              <li key={k} className="flex items-center justify-between gap-2">
                <span className="text-fg-muted truncate">{k}</span>
                <span className="text-fg">{v}</span>
              </li>
            ))}
          </ul>
        ) : (
          <p className="text-[10px] text-fg-muted">Computing…</p>
        )}
      </div>
    </div>
  );
}

function Section({
  title,
  tokens,
  children,
}: {
  title: string;
  tokens?: string;
  children: React.ReactNode;
}) {
  return (
    <section className="mb-10">
      <h2 className="text-[11px] font-semibold uppercase tracking-widest text-fg-muted mb-3 num-tabular">
        {title}
      </h2>
      {tokens && (
        <p className="text-[11px] text-fg-muted mb-4 font-mono num-tabular">
          {tokens}
        </p>
      )}
      <div className="rounded-md border border-border-subtle bg-bg-panel p-5 flex flex-col gap-4">
        {children}
      </div>
    </section>
  );
}

function Row({
  label,
  children,
}: {
  label: string;
  children: React.ReactNode;
}) {
  return (
    <div className="flex flex-wrap items-center gap-3">
      <span className="text-[11px] uppercase tracking-wider text-fg-muted w-40 shrink-0 num-tabular">
        {label}
      </span>
      <div className="flex flex-wrap items-center gap-3">{children}</div>
    </div>
  );
}

function LabeledToggle({
  label,
  children,
}: {
  label: string;
  children: React.ReactNode;
}) {
  return (
    <span className="inline-flex items-center gap-2 text-sm text-fg-secondary">
      {children}
      <span>{label}</span>
    </span>
  );
}

function PillToggleDemo() {
  const [active, setActive] = useState<"all" | "active" | "paused">("active");
  return (
    <>
      {(["all", "active", "paused"] as const).map((k) => (
        <Pill
          key={k}
          as="clickable"
          intent="neutral"
          active={active === k}
          onClick={() => setActive(k)}
        >
          {k}
        </Pill>
      ))}
    </>
  );
}

function FilterChipDemo() {
  const [chips, setChips] = useState<string[]>(["regime: choppy", "BTC-PERP", "open"]);
  if (chips.length === 0) {
    return (
      <Button size="xs" onClick={() => setChips(["regime: choppy", "BTC-PERP", "open"])}>
        Reset
      </Button>
    );
  }
  return (
    <>
      {chips.map((c) => (
        <Pill
          key={c}
          as="removable"
          intent="accent"
          onRemove={() => setChips((s) => s.filter((x) => x !== c))}
        >
          {c}
        </Pill>
      ))}
    </>
  );
}

const STREAM_FULL = `Examining the 1m candles for BTC-PERP. Recent
240 bars show declining realized vol (12.4 → 7.8 over last 30
minutes), with returns clustering tightly around zero — classic
ranging behavior.

Probability shift detected: trending → **choppy**.

\`\`\`
p(trending) = 0.18
p(choppy)   = 0.71
p(reversal) = 0.11
\`\`\`

Recommend reducing trend-follower position size by 0.4× until
volatility resumes.`;

const MINIMAP_NODES: MiniMapNode[] = [
  { id: "ing", x: 40, y: 40, width: 120, height: 60, kind: "data-source", state: "running" },
  { id: "ta", x: 220, y: 20, width: 120, height: 60, kind: "agent", state: "running" },
  { id: "rg", x: 220, y: 100, width: 120, height: 60, kind: "agent", state: "paused" },
  { id: "se", x: 220, y: 180, width: 120, height: 60, kind: "agent", state: "errored" },
  { id: "st", x: 400, y: 100, width: 120, height: 60, kind: "decision", state: "selected" },
  { id: "ex", x: 580, y: 100, width: 120, height: 60, kind: "sink", state: "idle" },
  { id: "lg", x: 580, y: 200, width: 120, height: 60, kind: "sink", state: "idle" },
  // Off-screen running node — should pulse on the minimap
  { id: "off", x: 900, y: 400, width: 120, height: 60, kind: "agent", state: "running" },
];

function MiniMapDemo() {
  const [vp, setVp] = useState({ x: 0, y: 0 });
  return (
    <MiniMap
      nodes={MINIMAP_NODES}
      viewport={{ x: vp.x, y: vp.y, width: 360, height: 220 }}
      onViewportChange={setVp}
    />
  );
}

function StreamingDemo() {
  const [text, setText] = useState("");
  const [running, setRunning] = useState(false);
  useEffect(() => {
    if (!running) return;
    let i = text.length;
    const id = window.setInterval(() => {
      i = Math.min(STREAM_FULL.length, i + 4);
      setText(STREAM_FULL.slice(0, i));
      if (i >= STREAM_FULL.length) {
        window.clearInterval(id);
        setRunning(false);
      }
    }, 30);
    return () => window.clearInterval(id);
  }, [running]);

  const reset = () => {
    setText("");
    setRunning(true);
  };

  const state =
    !running && text.length === 0
      ? "done"
      : running
        ? "streaming"
        : "done";

  return (
    <span className="inline-flex items-center gap-3 w-[34rem]">
      <div className="flex-1">
        <ReasoningStream
          mode="prose"
          state={state}
          content={text}
          maxHeight={180}
          meta={
            state === "done" && text.length > 0
              ? `${(STREAM_FULL.length / 60).toFixed(1)}s · ${Math.round(STREAM_FULL.length / 4)} tokens · sonnet-4-6`
              : undefined
          }
        />
      </div>
      <Button size="xs" intent="primary" onClick={reset} disabled={running}>
        replay
      </Button>
    </span>
  );
}

const SAMPLE_DEBATE: DebateContribution[] = [
  {
    id: "ta",
    agent: "ta",
    stance: "for",
    summary: "trend confirmed on 1h, momentum positive",
    confidence: 0.71,
  },
  {
    id: "regime",
    agent: "regime",
    stance: "against",
    summary: "regime is choppy; trend signals are unreliable here",
    confidence: 0.71,
  },
  {
    id: "sentiment",
    agent: "sentiment",
    stance: "for",
    summary: "social sentiment +0.32, but volume thin",
    confidence: 0.32,
  },
  {
    id: "synth",
    agent: "debate",
    agentNameOverride: "orchestrator",
    stance: "synthesis",
    summary: "0.62 confidence in long; suggest reduced size (0.4x)",
    confidence: 0.62,
  },
];

const SAMPLE_RECENT_TRACES: AgentTraceProps[] = [
  {
    agent: "regime" as AgentKind,
    emittedAt: Date.UTC(2026, 4, 7, 14, 32, 1, 234),
    state: "complete",
    output: (
      <span className="font-mono text-[11px]">
        regime: choppy · p=0.71
      </span>
    ),
  },
  {
    agent: "ta" as AgentKind,
    emittedAt: Date.UTC(2026, 4, 7, 14, 31, 55, 12),
    state: "complete",
    output: (
      <span className="font-mono text-[11px]">
        trend: up · momentum: +0.42
      </span>
    ),
  },
  {
    agent: "sentiment" as AgentKind,
    emittedAt: Date.UTC(2026, 4, 7, 14, 31, 32, 901),
    state: "complete",
    output: (
      <span className="font-mono text-[11px]">
        sentiment: +0.32 (weak)
      </span>
    ),
  },
];

function FlashingPnLDemo() {
  const [val, setVal] = useState(123.45);
  return (
    <span className="inline-flex items-center gap-3">
      <PnLBadge value={val} mode="absolute" currency="USDC" flashOnChange />
      <Button
        size="xs"
        intent="bid"
        onClick={() => setVal((v) => v + Math.random() * 10)}
      >
        tick up
      </Button>
      <Button
        size="xs"
        intent="ask"
        onClick={() => setVal((v) => v - Math.random() * 10)}
      >
        tick down
      </Button>
    </span>
  );
}

const NOW = Date.UTC(2026, 4, 7, 14, 32, 18, 412);
const SAMPLE_TAPE: Array<{
  side: "bid" | "ask";
  time: number;
  size: number;
  price: number;
  largePrint?: boolean;
}> = [
  { side: "bid", time: NOW + 0, size: 0.0125, price: 42318.27 },
  { side: "ask", time: NOW - 240, size: 0.0042, price: 42319.5 },
  { side: "bid", time: NOW - 510, size: 0.211, price: 42317.0, largePrint: true },
  { side: "ask", time: NOW - 814, size: 0.0182, price: 42320.25 },
  { side: "bid", time: NOW - 1102, size: 0.005, price: 42316.8 },
  { side: "ask", time: NOW - 1380, size: 0.0934, price: 42321.75, largePrint: true },
  { side: "bid", time: NOW - 1650, size: 0.0094, price: 42315.0 },
];

const SAMPLE_DEPTH_BIDS: DepthLevel[] = [
  { price: 42318.27, size: 0.5 },
  { price: 42317.5, size: 1.2 },
  { price: 42316.0, size: 0.8 },
  { price: 42314.0, size: 2.5 },
  { price: 42310.0, size: 4.1 },
  { price: 42305.0, size: 5.2 },
  { price: 42298.0, size: 6.8 },
  { price: 42290.0, size: 9.0 },
];

const SAMPLE_DEPTH_ASKS: DepthLevel[] = [
  { price: 42319.0, size: 0.4 },
  { price: 42320.5, size: 0.9 },
  { price: 42322.0, size: 1.1 },
  { price: 42325.0, size: 2.0 },
  { price: 42330.0, size: 3.5 },
  { price: 42338.0, size: 4.7 },
  { price: 42345.0, size: 6.2 },
  { price: 42355.0, size: 8.1 },
];

const SAMPLE_BOOK_BIDS: OrderBookLevel[] = [
  { price: 42318.27, size: 0.5 },
  { price: 42317.5, size: 1.2 },
  { price: 42316.0, size: 0.8 },
  { price: 42314.0, size: 2.5 },
  { price: 42310.0, size: 4.1 },
  { price: 42305.0, size: 5.2 },
  { price: 42298.0, size: 6.8 },
];

const SAMPLE_BOOK_ASKS: OrderBookLevel[] = [
  { price: 42319.0, size: 0.4 },
  { price: 42320.5, size: 0.9 },
  { price: 42322.0, size: 1.1 },
  { price: 42325.0, size: 2.0 },
  { price: 42330.0, size: 3.5 },
  { price: 42338.0, size: 4.7 },
  { price: 42345.0, size: 6.2 },
];

interface TablePositionRow {
  symbol: string;
  side: "long" | "short";
  size: number;
  entry: number;
  mark: number;
  pnl: number;
  trend: number[];
}

const POSITIONS: TablePositionRow[] = [
  { symbol: "BTC-PERP", side: "long", size: 0.0125, entry: 64920, mark: 65310, pnl: 487.5, trend: [100, 102, 99, 105, 108, 110, 112] },
  { symbol: "ETH-PERP", side: "long", size: 0.42, entry: 3120, mark: 3088, pnl: -134.4, trend: [100, 96, 94, 98, 92, 90, 87] },
  { symbol: "SOL-PERP", side: "short", size: 12.0, entry: 145.2, mark: 142.7, pnl: 30.0, trend: [100, 100.2, 99.8, 100.1, 99.9, 100.05] },
  { symbol: "ARB-PERP", side: "long", size: 850, entry: 0.812, mark: 0.798, pnl: -11.9, trend: [100, 99, 98, 97, 96, 95, 94] },
];

function TableDemo() {
  const [sortKey, setSortKey] = useState<string | undefined>("pnl");
  const [sortDir, setSortDir] = useState<SortDirection>("desc");
  const [selected, setSelected] = useState<string | null>("BTC-PERP");
  const [density, setDensity] = useState<"compact" | "standard" | "comfortable">("standard");

  const sortedData = [...POSITIONS].sort((a, b) => {
    if (!sortKey) return 0;
    const av = (a as Record<string, unknown>)[sortKey];
    const bv = (b as Record<string, unknown>)[sortKey];
    if (typeof av === "number" && typeof bv === "number") {
      return sortDir === "asc" ? av - bv : bv - av;
    }
    return sortDir === "asc"
      ? String(av).localeCompare(String(bv))
      : String(bv).localeCompare(String(av));
  });

  const columns: TableColumn<TablePositionRow>[] = [
    { key: "symbol", header: "Symbol", sortable: true },
    {
      key: "side",
      header: "Side",
      sortable: true,
      render: (row) => (
        <Tag intent={row.side === "long" ? "bid" : "ask"} style="subtle">
          {row.side}
        </Tag>
      ),
    },
    {
      key: "size",
      header: "Size",
      numeric: true,
      sortable: true,
      render: (row) => row.size.toFixed(4),
    },
    {
      key: "entry",
      header: "Entry",
      numeric: true,
      sortable: true,
      render: (row) => `$${row.entry.toLocaleString()}`,
    },
    {
      key: "mark",
      header: "Mark",
      numeric: true,
      sortable: true,
      render: (row) => `$${row.mark.toLocaleString()}`,
    },
    {
      key: "pnl",
      header: "PnL",
      numeric: true,
      sortable: true,
      render: (row) => (
        <span className={row.pnl >= 0 ? "text-bid-400" : "text-ask-500"}>
          {row.pnl >= 0 ? "+" : ""}
          {row.pnl.toFixed(2)}
        </span>
      ),
    },
    {
      key: "trend",
      header: "7d",
      align: "right",
      render: (row) => <Sparkline values={row.trend} width={64} height={16} />,
    },
  ];

  return (
    <div className="flex flex-col gap-3">
      <div className="flex items-center gap-2">
        <span className="text-[11px] text-fg-muted uppercase tracking-wider num-tabular">
          density
        </span>
        {(["compact", "standard", "comfortable"] as const).map((d) => (
          <Pill
            key={d}
            as="clickable"
            intent="neutral"
            active={density === d}
            onClick={() => setDensity(d)}
          >
            {d}
          </Pill>
        ))}
      </div>
      <div className="rounded-md border border-border-subtle overflow-hidden">
        <Table
          data={sortedData}
          columns={columns}
          rowKey={(r) => r.symbol}
          density={density}
          sortKey={sortKey}
          sortDirection={sortDir}
          onSortChange={(k, d) => {
            setSortKey(k);
            setSortDir(d);
          }}
          selectable="single"
          selectedRowKey={selected}
          onRowSelect={(r) => setSelected(r.symbol)}
        />
      </div>
    </div>
  );
}
