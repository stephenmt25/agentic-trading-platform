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

interface PositionRow {
  symbol: string;
  side: "long" | "short";
  size: number;
  entry: number;
  mark: number;
  pnl: number;
  trend: number[];
}

const POSITIONS: PositionRow[] = [
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

  const columns: TableColumn<PositionRow>[] = [
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
