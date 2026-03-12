'use client';

import React, { useState } from 'react';
import { SimulatedTrade } from '../../lib/types';
import { Badge } from '@/components/ui/badge';
import { ChevronDown, ChevronUp } from 'lucide-react';

interface TradesTableProps {
  trades: SimulatedTrade[];
}

const PAGE_SIZE = 20;

export const TradesTable: React.FC<TradesTableProps> = ({ trades }) => {
  const [page, setPage] = useState(0);
  const [sortDesc, setSortDesc] = useState(true);

  const sorted = [...trades].sort((a, b) =>
    sortDesc ? b.pnl_pct - a.pnl_pct : a.pnl_pct - b.pnl_pct
  );

  const totalPages = Math.ceil(sorted.length / PAGE_SIZE);
  const paginated = sorted.slice(page * PAGE_SIZE, (page + 1) * PAGE_SIZE);

  return (
    <div>
      <div className="overflow-x-auto">
        <table className="w-full text-xs font-mono">
          <thead>
            <tr className="border-b border-border text-muted-foreground">
              <th className="text-left py-2 px-3 font-bold uppercase tracking-wider text-[10px]">
                #
              </th>
              <th className="text-left py-2 px-3 font-bold uppercase tracking-wider text-[10px]">
                Direction
              </th>
              <th className="text-left py-2 px-3 font-bold uppercase tracking-wider text-[10px]">
                Entry
              </th>
              <th className="text-left py-2 px-3 font-bold uppercase tracking-wider text-[10px]">
                Exit
              </th>
              <th
                className="text-right py-2 px-3 font-bold uppercase tracking-wider text-[10px] cursor-pointer select-none"
                onClick={() => setSortDesc(!sortDesc)}
              >
                <span className="inline-flex items-center gap-1">
                  P&L %
                  {sortDesc ? <ChevronDown className="w-3 h-3" /> : <ChevronUp className="w-3 h-3" />}
                </span>
              </th>
              <th className="text-left py-2 px-3 font-bold uppercase tracking-wider text-[10px]">
                Entry Time
              </th>
            </tr>
          </thead>
          <tbody>
            {paginated.map((trade, i) => {
              const isWin = trade.pnl_pct > 0;
              return (
                <tr
                  key={page * PAGE_SIZE + i}
                  className="border-b border-border/50 hover:bg-white/[0.02] transition-colors"
                >
                  <td className="py-2 px-3 text-muted-foreground">
                    {page * PAGE_SIZE + i + 1}
                  </td>
                  <td className="py-2 px-3">
                    <Badge
                      className={`text-[10px] font-bold ${
                        trade.direction === 'BUY'
                          ? 'bg-emerald-500/10 text-emerald-400'
                          : 'bg-rose-500/10 text-rose-400'
                      }`}
                    >
                      {trade.direction}
                    </Badge>
                  </td>
                  <td className="py-2 px-3 text-slate-300">
                    ${trade.entry_price.toFixed(2)}
                  </td>
                  <td className="py-2 px-3 text-slate-300">
                    {trade.exit_price != null ? `$${trade.exit_price.toFixed(2)}` : '-'}
                  </td>
                  <td
                    className={`py-2 px-3 text-right font-bold ${
                      isWin ? 'text-emerald-400' : 'text-rose-400'
                    }`}
                  >
                    {isWin ? '+' : ''}
                    {(trade.pnl_pct * 100).toFixed(2)}%
                  </td>
                  <td className="py-2 px-3 text-muted-foreground text-[10px]">
                    {trade.entry_time || '-'}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      {totalPages > 1 && (
        <div className="flex items-center justify-between mt-4 pt-3 border-t border-border">
          <span className="text-[10px] text-muted-foreground font-mono">
            Page {page + 1} of {totalPages}
          </span>
          <div className="flex gap-2">
            <button
              onClick={() => setPage(Math.max(0, page - 1))}
              disabled={page === 0}
              className="px-3 py-1 text-xs font-mono bg-black/20 border border-border rounded disabled:opacity-30 hover:bg-white/5 transition-colors"
            >
              Prev
            </button>
            <button
              onClick={() => setPage(Math.min(totalPages - 1, page + 1))}
              disabled={page >= totalPages - 1}
              className="px-3 py-1 text-xs font-mono bg-black/20 border border-border rounded disabled:opacity-30 hover:bg-white/5 transition-colors"
            >
              Next
            </button>
          </div>
        </div>
      )}
    </div>
  );
};
