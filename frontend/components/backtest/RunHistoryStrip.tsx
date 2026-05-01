'use client';

import React, { memo, useState } from 'react';
import { StoredRun } from '../../lib/types';
import { Pin, PinOff, Copy, Trash2, Pencil, Check, X, Trash } from 'lucide-react';

interface RunHistoryStripProps {
  runs: StoredRun[];
  activeRunId: string | null;
  onSelect: (id: string) => void;
  onToggleVisible: (id: string) => void;
  onTogglePinned: (id: string) => void;
  onClone: (id: string) => void;
  onDelete: (id: string) => void;
  onRename: (id: string, label: string) => void;
  onClearUnpinned: () => void;
}

export const RunHistoryStrip: React.FC<RunHistoryStripProps> = ({
  runs,
  activeRunId,
  onSelect,
  onToggleVisible,
  onTogglePinned,
  onClone,
  onDelete,
  onRename,
  onClearUnpinned,
}) => {
  if (runs.length === 0) return null;

  const hasUnpinned = runs.some((r) => !r.pinned);

  return (
    <section>
      <div className="flex items-center justify-between mb-2">
        <h2 className="uppercase text-xs font-semibold text-muted-foreground tracking-wider">
          Run History ({runs.length})
        </h2>
        {hasUnpinned && (
          <button
            onClick={onClearUnpinned}
            className="flex items-center gap-1 text-xs text-muted-foreground hover:text-foreground transition-colors"
          >
            <Trash className="w-3 h-3" />
            Clear unpinned
          </button>
        )}
      </div>
      <div className="flex gap-3 overflow-x-auto pb-2 -mx-1 px-1">
        {runs.map((run) => (
          <RunCard
            key={run.id}
            run={run}
            active={run.id === activeRunId}
            onSelect={() => onSelect(run.id)}
            onToggleVisible={() => onToggleVisible(run.id)}
            onTogglePinned={() => onTogglePinned(run.id)}
            onClone={() => onClone(run.id)}
            onDelete={() => onDelete(run.id)}
            onRename={(label) => onRename(run.id, label)}
          />
        ))}
      </div>
    </section>
  );
};

interface RunCardProps {
  run: StoredRun;
  active: boolean;
  onSelect: () => void;
  onToggleVisible: () => void;
  onTogglePinned: () => void;
  onClone: () => void;
  onDelete: () => void;
  onRename: (label: string) => void;
}

const RunCardInner: React.FC<RunCardProps> = ({
  run,
  active,
  onSelect,
  onToggleVisible,
  onTogglePinned,
  onClone,
  onDelete,
  onRename,
}) => {
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState(run.label);

  const winPct = (run.result.win_rate * 100).toFixed(0);
  const sharpe = run.result.sharpe.toFixed(2);
  const avgRet = (run.result.avg_return * 100).toFixed(1);
  const avgPositive = run.result.avg_return >= 0;

  const commitRename = () => {
    const trimmed = draft.trim();
    if (trimmed && trimmed !== run.label) onRename(trimmed);
    else setDraft(run.label);
    setEditing(false);
  };

  const cancelRename = () => {
    setDraft(run.label);
    setEditing(false);
  };

  return (
    <div
      className={`shrink-0 w-[220px] border rounded-md p-3 transition-colors cursor-pointer ${
        active ? 'border-primary bg-accent/40' : 'border-border hover:bg-accent/20'
      }`}
      onClick={onSelect}
    >
      <div className="flex items-center gap-2 mb-2" onClick={(e) => e.stopPropagation()}>
        <label
          className="flex items-center justify-center p-1 -m-1 cursor-pointer shrink-0"
          title="Show on equity chart"
        >
          <input
            type="checkbox"
            checked={run.visible}
            onChange={onToggleVisible}
            className="w-5 h-5 accent-primary cursor-pointer"
          />
        </label>
        <span
          className="w-2.5 h-2.5 rounded-full shrink-0"
          style={{ backgroundColor: run.color }}
        />
        {editing ? (
          <div className="flex items-center gap-1 flex-1 min-w-0">
            <input
              value={draft}
              onChange={(e) => setDraft(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === 'Enter') commitRename();
                if (e.key === 'Escape') cancelRename();
              }}
              autoFocus
              className="flex-1 min-w-0 text-xs font-mono bg-background border border-border rounded px-1.5 py-0.5 text-foreground focus-visible:outline-1 focus-visible:outline-primary"
            />
            <button onClick={commitRename} className="text-emerald-500 hover:text-emerald-400">
              <Check className="w-3 h-3" />
            </button>
            <button onClick={cancelRename} className="text-muted-foreground hover:text-foreground">
              <X className="w-3 h-3" />
            </button>
          </div>
        ) : (
          <span
            className="text-xs font-mono font-medium text-foreground truncate flex-1"
            title={run.label}
          >
            {run.label}
          </span>
        )}
      </div>

      <div className="grid grid-cols-3 gap-1 text-[10px] font-mono tabular-nums mb-2">
        <div>
          <div className="text-muted-foreground uppercase">Sharpe</div>
          <div className="text-foreground">{sharpe}</div>
        </div>
        <div>
          <div className="text-muted-foreground uppercase">Win</div>
          <div className="text-foreground">{winPct}%</div>
        </div>
        <div>
          <div className="text-muted-foreground uppercase">Avg</div>
          <div className={avgPositive ? 'text-emerald-500' : 'text-red-500'}>
            {avgPositive ? '+' : ''}
            {avgRet}%
          </div>
        </div>
      </div>

      <div className="text-[10px] text-muted-foreground font-mono tabular-nums mb-2 truncate">
        {run.config.symbol} · {run.config.timeframe} · {run.result.total_trades} tr
      </div>

      <div
        className="flex items-center justify-end gap-1"
        onClick={(e) => e.stopPropagation()}
      >
        {!editing && (
          <button
            onClick={() => setEditing(true)}
            className="p-1 text-muted-foreground hover:text-foreground transition-colors"
            title="Rename"
          >
            <Pencil className="w-3 h-3" />
          </button>
        )}
        <button
          onClick={onTogglePinned}
          className={`p-1 transition-colors ${
            run.pinned ? 'text-amber-500' : 'text-muted-foreground hover:text-foreground'
          }`}
          title={run.pinned ? 'Unpin' : 'Pin'}
        >
          {run.pinned ? <PinOff className="w-3 h-3" /> : <Pin className="w-3 h-3" />}
        </button>
        <button
          onClick={onClone}
          className="p-1 text-muted-foreground hover:text-foreground transition-colors"
          title="Clone params into form"
        >
          <Copy className="w-3 h-3" />
        </button>
        <button
          onClick={onDelete}
          className="p-1 text-muted-foreground hover:text-red-500 transition-colors"
          title="Delete"
        >
          <Trash2 className="w-3 h-3" />
        </button>
      </div>
    </div>
  );
};

const RunCard = memo(RunCardInner);
