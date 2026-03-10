'use client';

import React, { useEffect } from 'react';
import { PortfolioSummaryCard } from '../components/pnl/PortfolioSummaryCard';
import { PnLDisplay } from '../components/pnl/PnLDisplay';
import { usePortfolioStore } from '../lib/stores/portfolioStore';
import { apiClient } from '../lib/api/client';
import { Profile } from '../lib/types';

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";

export default function Dashboard() {
  const { profiles, setProfiles } = usePortfolioStore();

  useEffect(() => {
    // 1. Authenticate Mock
    // In actual app, login screen handles this.
    localStorage.setItem('jwt', 'mock-jwt-token-sprint-5');

    // 2. Fetch Active Profiles
    const fetchProfiles = async () => {
      try {
        // We'll mock returning 2 profiles to show the Dashboard real time loops
        const mockProfiles: Profile[] = [
          { profile_id: 'prof-btc-test1', is_active: true, rules_json: {} },
          { profile_id: 'prof-eth-test2', is_active: true, rules_json: {} }
        ];

        // Uncomment once backend is fully booted:
        // const fetched = await apiClient.get<Profile[]>('/profiles');
        setProfiles(mockProfiles);
      } catch (e) {
        console.error("Failed loading profiles", e);
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
            {profiles.length === 0 ? (
              <div className="h-full flex justify-center items-center font-mono opacity-50 text-sm">NO PROFILES ACTIVE</div>
            ) : (
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                {profiles.map(p => (
                  <div key={p.profile_id} className="border border-border p-5 rounded-lg bg-black/20 relative overflow-hidden group hover:border-primary/50 transition-colors">
                    <div className="absolute top-0 w-full h-1 bg-gradient-to-r from-primary to-cyan-500 transform origin-left transition-transform group-hover:scale-x-110 left-0" />
                    <div className="flex justify-between items-start mb-4">
                      <div className="text-sm font-bold font-mono text-cyan-400 truncate">{p.profile_id}</div>
                      <Badge variant="default" className="bg-emerald-500/10 text-emerald-500 hover:bg-emerald-500/20 text-[10px] font-bold">
                        RUNNING
                      </Badge>
                    </div>
                    <PnLDisplay profileId={p.profile_id} />
                  </div>
                ))}
              </div>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
