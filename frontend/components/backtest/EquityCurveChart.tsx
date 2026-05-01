'use client';

import React, { memo, useMemo } from 'react';
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Legend,
} from 'recharts';
import { lttb } from '@/lib/chart/downsample';

export interface EquitySeries {
  id: string;
  label: string;
  color: string;
  data: number[];
}

interface EquityCurveChartProps {
  series: EquitySeries[];
  activeId?: string | null;
}

const DISPLAY_POINTS = 500;

const EquityCurveChartInner: React.FC<EquityCurveChartProps> = ({ series, activeId }) => {
  // Downsample each series independently — LTTB preserves peaks/troughs while
  // collapsing thousands of candles into ~500 display points. Chart renders in ms.
  const displaySeries = useMemo(
    () => series.map((s) => ({ ...s, data: lttb(s.data, DISPLAY_POINTS) })),
    [series]
  );

  const chartData = useMemo(() => {
    const maxLen = displaySeries.reduce((m, s) => Math.max(m, s.data.length), 0);
    return Array.from({ length: maxLen }, (_, i) => {
      const row: Record<string, number> = { index: i };
      for (const s of displaySeries) {
        const v = s.data[i];
        if (v != null) row[s.id] = parseFloat((v * 100).toFixed(2));
      }
      return row;
    });
  }, [displaySeries]);

  const { minEquity, maxEquity } = useMemo(() => {
    const all = displaySeries.flatMap((s) => s.data.map((v) => v * 100));
    return {
      minEquity: all.length ? Math.min(...all) : 100,
      maxEquity: all.length ? Math.max(...all) : 100,
    };
  }, [displaySeries]);

  if (series.length === 0) return null;

  const padding = (maxEquity - minEquity) * 0.1 || 1;
  const hasActive = Boolean(activeId);

  return (
    <div className="h-64 w-full">
      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={chartData} margin={{ top: 5, right: 5, left: 0, bottom: 5 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.06)" />
          <XAxis
            dataKey="index"
            tick={{ fontSize: 10, fill: 'rgba(255,255,255,0.35)' }}
            tickLine={false}
            axisLine={{ stroke: 'rgba(255,255,255,0.08)' }}
          />
          <YAxis
            domain={[minEquity - padding, maxEquity + padding]}
            tick={{ fontSize: 10, fill: 'rgba(255,255,255,0.35)' }}
            tickLine={false}
            axisLine={{ stroke: 'rgba(255,255,255,0.08)' }}
            tickFormatter={(v) => `${v.toFixed(0)}%`}
          />
          <Tooltip
            contentStyle={{
              backgroundColor: 'rgba(15,18,25,0.95)',
              border: '1px solid rgba(255,255,255,0.08)',
              borderRadius: '6px',
              fontSize: '13px',
              fontFamily: 'monospace',
            }}
            labelFormatter={(idx) => `Candle #${idx}`}
            formatter={(value: number | undefined, name: string) => {
              const s = series.find((x) => x.id === name);
              return [`${(value ?? 0).toFixed(2)}%`, s?.label ?? name];
            }}
          />
          {series.length > 1 && (
            <Legend
              wrapperStyle={{ fontSize: '11px', fontFamily: 'monospace' }}
              formatter={(value) => series.find((s) => s.id === value)?.label ?? value}
            />
          )}
          {series.map((s) => {
            const isActive = hasActive && s.id === activeId;
            return (
              <Line
                key={s.id}
                type="monotone"
                dataKey={s.id}
                name={s.id}
                stroke={s.color}
                strokeWidth={isActive ? 3 : hasActive ? 1.5 : 2}
                strokeOpacity={hasActive && !isActive ? 0.35 : 1}
                dot={false}
                connectNulls
                isAnimationActive={false}
              />
            );
          })}
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
};

export const EquityCurveChart = memo(EquityCurveChartInner);
