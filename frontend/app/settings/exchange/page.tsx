"use client";

import { useEffect, useState } from "react";
import { Plus, Trash2, KeyRound, AlertTriangle, ShieldCheck, RefreshCcw } from "lucide-react";
import { toast } from "sonner";
import { Button, Input, Select, type SelectOption, Toggle } from "@/components/primitives";
import { Pill } from "@/components/data-display";
import { api, type ExchangeKeyInfo } from "@/lib/api/client";
import { formatDateTime, formatRelative } from "../profiles/_lib/format";

const EXCHANGES: SelectOption[] = [
  { value: "binance", label: "Binance" },
  { value: "hyperliquid", label: "Hyperliquid" },
  { value: "coinbase", label: "Coinbase" },
  { value: "kraken", label: "Kraken" },
  { value: "bybit", label: "Bybit" },
];

interface AddState {
  exchange_id: string;
  label: string;
  api_key: string;
  api_secret: string;
  withdraw_acknowledged: boolean;
}

const INITIAL_ADD: AddState = {
  exchange_id: "binance",
  label: "",
  api_key: "",
  api_secret: "",
  withdraw_acknowledged: false,
};

function maskKey(id: string, exchange: string): string {
  const tail = id.slice(-4);
  const prefix = exchange.slice(0, 2).toLowerCase();
  return `${prefix}_••••••••${tail}`;
}

/**
 * /settings/exchange — exchange API keys. Per surface spec §4.
 *
 * Security copy is mandatory: Praxis never stores keys with withdraw
 * permissions enabled. The user must explicitly acknowledge before save.
 * Saved keys are masked and never re-displayed.
 */
export default function ExchangeSettingsPage() {
  const [keys, setKeys] = useState<ExchangeKeyInfo[] | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [add, setAdd] = useState<AddState>(INITIAL_ADD);
  const [testing, setTesting] = useState(false);
  const [saving, setSaving] = useState(false);
  const [deleting, setDeleting] = useState<string | null>(null);

  const load = async () => {
    setLoading(true);
    setError(null);
    try {
      const list = await api.exchangeKeys.list();
      setKeys(list);
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : "Failed to load keys";
      if (!msg.includes("Unauthorized")) {
        setError(msg);
      }
      setKeys([]);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
  }, []);

  const formValid =
    add.api_key.length > 0 &&
    add.api_secret.length > 0 &&
    add.withdraw_acknowledged;

  const handleTest = async () => {
    if (!add.api_key || !add.api_secret) {
      toast.error("Enter both the API key and secret first.");
      return;
    }
    setTesting(true);
    try {
      const result = await api.exchangeKeys.test({
        api_key: add.api_key,
        api_secret: add.api_secret,
        exchange_id: add.exchange_id,
      });
      if (result.status === "success") {
        toast.success(result.message || "Connection successful.");
      } else {
        toast.error(result.message || "Connection failed.");
      }
    } catch (e: unknown) {
      toast.error(e instanceof Error ? e.message : "Test failed.");
    } finally {
      setTesting(false);
    }
  };

  const handleSave = async () => {
    if (!formValid) return;
    setSaving(true);
    try {
      await api.exchangeKeys.store({
        exchange_id: add.exchange_id,
        api_key: add.api_key,
        api_secret: add.api_secret,
      });
      toast.success("Key saved.");
      setAdd(INITIAL_ADD);
      await load();
    } catch (e: unknown) {
      toast.error(e instanceof Error ? e.message : "Failed to save key.");
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = async (key: ExchangeKeyInfo) => {
    const ok = window.confirm(
      `Revoke ${key.label || key.exchange_name}? Live trading on this exchange will stop until a new key is saved.`
    );
    if (!ok) return;
    setDeleting(key.id);
    try {
      await api.exchangeKeys.delete(key.id);
      toast.success("Key revoked.");
      await load();
    } catch (e: unknown) {
      toast.error(e instanceof Error ? e.message : "Failed to revoke key.");
    } finally {
      setDeleting(null);
    }
  };

  return (
    <section className="flex flex-col gap-6">
      <header className="flex flex-col gap-1">
        <h1 className="text-[22px] font-semibold tracking-tight text-fg">
          Exchange keys
        </h1>
        <p className="text-fg-secondary">
          Connect a venue to enable live trading. Keys are stored encrypted at
          rest. Praxis only requires read + trade permissions; never enable
          withdraw on the exchange side.
        </p>
      </header>

      <div className="flex flex-col gap-3">
        <div className="flex items-center justify-between">
          <h2 className="text-[14px] font-semibold text-fg">Connected</h2>
          <Button
            intent="secondary"
            size="sm"
            leftIcon={<RefreshCcw className="w-3.5 h-3.5" />}
            onClick={load}
            disabled={loading}
          >
            Refresh
          </Button>
        </div>

        {error && (
          <div
            role="alert"
            className="rounded-md border border-danger-700/40 bg-danger-700/10 px-4 py-3 text-[13px] text-danger-500 flex items-start gap-3"
          >
            <AlertTriangle className="w-4 h-4 shrink-0 mt-0.5" strokeWidth={1.5} aria-hidden />
            <div className="flex-1">{error}</div>
            <Button intent="secondary" size="sm" onClick={load}>
              Retry
            </Button>
          </div>
        )}

        {loading && (
          <div className="rounded-md border border-border-subtle bg-bg-panel p-4 animate-pulse-subtle">
            <div className="h-4 w-48 bg-bg-raised rounded" />
            <div className="h-3 w-72 bg-bg-raised/60 rounded mt-2" />
          </div>
        )}

        {!loading && (keys?.length ?? 0) === 0 && (
          <div className="rounded-md border border-border-subtle bg-bg-panel/60 p-6 text-center">
            <p className="text-fg">No exchanges connected.</p>
            <p className="text-[13px] text-fg-muted mt-1">
              Add an exchange below to enable live trading.
            </p>
          </div>
        )}

        {!loading && (keys?.length ?? 0) > 0 && (
          <ul className="flex flex-col gap-2" role="list">
            {keys!.map((key) => (
              <li
                key={key.id}
                className="flex items-center justify-between gap-4 rounded-md border border-border-subtle bg-bg-panel px-4 py-3"
              >
                <div className="flex items-center gap-3 min-w-0">
                  <KeyRound className="w-4 h-4 text-fg-muted" strokeWidth={1.5} aria-hidden />
                  <div className="min-w-0">
                    <p className="text-[14px] text-fg truncate">
                      {key.label || key.exchange_name}
                    </p>
                    <p className="text-[12px] text-fg-muted font-mono">
                      {maskKey(key.id, key.exchange_name)}
                      <span className="mx-2 text-fg-muted/50">·</span>
                      Added {formatRelative(key.created_at)}
                    </p>
                  </div>
                </div>
                <div className="flex items-center gap-2 shrink-0">
                  {key.is_active ? (
                    <Pill intent="bid">Active</Pill>
                  ) : (
                    <Pill intent="neutral">Inactive</Pill>
                  )}
                  <Button
                    intent="secondary"
                    size="sm"
                    iconOnly
                    aria-label={`Revoke key ${key.label || key.exchange_name}`}
                    onClick={() => handleDelete(key)}
                    loading={deleting === key.id}
                  >
                    <Trash2 className="w-3.5 h-3.5" strokeWidth={1.5} aria-hidden />
                  </Button>
                </div>
              </li>
            ))}
          </ul>
        )}
      </div>

      <div className="rounded-lg border border-border-subtle bg-bg-panel p-5 flex flex-col gap-5">
        <div className="flex items-center gap-2">
          <Plus className="w-4 h-4 text-fg-muted" strokeWidth={1.5} aria-hidden />
          <h2 className="text-[14px] font-semibold text-fg">Add exchange</h2>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <Select
            label="Exchange"
            options={EXCHANGES}
            value={add.exchange_id}
            onValueChange={(v) => setAdd({ ...add, exchange_id: v })}
            density="comfortable"
          />
          <Input
            label="Label"
            density="comfortable"
            placeholder="Main account"
            value={add.label}
            onChange={(e) => setAdd({ ...add, label: e.target.value })}
            hint="Optional, helps you identify the key later."
          />
        </div>

        <Input
          label="API key"
          density="comfortable"
          mono
          placeholder="Paste from your exchange API page"
          value={add.api_key}
          onChange={(e) => setAdd({ ...add, api_key: e.target.value })}
          autoComplete="off"
          spellCheck={false}
        />
        <Input
          label="API secret"
          density="comfortable"
          mono
          type="password"
          placeholder="Paste from your exchange API page"
          value={add.api_secret}
          onChange={(e) => setAdd({ ...add, api_secret: e.target.value })}
          autoComplete="off"
          spellCheck={false}
        />

        <div className="rounded-md border border-warn-700/40 bg-warn-700/10 px-4 py-3 flex items-start gap-3">
          <ShieldCheck className="w-4 h-4 text-warn-400 shrink-0 mt-0.5" strokeWidth={1.5} aria-hidden />
          <div className="flex-1 text-[13px] text-warn-400/90">
            <p className="font-medium text-warn-400">Withdraw must be off.</p>
            <p className="mt-1 text-warn-400/70">
              Confirm the key has only <strong className="text-warn-400">Read</strong> and{" "}
              <strong className="text-warn-400">Trade</strong> permissions in your exchange API
              settings. Praxis rejects keys that prove withdraw-capable when tested.
            </p>
          </div>
        </div>

        <div className="flex items-center justify-between rounded-md border border-border-subtle bg-bg-canvas/40 px-4 py-3">
          <div className="text-[13px] text-fg-secondary pr-3">
            I have confirmed withdraw is disabled on this key.
          </div>
          <Toggle
            checked={add.withdraw_acknowledged}
            onCheckedChange={(next) =>
              setAdd({ ...add, withdraw_acknowledged: next })
            }
            label="Withdraw is disabled"
          />
        </div>

        <div className="flex flex-wrap gap-2 justify-end pt-2 border-t border-border-subtle">
          <Button
            intent="secondary"
            size="lg"
            onClick={handleTest}
            disabled={!add.api_key || !add.api_secret}
            loading={testing}
          >
            Test connection
          </Button>
          <Button
            intent="primary"
            size="lg"
            leftIcon={<KeyRound className="w-4 h-4" />}
            onClick={handleSave}
            disabled={!formValid}
            loading={saving}
          >
            Save key
          </Button>
        </div>
        <p className="text-[12px] text-fg-muted -mt-3">
          The secret is encrypted and never re-displayed. To rotate, revoke this
          key and add a new one.
        </p>
      </div>

      <p className="text-[12px] text-fg-muted">
        Keys can be inspected at{" "}
        <span className="font-mono">
          {formatDateTime(new Date().toISOString())}
        </span>
        ; secrets are write-only.
      </p>
    </section>
  );
}
