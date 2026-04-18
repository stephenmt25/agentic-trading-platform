"use client";

import { useEffect, useRef, useCallback } from "react";
import {
  createChart,
  CandlestickSeries,
  HistogramSeries,
  type IChartApi,
  type ISeriesApi,
  type CandlestickData,
  type Time,
  ColorType,
} from "lightweight-charts";
import { useAnalysisStore } from "@/lib/stores/analysisStore";

interface CandleData {
  time: number;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
}

interface PriceChartProps {
  data: CandleData[];
  height?: number;
}

export function PriceChart({ data, height = 400 }: PriceChartProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const candleSeriesRef = useRef<ISeriesApi<"Candlestick"> | null>(null);
  const volumeSeriesRef = useRef<ISeriesApi<"Histogram"> | null>(null);
  const dataRef = useRef<CandleData[]>([]);
  const mirroringRef = useRef(false);

  const setHoveredTime = useAnalysisStore((s) => s.setHoveredTime);
  const setVisibleRange = useAnalysisStore((s) => s.setVisibleRange);
  const hoveredTime = useAnalysisStore((s) => s.hoveredTime);
  const hoverSource = useAnalysisStore((s) => s.hoverSource);

  const initChart = useCallback(() => {
    if (!containerRef.current) return;

    if (chartRef.current) {
      chartRef.current.remove();
      chartRef.current = null;
    }

    const chart = createChart(containerRef.current, {
      layout: {
        background: { type: ColorType.Solid, color: "transparent" },
        textColor: "#9ca3af",
        fontFamily: "'IBM Plex Mono', monospace",
        fontSize: 11,
      },
      grid: {
        vertLines: { color: "rgba(255, 255, 255, 0.04)" },
        horzLines: { color: "rgba(255, 255, 255, 0.04)" },
      },
      crosshair: {
        mode: 0,
        vertLine: { color: "rgba(255, 255, 255, 0.15)", width: 1, style: 2 },
        horzLine: { color: "rgba(255, 255, 255, 0.15)", width: 1, style: 2 },
      },
      rightPriceScale: {
        borderColor: "rgba(255, 255, 255, 0.1)",
        scaleMargins: { top: 0.1, bottom: 0.2 },
      },
      timeScale: {
        borderColor: "rgba(255, 255, 255, 0.1)",
        timeVisible: true,
        secondsVisible: false,
      },
      handleScroll: { vertTouchDrag: false },
    });

    const candleSeries = chart.addSeries(CandlestickSeries, {
      upColor: "#22c55e",
      downColor: "#ef4444",
      borderDownColor: "#ef4444",
      borderUpColor: "#22c55e",
      wickDownColor: "#ef4444",
      wickUpColor: "#22c55e",
    });

    const volumeSeries = chart.addSeries(HistogramSeries, {
      priceFormat: { type: "volume" },
      priceScaleId: "volume",
    });

    chart.priceScale("volume").applyOptions({
      scaleMargins: { top: 0.85, bottom: 0 },
    });

    chartRef.current = chart;
    candleSeriesRef.current = candleSeries;
    volumeSeriesRef.current = volumeSeries;

    chart.subscribeCrosshairMove((param) => {
      const { hoverSource: currentSource, hoveredTime: currentTime } =
        useAnalysisStore.getState();

      if (param.time == null) {
        // Only clear when we were the driver; don't clobber "score" as the
        // source after a clearCrosshairPosition echo.
        if (currentSource === "price") setHoveredTime(null, null);
        return;
      }

      const time = param.time as number;
      // Echo from our own setCrosshairPosition call — skip so the source
      // stays "score" and we don't ping-pong.
      if (currentSource === "score" && currentTime === time) return;

      setHoveredTime(time, "price");
    });

    chart.timeScale().subscribeVisibleTimeRangeChange((range) => {
      if (range) {
        setVisibleRange({
          from: range.from as number,
          to: range.to as number,
        });
      } else {
        setVisibleRange(null);
      }
    });

    const observer = new ResizeObserver((entries) => {
      for (const entry of entries) {
        chart.applyOptions({ width: entry.contentRect.width });
      }
    });
    observer.observe(containerRef.current);

    return () => observer.disconnect();
  }, [setHoveredTime, setVisibleRange]);

  useEffect(() => {
    const cleanup = initChart();
    return () => {
      cleanup?.();
      if (chartRef.current) {
        chartRef.current.remove();
        chartRef.current = null;
      }
    };
  }, [initChart]);

  useEffect(() => {
    if (!candleSeriesRef.current || !volumeSeriesRef.current || !data.length)
      return;

    dataRef.current = data;

    const candleData: CandlestickData<Time>[] = data.map((d) => ({
      time: d.time as Time,
      open: d.open,
      high: d.high,
      low: d.low,
      close: d.close,
    }));

    const volumeData = data.map((d) => ({
      time: d.time as Time,
      value: d.volume,
      color:
        d.close >= d.open
          ? "rgba(34, 197, 94, 0.3)"
          : "rgba(239, 68, 68, 0.3)",
    }));

    candleSeriesRef.current.setData(candleData);
    volumeSeriesRef.current.setData(volumeData);
  }, [data]);

  // Mirror external hover (from score chart) onto the price chart's crosshair
  useEffect(() => {
    if (!chartRef.current || !candleSeriesRef.current) return;

    if (hoverSource === "score" && hoveredTime != null) {
      const candles = dataRef.current;
      if (!candles.length) return;

      let nearest = candles[0];
      let bestDiff = Math.abs(nearest.time - hoveredTime);
      for (const c of candles) {
        const diff = Math.abs(c.time - hoveredTime);
        if (diff < bestDiff) {
          nearest = c;
          bestDiff = diff;
        }
      }

      chartRef.current.setCrosshairPosition(
        nearest.close,
        hoveredTime as Time,
        candleSeriesRef.current,
      );
      mirroringRef.current = true;
    } else if (mirroringRef.current) {
      // Score chart released hover — clear the mirrored crosshair.
      chartRef.current.clearCrosshairPosition();
      mirroringRef.current = false;
    }
  }, [hoveredTime, hoverSource]);

  return (
    <div
      ref={containerRef}
      style={{ height }}
      className="w-full rounded-lg overflow-hidden"
    />
  );
}
