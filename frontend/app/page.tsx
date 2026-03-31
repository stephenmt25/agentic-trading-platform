'use client';

import React, { useEffect, useState } from 'react';
import { PortfolioSummaryCard } from '../components/pnl/PortfolioSummaryCard';
import { PnLDisplay } from '../components/pnl/PnLDisplay';
import { AgentStatusPanel } from '../components/agents/AgentStatusPanel';
import { RiskMonitorCard } from '../components/risk/RiskMonitorCard';
import { usePortfolioStore } from '../lib/stores/portfolioStore';
import { api, type ProfileResponse } from '../lib/api/client';

import { Badge } from "@/components/ui/badge";
import { AlertTriangle } from "lucide-react";
import Link from "next/link";
import { motion } from "framer-motion";
import { pageEnter, staggerContainer, fadeUpChild } from "@/lib/motion";

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
        // Don't log or show error for auth failures — user just needs to log in
        if (msg.includes("Unauthorized")) {
          setError(null);
        } else {
          console.error("Failed loading profiles", msg);
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
    <motion.div className="relative h-full flex flex-col gap-6"
      variants={pageEnter} initial="initial" animate="animate">

      {/* Header Area */}
      <h1 className="text-xl font-semibold tracking-tight text-foreground border-b border-border pb-4">
        Dashboard
      </h1>

      {/* Main Grid Top */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <PortfolioSummaryCard />

        <section className="flex flex-col border-t border-border pt-4 lg:border-t-0 lg:pt-0">
          <h2 className="uppercase text-xs font-semibold text-muted-foreground tracking-wider mb-4">
            Active Agent Bounds
          </h2>
          <div className="flex-1">
            {isLoading ? (
              <div className="h-full flex flex-col gap-3 py-4">
                <div className="h-20 bg-accent animate-pulse rounded-md" />
                <div className="h-20 bg-accent animate-pulse rounded-md" />
                <div className="h-20 bg-accent animate-pulse rounded-md" />
              </div>
            ) : error ? (
              <div className="h-full flex flex-col justify-center items-center gap-2 text-center py-12">
                <AlertTriangle className="w-5 h-5 text-amber-500/80" />
                <div className="font-mono text-sm text-amber-500/80">BACKEND OFFLINE</div>
                <p className="text-xs text-muted-foreground max-w-xs">
                  Could not reach the API. Start the API gateway on port 8000 to see live profile data.
                </p>
              </div>
            ) : profiles.length === 0 ? (
              <div className="h-full flex flex-col justify-center items-center gap-2 text-center py-12">
                <div className="font-mono text-muted-foreground text-sm">NO ACTIVE PROFILES</div>
                <p className="text-xs text-muted-foreground">
                  Navigate to <Link href="/profiles" className="text-primary underline">Profiles</Link> to create your first trading agent.
                </p>
              </div>
            ) : (
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                {profiles.map(p => (
                  <Link
                    key={p.profile_id}
                    href={`/profiles?selected=${p.profile_id}`}
                    className="border border-border p-4 rounded-md hover:border-primary/40 transition-colors cursor-pointer block"
                  >
                    <div className="flex justify-between items-start mb-3">
                      <div className="text-sm font-medium font-mono text-foreground truncate">{p.name || 'Unnamed Agent'}</div>
                      <Badge variant="outline" className={`text-xs font-medium ${p.is_active ? 'text-emerald-500 border-emerald-500/30' : 'text-muted-foreground border-border'}`}>
                        {p.is_active ? 'RUNNING' : 'DORMANT'}
                      </Badge>
                    </div>
                    <PnLDisplay profileId={p.profile_id} />
                  </Link>
                ))}
              </div>
            )}
          </div>
        </section>
      </div>

      {/* ML Agents & Risk Monitor */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <AgentStatusPanel />
        <RiskMonitorCard
          profileIds={profiles.map(p => p.profile_id)}
        />
      </div>
    </motion.div>
  );
}
