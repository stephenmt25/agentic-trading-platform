'use client';

import React, { useState } from 'react';
import { StoredRun } from '../../lib/types';
import { ChevronDown, ChevronUp, ChevronsUpDown } from 'lucide-react';

interface ComparisonTableProps {
  runs: StoredRun[];
}

type MetricKey = 'total_trades' | 'win_rate' | 'avg_return' | 'max_drawdown' | 'sharpe' | 'profit_factor';

interface Column {
  key: MetricKey;
  label: string;
  format: (v: number) => string;
  higherIsBetter: boolean;
}

const COLUMNS: Column[] = [
  { key: 'total_trades', label: 'Trades', format: (v) => v.toString(), higherIsBetter: true },
  { key: 'win_rate', label: 'Win %', format: (v) => `${(v * 100).toFixed(1)}%`, higherIsBetter: true },
  { key: 'avg_return', label: 'Avg Ret', format: (v) => `${(v * 100).toFixed(2)}%`, higherIsBetter: true },
  { key: 'max_drawdown', label: 'Max DD', format: (v) => `${(v * 100).toFixed(2)}%`, higherIsBetter: false },
  { key: 'sharpe', label: 'Sharpe', format: (v) => v.toFixed(2), higherIsBetter: true },
  { key: 'profit_factor', label: 'PF', format: (v) => (v === Infinity ? 'INF' : v.toFixed(2)), higherIsBetter: true },
];

export const ComparisonTable: React.FC<ComparisonTableProps> = ({ runs }) => {
  const [sortKey, setSortKey] = useState<MetricKey | null>(null);
  const [sortDesc, setSortDesc] = useState(true);

  const sorted = sortKey
    ? [...runs].sort((a, b) => {
        const av = a.result[sortKey];
        const bv = b.result[sortKey];
        return sortDesc ? bv - av : av - bv;
      })
    : runs;

  const bestByCol: Record<MetricKey, number> = COLUMNS.reduce((acc, col) => {
    const vals = runs.map((r) => r.result[col.key]);
    acc[col.key] = col.higherIsBetter ? Math.max(...vals) : Math.min(...vals);
    return acc;
  }, {} as Record<MetricKey, number>);

  const handleSort = (key: MetricKey) => {
    if (sortKey === key) setSortDesc(!sortDesc);
    else {
      setSortKey(key);
      setSortDesc(true);
    }
  };

  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm font-mono tabular-nums">
        <thead>
          <tr className="border-b border-border">
            <th className="text-left px-3 py-2 text-xs uppercase text-muted-foreground font-medium">
              Run
            </th>
            {COLUMNS.map((col) => (
              <th
                key={col.key}
                onClick={() => handleSort(col.key)}
                className="text-right px-3 py-2 text-xs uppercase text-muted-foreground font-medium cursor-pointer select-none hover:text-foreground transition-colors"
              >
                <span className="inline-flex items-center gap-1">
                  {col.label}
                  {sortKey === col.key ? (
                    sortDesc ? (
                      <ChevronDown className="w-3 h-3" />
                    ) : (
                      <ChevronUp className="w-3 h-3" />
                    )
                  ) : (
                    <ChevronsUpDown className="w-3 h-3 opacity-40" />
                  )}
                </span>
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {sorted.map((run) => (
            <tr key={run.id} className="border-b border-border/50 hover:bg-accent/30 transition-colors">
              <td className="px-3 py-2 text-foreground">
                <span className="inline-flex items-center gap-2">
                  <span
                    className="w-2.5 h-2.5 rounded-full shrink-0"
                    style={{ backgroundColor: run.color }}
                  />
                  <span className="truncate max-w-[180px]" title={run.label}>
                    {run.label}
                  </span>
                </span>
              </td>
              {COLUMNS.map((col) => {
                const val = run.result[col.key];
                const isBest = runs.length > 1 && val === bestByCol[col.key] && Number.isFinite(val);
                return (
                  <td
                    key={col.key}
                    className={`px-3 py-2 text-right ${
                      isBest ? 'text-emerald-500 font-semibold' : 'text-foreground'
                    }`}
                  >
                    {col.format(val)}
                  </td>
                );
              })}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
};
