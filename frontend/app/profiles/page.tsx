"use client";

import React, { useState, useEffect } from "react";
import { Card, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Save, Plus, Activity, Power, PowerOff, Code } from "lucide-react";
import { Profile } from "@/lib/types";
import { toast } from "sonner";

// Mock Data
const MOCK_PROFILES: Profile[] = [
  {
    profile_id: "prof-btc-test1",
    is_active: true,
    rules_json: {
      "asset": "BTC/USD",
      "strategy": "MeanReversion",
      "timeframe": "1m",
      "max_position_size": 0.1,
      "stop_loss_pct": 0.05,
      "take_profit_pct": 0.10,
    }
  },
  {
    profile_id: "prof-eth-test2",
    is_active: true,
    rules_json: {
      "asset": "ETH/USD",
      "strategy": "Momentum",
      "timeframe": "5m",
      "max_position_size": 2.5,
      "stop_loss_pct": 0.02,
      "take_profit_pct": 0.06,
    }
  },
  {
    profile_id: "prof-sol-dormant",
    is_active: false,
    rules_json: {
      "asset": "SOL/USD",
      "strategy": "Arbitrage",
      "timeframe": "1s",
      "max_position_size": 50,
      "stop_loss_pct": 0.01,
      "take_profit_pct": 0.02,
    }
  }
];

export default function ProfilesPage() {
  const [profiles, setProfiles] = useState<Profile[]>(MOCK_PROFILES);
  const [selectedProfileId, setSelectedProfileId] = useState<string | null>(MOCK_PROFILES[0].profile_id);
  const [editorContent, setEditorContent] = useState<string>("");

  const selectedProfile = profiles.find(p => p.profile_id === selectedProfileId);

  useEffect(() => {
    if (selectedProfile) {
      setEditorContent(JSON.stringify(selectedProfile.rules_json, null, 2));
    } else {
      setEditorContent("");
    }
  }, [selectedProfileId]);

  const handleSave = () => {
    if (!selectedProfile) return;
    try {
      const parsed = JSON.parse(editorContent);
      setProfiles(prev => prev.map(p => 
        p.profile_id === selectedProfile.profile_id 
          ? { ...p, rules_json: parsed } 
          : p
      ));
      toast.success("Profile Saved!");
    } catch (e) {
      toast.error("Invalid JSON format");
    }
  };

  const activeCount = profiles.filter(p => p.is_active).length;

  return (
    <div className="flex flex-col h-full gap-6 max-w-[1600px] mx-auto">
      {/* Header */}
      <div className="flex items-center justify-between border-b border-border pb-4 shrink-0">
        <div>
          <h1 className="text-3xl font-black tracking-tight text-white mb-1">AGENT PROFILES</h1>
          <p className="text-muted-foreground text-sm">Manage trading agent boundaries, logic, and state.</p>
        </div>
        <div className="flex items-center gap-4">
          <Badge variant="outline" className="text-emerald-500 border-emerald-500/30 bg-emerald-500/10 px-3 py-1">
            <Activity className="w-3 h-3 mr-2 inline" />
            {activeCount} Active
          </Badge>
          <Button className="bg-primary text-primary-foreground hover:bg-primary/90 font-bold tracking-wider">
            <Plus className="w-4 h-4 mr-2" /> NEW PROFILE
          </Button>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-12 gap-8 flex-1 min-h-[600px] overflow-hidden">
        {/* Left Column: List */}
        <div className="lg:col-span-4 flex flex-col gap-4 overflow-hidden">
          <Input 
            type="search" 
            placeholder="Search profiles..." 
            className="bg-card border-border shrink-0" 
          />
          <div className="flex flex-col gap-3 overflow-y-auto pr-2 pb-4 flex-1">
            {profiles.map(p => (
              <Card 
                key={p.profile_id} 
                onClick={() => setSelectedProfileId(p.profile_id)}
                className={`cursor-pointer transition-all border shrink-0 ${selectedProfileId === p.profile_id ? 'border-primary ring-1 ring-primary/50 bg-primary/5' : 'border-border hover:border-slate-600 bg-card hover:bg-slate-900/50'}`}
              >
                <div className="p-4 flex items-center justify-between relative overflow-hidden">
                  {selectedProfileId === p.profile_id && (
                    <div className="absolute left-0 top-0 bottom-0 w-1 bg-primary" />
                  )}
                  <div className="flex flex-col gap-1">
                    <span className="font-mono font-bold text-sm text-slate-200">{p.profile_id}</span>
                    <span className="text-xs text-muted-foreground flex items-center gap-1">
                      {p.is_active ? <Power className="w-3 h-3 text-emerald-500" /> : <PowerOff className="w-3 h-3 text-slate-500" />}
                      {p.is_active ? 'Running' : 'Dormant'}
                    </span>
                  </div>
                  <div>
                    {p.is_active && <span className="flex h-2 w-2 relative"><span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75"></span><span className="relative inline-flex rounded-full h-2 w-2 bg-emerald-500"></span></span>}
                  </div>
                </div>
              </Card>
            ))}
          </div>
        </div>

        {/* Right Column: Editor */}
        <Card className="lg:col-span-8 flex flex-col border-border bg-card shadow-xl overflow-hidden h-full">
          {selectedProfile ? (
            <>
              <CardHeader className="border-b border-border bg-slate-900/50 py-4 shrink-0">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-3">
                    <Code className="text-primary w-5 h-5 flex-shrink-0" />
                    <div>
                      <CardTitle className="text-lg font-mono font-bold text-slate-200">{selectedProfile.profile_id}</CardTitle>
                      <CardDescription className="text-xs">JSON Configuration</CardDescription>
                    </div>
                  </div>
                  <div className="flex gap-2">
                    <Button variant="outline" size="sm" className="border-border hover:bg-slate-800 text-slate-300">
                      {selectedProfile.is_active ? 'DEACTIVATE' : 'ACTIVATE'}
                    </Button>
                    <Button size="sm" onClick={handleSave} className="bg-indigo-600 hover:bg-indigo-500 text-white font-bold">
                      <Save className="w-4 h-4 mr-2" /> SAVE
                    </Button>
                  </div>
                </div>
              </CardHeader>
              <div className="flex-1 relative bg-[#0d1117] p-4 text-sm overflow-hidden">
                <textarea
                  className="w-full h-full bg-transparent text-slate-300 font-mono resize-none focus:outline-none placeholder:text-slate-700 font-medium"
                  value={editorContent}
                  onChange={(e) => setEditorContent(e.target.value)}
                  spellCheck={false}
                />
              </div>
            </>
          ) : (
            <div className="flex-1 flex flex-col items-center justify-center text-slate-500 gap-4">
              <Code className="w-12 h-12 opacity-20" />
              <p>Select a profile to view configuration</p>
            </div>
          )}
        </Card>
      </div>
    </div>
  );
}
