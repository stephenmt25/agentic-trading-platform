'use client';

import React, { useEffect, useState } from 'react';
import { api } from '../../lib/api/client';
import { AgentScore } from '../../lib/types';
import { RegimeBadge } from '../profiles/RegimeBadge';
import { InfoTooltip } from '@/components/ui/InfoTooltip';
import { Badge } from '@/components/ui/badge';
import {
  RefreshCw,
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
    <section>
      <div className="flex items-center justify-between mb-4">
        <h2 className="uppercase text-xs font-semibold text-muted-foreground tracking-wider flex items-center gap-2">
          ML Agent Scores
          <InfoTooltip text="Latest scores from TA, Sentiment, and Regime agents per symbol. TA score ranges -1 (bearish) to +1 (bullish). Sentiment uses LLM analysis of news headlines." />
        </h2>
        <div className="flex items-center gap-2">
          {lastUpdated && (
            <span className="text-xs text-muted-foreground font-mono tabular-nums">
              {lastUpdated.toLocaleTimeString()}
            </span>
          )}
          <button
            onClick={fetchAgents}
            className="p-2 rounded-md hover:bg-accent transition-colors min-h-[44px] min-w-[44px] flex items-center justify-center focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary"
            aria-label="Refresh agent scores"
          >
            <RefreshCw className={`w-3.5 h-3.5 text-muted-foreground ${loading ? 'animate-spin' : ''}`} />
          </button>
        </div>
      </div>

      {error ? (
        <div className="flex flex-col items-center gap-2 py-6 text-center">
          <WifiOff className="w-5 h-5 text-muted-foreground/50" />
          <p className="text-xs text-muted-foreground">
            Agent API unavailable
          </p>
        </div>
      ) : !hasAnyData ? (
        <div className="flex flex-col items-center gap-2 py-6 text-center">
          <p className="text-xs text-muted-foreground font-mono">
            NO AGENT DATA
          </p>
          <p className="text-xs text-muted-foreground/70">
            Agent services will populate scores once running
          </p>
        </div>
      ) : (
        <div className="space-y-3">
          {agents.map((agent) => (
            <div
              key={agent.symbol}
              className="p-3 rounded-md border border-border space-y-3"
            >
              <div className="flex items-center justify-between">
                <span className="text-sm font-medium font-mono text-foreground">
                  {agent.symbol}
                </span>
                {agent.hmm_regime && (
                  <RegimeBadge regime={agent.hmm_regime} />
                )}
              </div>

              <div className="grid grid-cols-3 gap-3">
                {/* TA Score */}
                <div className="flex flex-col gap-1">
                  <span className="text-xs uppercase text-muted-foreground font-medium tracking-wider">
                    TA Score
                  </span>
                  {agent.ta_score !== null ? (
                    <div className="flex items-center gap-2">
                      <ScoreBar value={agent.ta_score} />
                      <span className="text-xs font-mono tabular-nums font-medium text-foreground/80">
                        {agent.ta_score > 0 ? '+' : ''}
                        {agent.ta_score.toFixed(2)}
                      </span>
                    </div>
                  ) : (
                    <span className="text-xs text-muted-foreground/50 font-mono">
                      --
                    </span>
                  )}
                </div>

                {/* Sentiment Score */}
                <div className="flex flex-col gap-1">
                  <span className="text-xs uppercase text-muted-foreground font-medium tracking-wider">
                    Sentiment
                  </span>
                  {agent.sentiment_score !== null ? (
                    <div className="flex items-center gap-2">
                      <ScoreBar value={agent.sentiment_score} />
                      <span className="text-xs font-mono tabular-nums font-medium text-foreground/80">
                        {agent.sentiment_score > 0 ? '+' : ''}
                        {agent.sentiment_score.toFixed(2)}
                      </span>
                    </div>
                  ) : (
                    <span className="text-xs text-muted-foreground/50 font-mono">
                      --
                    </span>
                  )}
                </div>

                {/* Sentiment Source */}
                <div className="flex flex-col gap-1">
                  <span className="text-xs uppercase text-muted-foreground font-medium tracking-wider">
                    Source
                  </span>
                  {agent.sentiment_source ? (
                    <Badge
                      className={`text-xs w-fit ${
                        agent.sentiment_source === 'llm'
                          ? 'text-muted-foreground'
                          : agent.sentiment_source === 'cache'
                          ? 'text-muted-foreground'
                          : 'text-muted-foreground'
                      }`}
                    >
                      {agent.sentiment_source.toUpperCase()}
                    </Badge>
                  ) : (
                    <span className="text-xs text-muted-foreground/50 font-mono">
                      --
                    </span>
                  )}
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </section>
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
    ? 'bg-red-500'
    : 'bg-muted-foreground/50';

  return (
    <div className="flex-1 h-1.5 bg-accent rounded-full overflow-hidden relative">
      {/* Center marker */}
      <div className="absolute left-1/2 top-0 w-px h-full bg-border z-10" />
      <div
        className={`absolute top-0 h-full rounded-full transition-[width] duration-500 ${color}`}
        style={{
          left: value >= 0 ? '50%' : `${pct}%`,
          width: `${Math.abs(value) * 50}%`,
        }}
      />
    </div>
  );
}
