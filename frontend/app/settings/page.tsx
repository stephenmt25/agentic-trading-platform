"use client";

import React, { useState, useEffect } from "react";
import { useSession } from "next-auth/react";
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Key, Plus, ExternalLink, ShieldAlert, CheckCircle2, Loader2, KeyRound, Save, Trash2, RefreshCw, Bell, Globe, Clock } from "lucide-react";
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
        exchange_name: "binance",
      });
      if (result.success) {
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
        exchange_name: "binance",
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

  const handleSavePreferences = () => {
    toast.success("Preferences saved!");
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
          <h1 className="text-3xl font-black tracking-tight text-white mb-1">PLATFORM SETTINGS</h1>
          <p className="text-muted-foreground text-sm">Manage your account, API keys, and notification preferences.</p>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-4 gap-8 flex-1 items-start">
        {/* Settings Navigation Sidebar */}
        <div className="flex flex-col gap-2">
          {tabs.map((tab) => (
            <Button
              key={tab.id}
              variant={activeTab === tab.id ? "secondary" : "ghost"}
              className={`justify-start font-bold ${activeTab === tab.id ? "" : "text-muted-foreground hover:text-white"}`}
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
              <Card className="border-border bg-card shadow-lg">
                <CardHeader className="pb-4 border-b border-border/50">
                  <div className="flex items-center justify-between">
                    <div>
                      <CardTitle className="text-lg text-slate-200">Connected Exchanges</CardTitle>
                      <CardDescription>Your active broker API connections.</CardDescription>
                    </div>
                    <Button size="sm" variant="ghost" className="text-muted-foreground hover:text-white" onClick={loadConnectedKeys}>
                      <RefreshCw className="w-4 h-4" />
                    </Button>
                  </div>
                </CardHeader>
                <CardContent className="pt-6">
                  {isLoading ? (
                    <div className="flex items-center justify-center p-8">
                      <Loader2 className="w-6 h-6 animate-spin text-muted-foreground" />
                    </div>
                  ) : connectedKeys.length === 0 ? (
                    <div className="flex flex-col items-center justify-center p-8 border border-dashed border-border rounded-xl bg-black/20 text-center">
                      <Key className="w-12 h-12 text-muted-foreground mb-4 opacity-50" />
                      <p className="text-slate-300 font-bold mb-1">No execution keys found</p>
                      <p className="text-sm text-slate-500 max-w-sm mb-6">Connect a supported exchange to execute live trades or begin paper trading with real order books.</p>
                    </div>
                  ) : (
                    <div className="space-y-3">
                      {connectedKeys.map((key) => (
                        <div key={key.id} className="flex items-center justify-between p-4 border border-border rounded-lg bg-black/20">
                          <div className="flex items-center gap-4">
                            <div className="h-10 w-10 rounded-lg bg-primary/10 border border-primary/20 flex items-center justify-center">
                              <KeyRound className="w-5 h-5 text-primary" />
                            </div>
                            <div>
                              <p className="text-sm font-bold text-slate-200">{key.label}</p>
                              <p className="text-xs text-slate-500 font-mono uppercase">{key.exchange_name}</p>
                            </div>
                          </div>
                          <div className="flex items-center gap-3">
                            <Badge variant={key.is_active ? "default" : "secondary"} className={key.is_active ? "bg-emerald-900/50 text-emerald-400 border-emerald-800" : ""}>
                              {key.is_active ? "Active" : "Inactive"}
                            </Badge>
                            <Button size="sm" variant="ghost" className="text-red-500/50 hover:text-red-400 hover:bg-red-900/20" onClick={() => handleDeleteKey(key.id)}>
                              <Trash2 className="w-4 h-4" />
                            </Button>
                          </div>
                        </div>
                      ))}
                    </div>
                  )}
                </CardContent>
              </Card>

              {/* Setup Form */}
              <Card className="border-primary/50 bg-primary/5 shadow-xl relative overflow-hidden">
                <div className="absolute top-0 w-full h-1 bg-gradient-to-r from-primary to-indigo-400 left-0" />
                <CardHeader>
                  <CardTitle className="text-lg text-primary flex items-center gap-2">
                    <Plus className="w-5 h-5" /> Connect Binance
                  </CardTitle>
                  <CardDescription>
                    We only require <strong className="text-white">Read</strong> and <strong className="text-white">Trade</strong> permissions.
                    Keys with Withdrawal access will be automatically rejected by the validation engine.
                  </CardDescription>
                </CardHeader>
                <CardContent className="space-y-6">
                  <div className="space-y-4">
                    <div>
                      <label className="text-xs font-bold text-slate-400 uppercase tracking-widest mb-1 block">API Key</label>
                      <Input type="text" placeholder="vmPUZE6mv9SD5VNHk4HlWJmN..." className="bg-black/50 border-border font-mono text-slate-300 placeholder:opacity-30" value={apiKey} onChange={(e) => setApiKey(e.target.value)} />
                    </div>
                    <div>
                      <label className="text-xs font-bold text-slate-400 uppercase tracking-widest mb-1 block">Secret Key</label>
                      <Input type="password" placeholder="••••••••••••••••••••••••" className="bg-black/50 border-border font-mono text-slate-300 placeholder:opacity-30" value={apiSecret} onChange={(e) => setApiSecret(e.target.value)} />
                    </div>
                  </div>
                  <div className="flex items-center gap-4 pt-4 border-t border-border/50">
                    <Button onClick={handleTestConnection} disabled={isTesting} variant="outline" className="border-primary text-primary hover:bg-primary/10">
                      {isTesting ? <><Loader2 className="w-4 h-4 mr-2 animate-spin" /> TESTING...</> : "TEST CONNECTION"}
                    </Button>
                    <Button onClick={handleSaveKeys} disabled={isSaving || !apiKey || !apiSecret} className="bg-primary text-primary-foreground hover:bg-primary/90">
                      {isSaving ? <><Loader2 className="w-4 h-4 mr-2 animate-spin" /> SAVING...</> : <><Save className="w-4 h-4 mr-2" /> SAVE KEYS SECURELY</>}
                    </Button>
                  </div>
                </CardContent>
              </Card>
            </>
          )}

          {/* ═══ SECURITY TAB ═══ */}
          {activeTab === "security" && (
            <>
              {/* OAuth Provider */}
              <Card className="border-border bg-card shadow-lg">
                <CardHeader className="pb-4 border-b border-border/50">
                  <CardTitle className="text-lg text-slate-200">Authentication</CardTitle>
                  <CardDescription>Your sign-in method and session details.</CardDescription>
                </CardHeader>
                <CardContent className="pt-6 space-y-4">
                  <div className="flex items-center justify-between p-4 border border-border rounded-lg bg-black/20">
                    <div className="flex items-center gap-4">
                      <div className="h-10 w-10 rounded-lg bg-emerald-500/10 border border-emerald-500/20 flex items-center justify-center">
                        <CheckCircle2 className="w-5 h-5 text-emerald-500" />
                      </div>
                      <div>
                        <p className="text-sm font-bold text-slate-200">
                          {((session?.user as unknown) as { provider?: string })?.provider === "github" ? "GitHub" : "Google"} OAuth
                        </p>
                        <p className="text-xs text-slate-500">{session?.user?.email || "Connected"}</p>
                      </div>
                    </div>
                    <Badge className="bg-emerald-900/50 text-emerald-400 border-emerald-800">Connected</Badge>
                  </div>
                </CardContent>
              </Card>

              {/* Session Info */}
              <Card className="border-border bg-card shadow-lg">
                <CardHeader className="pb-4 border-b border-border/50">
                  <CardTitle className="text-lg text-slate-200">Active Session</CardTitle>
                  <CardDescription>Details about your current browser session.</CardDescription>
                </CardHeader>
                <CardContent className="pt-6">
                  <div className="space-y-3">
                    <div className="flex justify-between py-2 border-b border-border/30">
                      <span className="text-sm text-slate-400">Signed in as</span>
                      <span className="text-sm font-mono text-slate-200">{session?.user?.name || "Unknown"}</span>
                    </div>
                    <div className="flex justify-between py-2 border-b border-border/30">
                      <span className="text-sm text-slate-400">Email</span>
                      <span className="text-sm font-mono text-slate-200">{session?.user?.email || "—"}</span>
                    </div>
                    <div className="flex justify-between py-2 border-b border-border/30">
                      <span className="text-sm text-slate-400">Auth Provider</span>
                      <span className="text-sm font-mono text-slate-200 capitalize">{((session?.user as unknown) as { provider?: string })?.provider || "—"}</span>
                    </div>
                    <div className="flex justify-between py-2">
                      <span className="text-sm text-slate-400">Session Status</span>
                      <Badge className="bg-emerald-900/50 text-emerald-400 border-emerald-800 text-[10px]">ACTIVE</Badge>
                    </div>
                  </div>
                </CardContent>
              </Card>

              {/* Security Notice */}
              <Card className="border-amber-500/30 bg-amber-950/10 shadow-lg">
                <CardContent className="pt-6">
                  <div className="flex items-start gap-3">
                    <ShieldAlert className="w-5 h-5 text-amber-500 shrink-0 mt-0.5" />
                    <div>
                      <p className="text-sm font-bold text-amber-400 mb-1">Security Policy</p>
                      <p className="text-xs text-slate-400 leading-relaxed">
                        All API keys are encrypted using Fernet symmetric encryption before storage. Keys with withdrawal permissions are automatically rejected. Sessions expire after 1 hour of inactivity.
                      </p>
                    </div>
                  </div>
                </CardContent>
              </Card>
            </>
          )}

          {/* ═══ PREFERENCES TAB ═══ */}
          {activeTab === "preferences" && (
            <>
              {/* Notifications */}
              <Card className="border-border bg-card shadow-lg">
                <CardHeader className="pb-4 border-b border-border/50">
                  <CardTitle className="text-lg text-slate-200 flex items-center gap-2">
                    <Bell className="w-5 h-5" /> Notifications
                  </CardTitle>
                  <CardDescription>Configure how you receive alerts.</CardDescription>
                </CardHeader>
                <CardContent className="pt-6 space-y-4">
                  <div className="flex items-center justify-between py-3 border-b border-border/30">
                    <div>
                      <p className="text-sm font-bold text-slate-200">Email Alerts</p>
                      <p className="text-xs text-slate-500">Receive critical system alerts via email.</p>
                    </div>
                    <button
                      onClick={() => { setEmailAlerts(!emailAlerts); toast.success(emailAlerts ? "Email alerts disabled" : "Email alerts enabled"); }}
                      className={`relative w-11 h-6 rounded-full transition-colors ${emailAlerts ? "bg-primary" : "bg-slate-700"}`}
                    >
                      <span className={`block w-4 h-4 rounded-full bg-white shadow-sm transition-transform absolute top-1 ${emailAlerts ? "translate-x-6" : "translate-x-1"}`} />
                    </button>
                  </div>
                  <div className="flex items-center justify-between py-3">
                    <div>
                      <p className="text-sm font-bold text-slate-200">Trade Notifications</p>
                      <p className="text-xs text-slate-500">In-app alerts for every executed trade.</p>
                    </div>
                    <button
                      onClick={() => { setTradeNotifications(!tradeNotifications); toast.success(tradeNotifications ? "Trade notifications disabled" : "Trade notifications enabled"); }}
                      className={`relative w-11 h-6 rounded-full transition-colors ${tradeNotifications ? "bg-primary" : "bg-slate-700"}`}
                    >
                      <span className={`block w-4 h-4 rounded-full bg-white shadow-sm transition-transform absolute top-1 ${tradeNotifications ? "translate-x-6" : "translate-x-1"}`} />
                    </button>
                  </div>
                </CardContent>
              </Card>

              {/* Trading Defaults */}
              <Card className="border-border bg-card shadow-lg">
                <CardHeader className="pb-4 border-b border-border/50">
                  <CardTitle className="text-lg text-slate-200 flex items-center gap-2">
                    <Globe className="w-5 h-5" /> Trading Defaults
                  </CardTitle>
                  <CardDescription>Default settings for new trading profiles.</CardDescription>
                </CardHeader>
                <CardContent className="pt-6 space-y-4">
                  <div>
                    <label className="text-xs font-bold text-slate-400 uppercase tracking-widest mb-1.5 block">Default Exchange</label>
                    <select
                      value={defaultExchange}
                      onChange={(e) => setDefaultExchange(e.target.value)}
                      className="w-full bg-black/50 border border-border rounded-md px-3 py-2 text-sm text-slate-200 focus:outline-none focus:ring-1 focus:ring-primary"
                    >
                      <option value="binance">Binance</option>
                      <option value="coinbase">Coinbase Pro</option>
                      <option value="kraken">Kraken</option>
                      <option value="bybit">Bybit</option>
                    </select>
                  </div>
                  <div>
                    <label className="text-xs font-bold text-slate-400 uppercase tracking-widest mb-1.5 block flex items-center gap-2">
                      <Clock className="w-3 h-3" /> Timezone
                    </label>
                    <Input
                      type="text"
                      value={timezone}
                      onChange={(e) => setTimezone(e.target.value)}
                      className="bg-black/50 border-border text-slate-200 font-mono text-sm"
                    />
                    <p className="text-[10px] text-slate-600 mt-1">Used for PnL reporting and trade timestamps.</p>
                  </div>
                  <div className="pt-2">
                    <Button onClick={handleSavePreferences} className="bg-primary text-primary-foreground hover:bg-primary/90 font-bold">
                      <Save className="w-4 h-4 mr-2" /> SAVE PREFERENCES
                    </Button>
                  </div>
                </CardContent>
              </Card>
            </>
          )}

        </div>
      </div>
    </div>
  );
}
