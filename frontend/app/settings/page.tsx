"use client";

import React, { useState } from "react";
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Key, Plus, ExternalLink, ShieldAlert, CheckCircle2, Loader2, KeyRound, Save } from "lucide-react";
import { toast } from "sonner";

export default function SettingsPage() {
  const [isTesting, setIsTesting] = useState(false);
  const [apiKey, setApiKey] = useState("");
  const [apiSecret, setApiSecret] = useState("");
  
  const handleTestConnection = async () => {
    if (!apiKey || !apiSecret) {
      toast.error("Please enter both API Key and Secret.");
      return;
    }
    
    setIsTesting(true);
    // Mock API call
    setTimeout(() => {
      setIsTesting(false);
      toast.success("Connection Successful! Read-only permissions verified.");
    }, 1500);
  };

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
          <Button variant="secondary" className="justify-start font-bold">
            <KeyRound className="w-4 h-4 mr-3" />
            Exchange Accounts
          </Button>
          <Button variant="ghost" className="justify-start text-muted-foreground hover:text-white">
            <ShieldAlert className="w-4 h-4 mr-3" />
            Security
          </Button>
          <Button variant="ghost" className="justify-start text-muted-foreground hover:text-white">
            <ExternalLink className="w-4 h-4 mr-3" />
            Preferences
          </Button>
        </div>

        {/* Main Content Area */}
        <div className="md:col-span-3 flex flex-col gap-8">
          
          {/* Linked Accounts */}
          <Card className="border-border bg-card shadow-lg">
            <CardHeader className="pb-4 border-b border-border/50">
              <div className="flex items-center justify-between">
                <div>
                  <CardTitle className="text-lg text-slate-200">Connected Exchanges</CardTitle>
                  <CardDescription>Your active broker API connections.</CardDescription>
                </div>
                <Button size="sm" variant="outline" className="border-border hover:bg-slate-800">
                  <Plus className="w-4 h-4 mr-2" /> ADD EXCHANGE
                </Button>
              </div>
            </CardHeader>
            <CardContent className="pt-6">
               <div className="flex flex-col items-center justify-center p-8 border border-dashed border-border rounded-xl bg-black/20 text-center">
                  <Key className="w-12 h-12 text-muted-foreground mb-4 opacity-50" />
                  <p className="text-slate-300 font-bold mb-1">No execution keys found</p>
                  <p className="text-sm text-slate-500 max-w-sm mb-6">Connect a supported exchange to execute live trades or begin paper trading with real order books.</p>
               </div>
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
                  <Input 
                    type="text" 
                    placeholder="vmPUZE6mv9SD5VNHk4HlWJmN..." 
                    className="bg-black/50 border-border font-mono text-slate-300 placeholder:opacity-30"
                    value={apiKey}
                    onChange={(e) => setApiKey(e.target.value)}
                  />
                </div>
                <div>
                  <label className="text-xs font-bold text-slate-400 uppercase tracking-widest mb-1 block">Secret Key</label>
                  <Input 
                    type="password" 
                    placeholder="••••••••••••••••••••••••" 
                    className="bg-black/50 border-border font-mono text-slate-300 placeholder:opacity-30"
                    value={apiSecret}
                    onChange={(e) => setApiSecret(e.target.value)}
                  />
                </div>
              </div>

              <div className="flex items-center gap-4 pt-4 border-t border-border/50">
                <Button 
                  onClick={handleTestConnection} 
                  disabled={isTesting}
                  variant="outline" 
                  className="border-primary text-primary hover:bg-primary/10"
                >
                  {isTesting ? (
                    <><Loader2 className="w-4 h-4 mr-2 animate-spin" /> TESTING...</>
                  ) : (
                    "TEST CONNECTION"
                  )}
                </Button>
                <Button 
                  disabled={true} 
                  className="bg-primary text-primary-foreground opacity-50 cursor-not-allowed"
                >
                  <Save className="w-4 h-4 mr-2" /> SAVE KEYS EXTERNALLY
                </Button>
              </div>
            </CardContent>
          </Card>

        </div>
      </div>
    </div>
  );
}
