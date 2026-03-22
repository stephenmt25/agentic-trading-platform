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

  if (trades.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center py-12 text-center">
        <p className="text-sm text-muted-foreground">No trades found</p>
      </div>
    );
  }

  return (
    <div>
      <div className="overflow-x-auto">
        <table className="w-full text-sm font-mono tabular-nums">
          <thead>
            <tr className="border-b border-border">
              <th className="text-left px-4 py-2.5 text-xs uppercase text-muted-foreground font-medium">
                #
              </th>
              <th className="text-left px-4 py-2.5 text-xs uppercase text-muted-foreground font-medium">
                Direction
              </th>
              <th className="text-right px-4 py-2.5 text-xs uppercase text-muted-foreground font-medium">
                Entry
              </th>
              <th className="text-right px-4 py-2.5 text-xs uppercase text-muted-foreground font-medium">
                Exit
              </th>
              <th
                className="text-right px-4 py-2.5 text-xs uppercase text-muted-foreground font-medium cursor-pointer select-none"
                onClick={() => setSortDesc(!sortDesc)}
              >
                <span className="inline-flex items-center gap-1">
                  P&L %
                  {sortDesc ? <ChevronDown className="w-3 h-3" /> : <ChevronUp className="w-3 h-3" />}
                </span>
              </th>
              <th className="text-left px-4 py-2.5 text-xs uppercase text-muted-foreground font-medium">
                Entry Time
              </th>
            </tr>
          </thead>
          <tbody>
            {paginated.map((trade, i) => {
              const isWin = trade.pnl_pct > 0;
              const isZero = trade.pnl_pct === 0;
              return (
                <tr
                  key={page * PAGE_SIZE + i}
                  className="border-b border-border/50 hover:bg-accent/50 transition-colors"
                >
                  <td className="px-4 py-2.5 text-muted-foreground">
                    {page * PAGE_SIZE + i + 1}
                  </td>
                  <td className="px-4 py-2.5">
                    <span
                      className={`text-xs font-medium ${
                        trade.direction === 'BUY'
                          ? 'text-emerald-500'
                          : 'text-red-500'
                      }`}
                    >
                      {trade.direction}
                    </span>
                  </td>
                  <td className="px-4 py-2.5 text-right text-foreground">
                    ${trade.entry_price.toFixed(2)}
                  </td>
                  <td className="px-4 py-2.5 text-right text-foreground">
                    {trade.exit_price != null ? `$${trade.exit_price.toFixed(2)}` : <span className="text-muted-foreground">--</span>}
                  </td>
                  <td
                    className={`px-4 py-2.5 text-right font-medium ${
                      isZero ? 'text-muted-foreground' : isWin ? 'text-emerald-500' : 'text-red-500'
                    }`}
                  >
                    {isWin ? '+' : ''}
                    {(trade.pnl_pct * 100).toFixed(2)}%
                  </td>
                  <td className="px-4 py-2.5 text-muted-foreground text-xs truncate max-w-[140px]">
                    {trade.entry_time || '--'}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      {totalPages > 1 && (
        <div className="flex items-center justify-between mt-4 pt-3 border-t border-border">
          <span className="text-xs text-muted-foreground font-mono tabular-nums">
            Page {page + 1} of {totalPages}
          </span>
          <div className="flex gap-2">
            <button
              onClick={() => setPage(Math.max(0, page - 1))}
              disabled={page === 0}
              className="px-3 py-2 text-xs font-mono border border-border rounded-md disabled:opacity-30 hover:bg-accent transition-colors min-h-[44px] focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary"
            >
              Prev
            </button>
            <button
              onClick={() => setPage(Math.min(totalPages - 1, page + 1))}
              disabled={page >= totalPages - 1}
              className="px-3 py-2 text-xs font-mono border border-border rounded-md disabled:opacity-30 hover:bg-accent transition-colors min-h-[44px] focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary"
            >
              Next
            </button>
          </div>
        </div>
      )}
    </div>
  );
};
