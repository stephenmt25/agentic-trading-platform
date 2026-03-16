'use client';

import React, { useEffect, useState } from 'react';
import { PortfolioSummaryCard } from '../components/pnl/PortfolioSummaryCard';
import { PnLDisplay } from '../components/pnl/PnLDisplay';
import { AgentStatusPanel } from '../components/agents/AgentStatusPanel';
import { RiskMonitorCard } from '../components/risk/RiskMonitorCard';
import { usePortfolioStore } from '../lib/stores/portfolioStore';
import { api, type ProfileResponse } from '../lib/api/client';

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Loader2 } from "lucide-react";
import Link from "next/link";

export default function Dashboard() {
  const { profiles, setProfiles } = usePortfolioStore();
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const fetchProfiles = async () => {
      setIsLoading(true);
      try {
        const fetched = await api.profiles.list();
        // Only show active profiles on the dashboard
        const activeProfiles = fetched.filter((p) => p.is_active && !p.deleted_at);
        setProfiles(
          activeProfiles.map((p) => ({
            profile_id: p.profile_id,
            name: p.name,
            is_active: p.is_active,
            rules_json: p.rules_json,
          }))
        );
        setError(null);
      } catch (e: any) {
        const msg = e.message || "Failed to load profiles";
        console.error("Failed loading profiles", msg);
        // Don't show error for auth failures — user just needs to log in
        if (msg.includes("Unauthorized")) {
          setError(null);
        } else {
          setError(msg);
        }
        setProfiles([]);
      } finally {
        setIsLoading(false);
      }
    };

    fetchProfiles();
  }, [setProfiles]);

  return (
    <div className="relative h-full flex flex-col gap-6">

      {/* Header Area */}
      <h1 className="text-3xl font-black tracking-tight text-white mb-4 border-b border-border pb-4 flex justify-between items-center">
        DASHBOARD OVERVIEW
      </h1>

      {/* Main Grid Top */}
      <div className="grid grid-cols-1 xl:grid-cols-2 gap-8 mb-8">
        <PortfolioSummaryCard />

        <Card className="flex flex-col border-border bg-card shadow-2xl">
          <CardHeader>
            <CardTitle className="uppercase text-xs font-bold text-muted-foreground tracking-wider">
              Active Agent Bounds
            </CardTitle>
          </CardHeader>
          <CardContent className="flex-1">
            {isLoading ? (
              <div className="h-full flex justify-center items-center">
                <Loader2 className="w-6 h-6 animate-spin text-muted-foreground" />
              </div>
            ) : error ? (
              <div className="h-full flex flex-col justify-center items-center gap-2 text-center">
                <div className="font-mono text-sm text-amber-500/80">BACKEND OFFLINE</div>
                <p className="text-xs text-muted-foreground max-w-xs">
                  Could not reach the API. Start the API gateway on port 8000 to see live profile data.
                </p>
              </div>
            ) : profiles.length === 0 ? (
              <div className="h-full flex flex-col justify-center items-center gap-2 text-center">
                <div className="font-mono opacity-50 text-sm">NO ACTIVE PROFILES</div>
                <p className="text-xs text-muted-foreground">
                  Navigate to <Link href="/profiles" className="text-primary underline">Profiles</Link> to create your first trading agent.
                </p>
              </div>
            ) : (
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                {profiles.map(p => (
                  <Link
                    key={p.profile_id}
                    href={`/profiles?selected=${p.profile_id}`}
                    className="border border-border p-5 rounded-lg bg-black/20 relative overflow-hidden group hover:border-primary/50 transition-colors cursor-pointer block"
                  >
                    <div className="absolute top-0 w-full h-1 bg-gradient-to-r from-primary to-cyan-500 transform origin-left transition-transform group-hover:scale-x-110 left-0" />
                    <div className="flex justify-between items-start mb-4">
                      <div className="text-sm font-bold font-mono text-cyan-400 truncate">{p.name || 'Unnamed Agent'}</div>
                      <Badge variant="default" className={`text-[10px] font-bold ${p.is_active ? 'bg-emerald-500/10 text-emerald-500 hover:bg-emerald-500/20' : 'bg-slate-500/10 text-slate-500'}`}>
                        {p.is_active ? 'RUNNING' : 'DORMANT'}
                      </Badge>
                    </div>
                    <PnLDisplay profileId={p.profile_id} />
                  </Link>
                ))}
              </div>
            )}
          </CardContent>
        </Card>
      </div>

      {/* Phase 3: ML Agents & Risk Monitor */}
      <div className="grid grid-cols-1 xl:grid-cols-2 gap-8">
        <AgentStatusPanel />
        <RiskMonitorCard
          profileIds={profiles.map(p => p.profile_id)}
        />
      </div>
    </div>
  );
}
