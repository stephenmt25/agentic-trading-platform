"use client";

import React, { useState, useEffect } from "react";
import { useSession } from "next-auth/react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Plus, ExternalLink, ShieldAlert, CheckCircle2, Loader2, KeyRound, Save, Trash2, RefreshCw, Bell, Globe, Clock } from "lucide-react";
import { toast } from "sonner";
import { api, type ExchangeKeyInfo } from "@/lib/api/client";

type SettingsTab = "exchange" | "security" | "preferences";

export default function SettingsPage() {
  const { data: session } = useSession();
  const [activeTab, setActiveTab] = useState<SettingsTab>("exchange");

  // Exchange keys state
  const [isTesting, setIsTesting] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const [apiKey, setApiKey] = useState("");
  const [apiSecret, setApiSecret] = useState("");
  const [connectedKeys, setConnectedKeys] = useState<ExchangeKeyInfo[]>([]);
  const [isLoading, setIsLoading] = useState(true);

  // Preferences state
  const [emailAlerts, setEmailAlerts] = useState(true);
  const [tradeNotifications, setTradeNotifications] = useState(true);
  const [defaultExchange, setDefaultExchange] = useState("binance");
  const [timezone, setTimezone] = useState(Intl.DateTimeFormat().resolvedOptions().timeZone);

  useEffect(() => {
    loadConnectedKeys();
  }, []);

  const loadConnectedKeys = async () => {
    setIsLoading(true);
    try {
      const keys = await api.exchangeKeys.list();
      setConnectedKeys(keys);
    } catch {
      setConnectedKeys([]);
    } finally {
      setIsLoading(false);
    }
  };

  const handleTestConnection = async () => {
    if (!apiKey || !apiSecret) {
      toast.error("Please enter both API Key and Secret.");
      return;
    }
    setIsTesting(true);
    try {
      const result = await api.exchangeKeys.test({
        api_key: apiKey,
        api_secret: apiSecret,
        exchange_id: "binance",
      });
      if (result.status === "success") {
        toast.success(result.message);
      } else {
        toast.error(result.message);
      }
    } catch (err) {
      toast.error((err as Error).message || "Connection test failed.");
    } finally {
      setIsTesting(false);
    }
  };

  const handleSaveKeys = async () => {
    if (!apiKey || !apiSecret) {
      toast.error("Please enter both API Key and Secret.");
      return;
    }
    setIsSaving(true);
    try {
      const result = await api.exchangeKeys.store({
        exchange_id: "binance",
        api_key: apiKey,
        api_secret: apiSecret,
      });
      toast.success(result.message);
      setApiKey("");
      setApiSecret("");
      await loadConnectedKeys();
    } catch (err) {
      toast.error((err as Error).message || "Failed to save keys.");
    } finally {
      setIsSaving(false);
    }
  };

  const handleDeleteKey = async (id: string) => {
    try {
      await api.exchangeKeys.delete(id);
      toast.success("Exchange key removed.");
      await loadConnectedKeys();
    } catch (err) {
      toast.error((err as Error).message || "Failed to delete key.");
    }
  };

  const [isSavingPrefs, setIsSavingPrefs] = useState(false);

  const handleSavePreferences = async () => {
    setIsSavingPrefs(true);
    try {
      await api.preferences.save({
        email_alerts: emailAlerts,
        trade_notifications: tradeNotifications,
        default_exchange: defaultExchange,
        timezone,
      });
      toast.success("Preferences saved!");
    } catch (err) {
      toast.error((err as Error).message || "Failed to save preferences.");
    } finally {
      setIsSavingPrefs(false);
    }
  };

  const tabs: { id: SettingsTab; label: string; icon: React.ReactNode }[] = [
    { id: "exchange", label: "Exchange Accounts", icon: <KeyRound className="w-4 h-4 mr-3" /> },
    { id: "security", label: "Security", icon: <ShieldAlert className="w-4 h-4 mr-3" /> },
    { id: "preferences", label: "Preferences", icon: <ExternalLink className="w-4 h-4 mr-3" /> },
  ];

  return (
    <div className="flex flex-col h-full gap-8 max-w-[1200px] mx-auto w-full">
      {/* Header */}
      <div className="flex items-center justify-between border-b border-border pb-4 shrink-0">
        <div>
          <h1 className="text-xl font-semibold tracking-tight text-foreground mb-1">Settings</h1>
          <p className="text-muted-foreground text-sm">Manage your account, API keys, and notification preferences.</p>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-4 gap-6 flex-1 items-start">
        {/* Settings Navigation Sidebar */}
        <div className="flex flex-col gap-1">
          {tabs.map((tab) => (
            <Button
              key={tab.id}
              variant={activeTab === tab.id ? "secondary" : "ghost"}
              className={`justify-start font-medium min-h-[44px] ${activeTab === tab.id ? "" : "text-muted-foreground hover:text-foreground"}`}
              onClick={() => setActiveTab(tab.id)}
            >
              {tab.icon}
              {tab.label}
            </Button>
          ))}
        </div>

        {/* Main Content Area */}
        <div className="md:col-span-3 flex flex-col gap-8">

          {/* ═══ EXCHANGE ACCOUNTS TAB ═══ */}
          {activeTab === "exchange" && (
            <>
              {/* Linked Accounts */}
              <section className="border border-border rounded-md">
                <div className="p-4 border-b border-border flex items-center justify-between">
                  <div>
                    <h3 className="text-lg font-medium text-foreground">Connected Exchanges</h3>
                    <p className="text-sm text-muted-foreground">Your active broker API connections.</p>
                  </div>
                  <Button size="sm" variant="ghost" className="text-muted-foreground hover:text-foreground min-h-[44px] min-w-[44px]" onClick={loadConnectedKeys} aria-label="Refresh exchange keys">
                    <RefreshCw className="w-4 h-4" />
                  </Button>
                </div>
                <div className="p-4">
                  {isLoading ? (
                    <div className="flex flex-col gap-2 p-4">
                      <div className="h-14 bg-accent animate-pulse rounded-md" />
                      <div className="h-14 bg-accent animate-pulse rounded-md" />
                    </div>
                  ) : connectedKeys.length === 0 ? (
                    <div className="flex flex-col items-center justify-center p-8 text-center">
                      <p className="text-foreground font-medium mb-1">No execution keys found</p>
                      <p className="text-sm text-muted-foreground max-w-sm">Connect a supported exchange to execute live trades or begin paper trading with real order books.</p>
                    </div>
                  ) : (
                    <div className="space-y-2">
                      {connectedKeys.map((key) => (
                        <div key={key.id} className="flex items-center justify-between p-3 border border-border rounded-md">
                          <div className="flex items-center gap-3">
                            <KeyRound className="w-4 h-4 text-muted-foreground" />
                            <div>
                              <p className="text-sm font-medium text-foreground">{key.label}</p>
                              <p className="text-xs text-muted-foreground font-mono uppercase">{key.exchange_name}</p>
                            </div>
                          </div>
                          <div className="flex items-center gap-3">
                            <Badge variant="outline" className={key.is_active ? "text-emerald-500 border-emerald-500/30" : "text-muted-foreground border-border"}>
                              {key.is_active ? "Active" : "Inactive"}
                            </Badge>
                            <Button size="sm" variant="ghost" className="text-red-500/50 hover:text-red-500 min-h-[44px] min-w-[44px]" onClick={() => handleDeleteKey(key.id)} aria-label="Delete exchange key">
                              <Trash2 className="w-4 h-4" />
                            </Button>
                          </div>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              </section>

              {/* Setup Form */}
              <section className="border border-border rounded-md">
                <div className="p-4 border-b border-border">
                  <h3 className="text-lg font-medium text-foreground flex items-center gap-2">
                    <Plus className="w-4 h-4" /> Connect Binance
                  </h3>
                  <p className="text-sm text-muted-foreground mt-1">
                    We only require <strong className="text-foreground">Read</strong> and <strong className="text-foreground">Trade</strong> permissions.
                    Keys with Withdrawal access will be automatically rejected.
                  </p>
                </div>
                <div className="p-4 space-y-4">
                  <div>
                    <label className="text-xs font-medium text-muted-foreground uppercase tracking-wider mb-1 block">API Key</label>
                    <Input type="text" placeholder="vmPUZE6mv9SD5VNHk4HlWJmN..." className="bg-background border-border font-mono text-foreground/80 placeholder:opacity-30 min-h-[44px]" value={apiKey} onChange={(e) => setApiKey(e.target.value)} />
                  </div>
                  <div>
                    <label className="text-xs font-medium text-muted-foreground uppercase tracking-wider mb-1 block">Secret Key</label>
                    <Input type="password" placeholder="------------------------" className="bg-background border-border font-mono text-foreground/80 placeholder:opacity-30 min-h-[44px]" value={apiSecret} onChange={(e) => setApiSecret(e.target.value)} />
                  </div>
                  <div className="flex flex-wrap items-center gap-3 pt-4 border-t border-border">
                    <Button onClick={handleTestConnection} disabled={isTesting} variant="outline" className="border-border text-foreground/80 hover:bg-accent min-h-[44px]">
                      {isTesting ? <><Loader2 className="w-4 h-4 mr-2 animate-spin" /> Testing...</> : "Test Connection"}
                    </Button>
                    <Button onClick={handleSaveKeys} disabled={isSaving || !apiKey || !apiSecret} className="bg-primary text-primary-foreground hover:bg-primary/90 min-h-[44px]">
                      {isSaving ? <><Loader2 className="w-4 h-4 mr-2 animate-spin" /> Saving...</> : <><Save className="w-4 h-4 mr-2" /> Save Keys</>}
                    </Button>
                  </div>
                </div>
              </section>
            </>
          )}

          {/* ═══ SECURITY TAB ═══ */}
          {activeTab === "security" && (
            <>
              {/* OAuth Provider */}
              <section className="border border-border rounded-md">
                <div className="p-4 border-b border-border">
                  <h3 className="text-lg font-medium text-foreground">Authentication</h3>
                  <p className="text-sm text-muted-foreground">Your sign-in method and session details.</p>
                </div>
                <div className="p-4">
                  <div className="flex items-center justify-between p-3 border border-border rounded-md">
                    <div className="flex items-center gap-3">
                      <CheckCircle2 className="w-4 h-4 text-emerald-500" />
                      <div>
                        <p className="text-sm font-medium text-foreground">
                          {session?.user?.provider === "github" ? "GitHub" : "Google"} OAuth
                        </p>
                        <p className="text-xs text-muted-foreground">{session?.user?.email || "Connected"}</p>
                      </div>
                    </div>
                    <span className="text-xs text-emerald-500 font-mono">Connected</span>
                  </div>
                </div>
              </section>

              {/* Session Info */}
              <section className="border border-border rounded-md">
                <div className="p-4 border-b border-border">
                  <h3 className="text-lg font-medium text-foreground">Active Session</h3>
                  <p className="text-sm text-muted-foreground">Details about your current browser session.</p>
                </div>
                <div className="p-4 space-y-0">
                  <div className="flex justify-between py-3 border-b border-border">
                    <span className="text-sm text-muted-foreground">Signed in as</span>
                    <span className="text-sm font-mono text-foreground">{session?.user?.name || "Unknown"}</span>
                  </div>
                  <div className="flex justify-between py-3 border-b border-border">
                    <span className="text-sm text-muted-foreground">Email</span>
                    <span className="text-sm font-mono text-foreground">{session?.user?.email || "--"}</span>
                  </div>
                  <div className="flex justify-between py-3 border-b border-border">
                    <span className="text-sm text-muted-foreground">Auth Provider</span>
                    <span className="text-sm font-mono text-foreground capitalize">{session?.user?.provider || "--"}</span>
                  </div>
                  <div className="flex justify-between py-3">
                    <span className="text-sm text-muted-foreground">Session Status</span>
                    <span className="text-xs text-emerald-500 font-mono">ACTIVE</span>
                  </div>
                </div>
              </section>

              {/* Security Notice */}
              <section className="border border-amber-500/20 rounded-md p-4">
                <div className="flex items-start gap-3">
                  <ShieldAlert className="w-4 h-4 text-amber-500 shrink-0 mt-0.5" />
                  <div>
                    <p className="text-sm font-medium text-amber-500 mb-1">Security Policy</p>
                    <p className="text-sm text-muted-foreground leading-relaxed">
                      All API keys are encrypted using Fernet symmetric encryption before storage. Keys with withdrawal permissions are automatically rejected. Sessions expire after 1 hour of inactivity.
                    </p>
                  </div>
                </div>
              </section>
            </>
          )}

          {/* ═══ PREFERENCES TAB ═══ */}
          {activeTab === "preferences" && (
            <>
              {/* Notifications */}
              <section className="border border-border rounded-md">
                <div className="p-4 border-b border-border">
                  <h3 className="text-lg font-medium text-foreground">Notifications</h3>
                  <p className="text-sm text-muted-foreground">Configure how you receive alerts.</p>
                </div>
                <div className="p-4 space-y-0">
                  <div className="flex items-center justify-between py-3 border-b border-border">
                    <div>
                      <p className="text-sm font-medium text-foreground">Email Alerts</p>
                      <p className="text-xs text-muted-foreground">Receive critical system alerts via email.</p>
                    </div>
                    <button
                      onClick={() => { setEmailAlerts(!emailAlerts); toast.success(emailAlerts ? "Email alerts disabled" : "Email alerts enabled"); }}
                      className={`relative w-11 h-6 rounded-full transition-colors min-w-[44px] min-h-[44px] flex items-center focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary ${emailAlerts ? "bg-primary" : "bg-accent"}`}
                      aria-label="Toggle email alerts"
                      role="switch"
                      aria-checked={emailAlerts}
                    >
                      <span className={`block w-4 h-4 rounded-full bg-white transition-transform absolute top-1/2 -translate-y-1/2 ${emailAlerts ? "translate-x-6" : "translate-x-1"}`} />
                    </button>
                  </div>
                  <div className="flex items-center justify-between py-3">
                    <div>
                      <p className="text-sm font-medium text-foreground">Trade Notifications</p>
                      <p className="text-xs text-muted-foreground">In-app alerts for every executed trade.</p>
                    </div>
                    <button
                      onClick={() => { setTradeNotifications(!tradeNotifications); toast.success(tradeNotifications ? "Trade notifications disabled" : "Trade notifications enabled"); }}
                      className={`relative w-11 h-6 rounded-full transition-colors min-w-[44px] min-h-[44px] flex items-center focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary ${tradeNotifications ? "bg-primary" : "bg-accent"}`}
                      aria-label="Toggle trade notifications"
                      role="switch"
                      aria-checked={tradeNotifications}
                    >
                      <span className={`block w-4 h-4 rounded-full bg-white transition-transform absolute top-1/2 -translate-y-1/2 ${tradeNotifications ? "translate-x-6" : "translate-x-1"}`} />
                    </button>
                  </div>
                </div>
              </section>

              {/* Trading Defaults */}
              <section className="border border-border rounded-md">
                <div className="p-4 border-b border-border">
                  <h3 className="text-lg font-medium text-foreground">Trading Defaults</h3>
                  <p className="text-sm text-muted-foreground">Default settings for new trading profiles.</p>
                </div>
                <div className="p-4 space-y-4">
                  <div>
                    <label className="text-xs font-medium text-muted-foreground uppercase tracking-wider mb-1.5 block">Default Exchange</label>
                    <select
                      value={defaultExchange}
                      onChange={(e) => setDefaultExchange(e.target.value)}
                      className="w-full bg-background border border-border rounded-md px-3 py-2 text-sm text-foreground focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary min-h-[44px]"
                    >
                      <option value="binance">Binance</option>
                      <option value="coinbase">Coinbase Pro</option>
                      <option value="kraken">Kraken</option>
                      <option value="bybit">Bybit</option>
                    </select>
                  </div>
                  <div>
                    <label className="text-xs font-medium text-muted-foreground uppercase tracking-wider mb-1.5 block">
                      Timezone
                    </label>
                    <Input
                      type="text"
                      value={timezone}
                      onChange={(e) => setTimezone(e.target.value)}
                      className="bg-background border-border text-foreground font-mono text-sm min-h-[44px]"
                    />
                    <p className="text-xs text-muted-foreground mt-1">Used for PnL reporting and trade timestamps.</p>
                  </div>
                  <div className="pt-2">
                    <Button onClick={handleSavePreferences} disabled={isSavingPrefs} className="bg-primary text-primary-foreground hover:bg-primary/90 font-medium min-h-[44px]">
                      {isSavingPrefs ? <><Loader2 className="w-4 h-4 mr-2 animate-spin" /> Saving...</> : <><Save className="w-4 h-4 mr-2" /> Save Preferences</>}
                    </Button>
                  </div>
                </div>
              </section>
            </>
          )}

        </div>
      </div>
    </div>
  );
}
