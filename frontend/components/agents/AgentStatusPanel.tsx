'use client';

import React, { useEffect, useState } from 'react';
import { api } from '../../lib/api/client';
import { AgentScore } from '../../lib/types';
import { RegimeBadge } from '../profiles/RegimeBadge';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import {
  Brain,
  Activity,
  MessageSquare,
  RefreshCw,
  Wifi,
  WifiOff,
} from 'lucide-react';

const POLL_INTERVAL = 15000; // 15 seconds

export const AgentStatusPanel: React.FC = () => {
  const [agents, setAgents] = useState<AgentScore[]>([]);
  const [loading, setLoading] = useState(true);
  const [lastUpdated, setLastUpdated] = useState<Date | null>(null);
  const [error, setError] = useState(false);

  const fetchAgents = async () => {
    try {
      const data = await api.agents.status();
      setAgents(data as AgentScore[]);
      setLastUpdated(new Date());
      setError(false);
    } catch {
      setError(true);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchAgents();
    const interval = setInterval(fetchAgents, POLL_INTERVAL);
    return () => clearInterval(interval);
  }, []);

  const hasAnyData = agents.some(
    (a) => a.ta_score !== null || a.sentiment_score !== null || a.hmm_regime !== null
  );

  return (
    <Card className="border-border bg-card shadow-2xl">
      <CardHeader className="pb-3">
        <div className="flex items-center justify-between">
          <CardTitle className="uppercase text-xs font-bold text-muted-foreground tracking-wider flex items-center gap-2">
            <Brain className="w-3.5 h-3.5" />
            ML Agent Scores
          </CardTitle>
          <div className="flex items-center gap-2">
            {lastUpdated && (
              <span className="text-[9px] text-muted-foreground font-mono">
                {lastUpdated.toLocaleTimeString()}
              </span>
            )}
            <button
              onClick={fetchAgents}
              className="p-1 rounded hover:bg-white/5 transition-colors"
              title="Refresh"
            >
              <RefreshCw className={`w-3 h-3 text-muted-foreground ${loading ? 'animate-spin' : ''}`} />
            </button>
          </div>
        </div>
      </CardHeader>
      <CardContent>
        {error ? (
          <div className="flex flex-col items-center gap-2 py-6 text-center">
            <WifiOff className="w-5 h-5 text-muted-foreground/50" />
            <p className="text-xs text-muted-foreground">
              Agent API unavailable
            </p>
          </div>
        ) : !hasAnyData ? (
          <div className="flex flex-col items-center gap-2 py-6 text-center">
            <Wifi className="w-5 h-5 text-muted-foreground/30" />
            <p className="text-xs text-muted-foreground font-mono">
              NO AGENT DATA
            </p>
            <p className="text-[10px] text-muted-foreground/70">
              Agent services will populate scores once running
            </p>
          </div>
        ) : (
          <div className="space-y-4">
            {agents.map((agent) => (
              <div
                key={agent.symbol}
                className="p-4 rounded-lg bg-black/20 border border-border/50 space-y-3"
              >
                <div className="flex items-center justify-between">
                  <span className="text-sm font-bold font-mono text-cyan-400">
                    {agent.symbol}
                  </span>
                  {agent.hmm_regime && (
                    <RegimeBadge regime={agent.hmm_regime} />
                  )}
                </div>

                <div className="grid grid-cols-3 gap-3">
                  {/* TA Score */}
                  <div className="flex flex-col gap-1">
                    <div className="flex items-center gap-1.5">
                      <Activity className="w-3 h-3 text-indigo-400" />
                      <span className="text-[9px] uppercase text-muted-foreground font-bold tracking-wider">
                        TA Score
                      </span>
                    </div>
                    {agent.ta_score !== null ? (
                      <div className="flex items-center gap-2">
                        <ScoreBar value={agent.ta_score} />
                        <span className="text-xs font-mono font-bold text-slate-300">
                          {agent.ta_score > 0 ? '+' : ''}
                          {agent.ta_score.toFixed(2)}
                        </span>
                      </div>
                    ) : (
                      <span className="text-[10px] text-muted-foreground/50 font-mono">
                        --
                      </span>
                    )}
                  </div>

                  {/* Sentiment Score */}
                  <div className="flex flex-col gap-1">
                    <div className="flex items-center gap-1.5">
                      <MessageSquare className="w-3 h-3 text-violet-400" />
                      <span className="text-[9px] uppercase text-muted-foreground font-bold tracking-wider">
                        Sentiment
                      </span>
                    </div>
                    {agent.sentiment_score !== null ? (
                      <div className="flex items-center gap-2">
                        <ScoreBar value={agent.sentiment_score} />
                        <span className="text-xs font-mono font-bold text-slate-300">
                          {agent.sentiment_score > 0 ? '+' : ''}
                          {agent.sentiment_score.toFixed(2)}
                        </span>
                      </div>
                    ) : (
                      <span className="text-[10px] text-muted-foreground/50 font-mono">
                        --
                      </span>
                    )}
                  </div>

                  {/* Sentiment Source */}
                  <div className="flex flex-col gap-1">
                    <span className="text-[9px] uppercase text-muted-foreground font-bold tracking-wider">
                      Source
                    </span>
                    {agent.sentiment_source ? (
                      <Badge
                        className={`text-[9px] w-fit ${
                          agent.sentiment_source === 'llm'
                            ? 'bg-violet-500/10 text-violet-400'
                            : agent.sentiment_source === 'cache'
                            ? 'bg-cyan-500/10 text-cyan-400'
                            : 'bg-slate-500/10 text-slate-400'
                        }`}
                      >
                        {agent.sentiment_source.toUpperCase()}
                      </Badge>
                    ) : (
                      <span className="text-[10px] text-muted-foreground/50 font-mono">
                        --
                      </span>
                    )}
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </CardContent>
    </Card>
  );
};

function ScoreBar({ value }: { value: number }) {
  // value: -1.0 to 1.0, map to 0-100%
  const pct = ((value + 1) / 2) * 100;
  const isBullish = value > 0.1;
  const isBearish = value < -0.1;
  const color = isBullish
    ? 'bg-emerald-500'
    : isBearish
    ? 'bg-rose-500'
    : 'bg-slate-500';

  return (
    <div className="flex-1 h-1.5 bg-slate-800 rounded-full overflow-hidden relative">
      {/* Center marker */}
      <div className="absolute left-1/2 top-0 w-px h-full bg-slate-600 z-10" />
      <div
        className={`absolute top-0 h-full rounded-full transition-all duration-500 ${color}`}
        style={{
          left: value >= 0 ? '50%' : `${pct}%`,
          width: `${Math.abs(value) * 50}%`,
        }}
      />
    </div>
  );
}
