'use client';

import React, { useEffect } from 'react';
import { PortfolioSummaryCard } from '../components/pnl/PortfolioSummaryCard';
import { AlertTray } from '../components/validation/AlertTray';
import { PnLDisplay } from '../components/pnl/PnLDisplay';
import { usePortfolioStore } from '../lib/stores/portfolioStore';
import { apiClient } from '../lib/api/client';
import { Profile } from '../lib/types';

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
      <h1 className="text-3xl font-black tracking-tight text-white mb-4 border-b border-slate-800 pb-4 flex justify-between items-center">
        DASHBOARD OVERVIEW
      </h1>

      {/* Main Grid Top */}
      <div className="grid grid-cols-1 xl:grid-cols-2 gap-8 mb-8">
        <PortfolioSummaryCard />

        <div className="bg-slate-900 border border-slate-700/50 rounded-xl p-6 shadow-xl w-full flex flex-col">
          <h2 className="uppercase text-xs font-bold text-slate-500 mb-6">Active Agent Bounds</h2>
          {profiles.length === 0 ? (
            <div className="flex-1 flex justify-center items-center font-mono opacity-50 text-sm">NO PROFILES ACTIVE</div>
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {profiles.map(p => (
                <div key={p.profile_id} className="border border-slate-800 p-4 rounded-lg bg-slate-950/50 relative overflow-hidden group">
                  <div className="absolute top-0 w-full h-1 bg-gradient-to-r from-indigo-500 to-cyan-500 transform origin-left transition-transform group-hover:scale-x-110" />
                  <div className="text-sm font-bold font-mono text-cyan-400 truncate mb-1">{p.profile_id}</div>
                  <div className="text-[10px] uppercase text-emerald-500 bg-emerald-500/10 inline-block px-2 py-0.5 rounded-full font-bold mb-4">
                    RUNNING
                  </div>
                  <PnLDisplay profileId={p.profile_id} />
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      <AlertTray />
    </div>
  );
}
