'use client';

import React from 'react';
import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from 'recharts';

interface EquityCurveChartProps {
  data: number[];
}

export const EquityCurveChart: React.FC<EquityCurveChartProps> = ({ data }) => {
  const chartData = data.map((value, index) => ({
    index,
    equity: parseFloat((value * 100).toFixed(2)),
  }));

  const minEquity = Math.min(...chartData.map((d) => d.equity));
  const maxEquity = Math.max(...chartData.map((d) => d.equity));
  const padding = (maxEquity - minEquity) * 0.1 || 1;

  const finalEquity = chartData[chartData.length - 1]?.equity ?? 100;
  const isPositive = finalEquity >= 100;
  const strokeColor = isPositive ? '#34d399' : '#f43f5e';
  const fillColor = isPositive ? 'url(#greenGradient)' : 'url(#redGradient)';

  return (
    <div className="h-64 w-full">
      <ResponsiveContainer width="100%" height="100%">
        <AreaChart data={chartData} margin={{ top: 5, right: 5, left: 0, bottom: 5 }}>
          <defs>
            <linearGradient id="greenGradient" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="#34d399" stopOpacity={0.3} />
              <stop offset="100%" stopColor="#34d399" stopOpacity={0.0} />
            </linearGradient>
            <linearGradient id="redGradient" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="#f43f5e" stopOpacity={0.3} />
              <stop offset="100%" stopColor="#f43f5e" stopOpacity={0.0} />
            </linearGradient>
          </defs>
          <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
          <XAxis
            dataKey="index"
            tick={{ fontSize: 10, fill: '#64748b' }}
            tickLine={false}
            axisLine={{ stroke: '#334155' }}
          />
          <YAxis
            domain={[minEquity - padding, maxEquity + padding]}
            tick={{ fontSize: 10, fill: '#64748b' }}
            tickLine={false}
            axisLine={{ stroke: '#334155' }}
            tickFormatter={(v) => `${v.toFixed(0)}%`}
          />
          <Tooltip
            contentStyle={{
              backgroundColor: '#0f172a',
              border: '1px solid #334155',
              borderRadius: '8px',
              fontSize: '12px',
              fontFamily: 'monospace',
            }}
            labelFormatter={(idx) => `Candle #${idx}`}
            formatter={(value: number | undefined) => [`${(value ?? 0).toFixed(2)}%`, 'Equity']}
          />
          <Area
            type="monotone"
            dataKey="equity"
            stroke={strokeColor}
            strokeWidth={2}
            fill={fillColor}
            dot={false}
          />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  );
};
