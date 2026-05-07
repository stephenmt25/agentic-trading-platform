"use client";

import { useState } from "react";
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

      {/* MODE-SCOPED PREVIEW */}
      <Section title="Mode preview (HOT vs. COOL vs. CALM)" tokens="data-mode resolves bg/fg/border aliases">
        <div className="grid grid-cols-3 gap-4">
          {(["hot", "cool", "calm"] as const).map((m) => (
            <div
              key={m}
              data-mode={m}
              className="rounded-md border border-border-subtle bg-bg-canvas p-4"
            >
              <p className="text-[11px] uppercase tracking-widest text-fg-muted mb-3 num-tabular">
                {m}
              </p>
              <div className="flex flex-col gap-2">
                <Button intent="primary" size="sm">
                  Primary
                </Button>
                <Button intent="secondary" size="sm">
                  Secondary
                </Button>
                <div className="text-sm text-fg">Foreground / primary</div>
                <div className="text-sm text-fg-secondary">Foreground / secondary</div>
                <div className="text-sm text-fg-muted">Foreground / muted</div>
              </div>
            </div>
          ))}
        </div>
      </Section>
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
