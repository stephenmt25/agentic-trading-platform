import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import { Chart, type ChartSeries } from "./Chart";

/**
 * Critical-path tests per docs/design/04-component-specs/chart.md:
 *   - SVG-first render with role="img" + ariaLabel summary
 *   - tableFallback renders an sr-only data table for SR users
 *   - Legend appears when ≥2 series (auto)
 *   - Empty state shows the empty caption (no SVG paths)
 *   - Series tone tokens are bound (no hex literals leak)
 *   - Bar shape renders <rect>s, line shape renders <path>s
 */

beforeEach(() => {
  // jsdom doesn't ship ResizeObserver; the Chart uses it for responsive
  // width measurement. Stub a no-op so render doesn't throw.
  if (!(globalThis as { ResizeObserver?: unknown }).ResizeObserver) {
    (globalThis as { ResizeObserver: unknown }).ResizeObserver = class {
      observe = vi.fn();
      unobserve = vi.fn();
      disconnect = vi.fn();
    };
  }
});

const SINGLE_LINE: ChartSeries[] = [
  {
    id: "equity",
    label: "Equity",
    shape: "line",
    tone: "bid",
    data: Array.from({ length: 10 }, (_, i) => ({ x: i, y: 100 + i * 5 })),
  },
];

const TWO_LINES: ChartSeries[] = [
  {
    id: "run-a",
    label: "Run A",
    shape: "line",
    tone: "accent",
    data: Array.from({ length: 5 }, (_, i) => ({ x: i, y: 100 + i })),
  },
  {
    id: "run-b",
    label: "Run B",
    shape: "line",
    tone: "neutral",
    stroke: "dashed",
    data: Array.from({ length: 5 }, (_, i) => ({ x: i, y: 110 - i })),
  },
];

describe("Chart — critical-path", () => {
  it("renders SVG with role='img' and the supplied aria-label", () => {
    render(
      <Chart
        series={SINGLE_LINE}
        ariaLabel="Equity curve from 100 to 145 over 10 samples."
      />
    );
    const region = screen.getByRole("img");
    expect(region).toHaveAttribute(
      "aria-label",
      "Equity curve from 100 to 145 over 10 samples."
    );
  });

  it("renders a line path for line-shape series", () => {
    const { container } = render(
      <Chart series={SINGLE_LINE} ariaLabel="line series" />
    );
    const paths = container.querySelectorAll("path");
    // At least one path with M...L drawing.
    const lines = Array.from(paths).filter((p) =>
      (p.getAttribute("d") ?? "").includes("L")
    );
    expect(lines.length).toBeGreaterThanOrEqual(1);
  });

  it("renders rects for bar-shape series", () => {
    const { container } = render(
      <Chart
        ariaLabel="bars"
        series={[
          {
            id: "b",
            shape: "bar",
            tone: "auto",
            data: [
              { x: 0, y: 1 },
              { x: 1, y: -1 },
              { x: 2, y: 2 },
            ],
          },
        ]}
      />
    );
    const rects = container.querySelectorAll("rect");
    // At least one rect per bar (plus the clipPath rect = 1).
    expect(rects.length).toBeGreaterThanOrEqual(4);
  });

  it("auto-shows legend when ≥2 series", () => {
    render(<Chart series={TWO_LINES} ariaLabel="two-series" />);
    expect(screen.getByText("Run A")).toBeInTheDocument();
    expect(screen.getByText("Run B")).toBeInTheDocument();
  });

  it("hides legend for single-series default", () => {
    render(
      <Chart
        series={SINGLE_LINE}
        ariaLabel="single"
        // legend defaults to "auto" — should not show for 1 series
      />
    );
    // Equity label should not be rendered as legend (no header at all)
    expect(screen.queryByText("Equity")).not.toBeInTheDocument();
  });

  it("renders empty caption when no series data", () => {
    render(
      <Chart
        series={[{ id: "e", data: [] }]}
        ariaLabel="empty"
        emptyMessage="No samples"
      />
    );
    expect(screen.getByText("No samples")).toBeInTheDocument();
  });

  it("renders error overlay when error prop set", () => {
    render(
      <Chart series={SINGLE_LINE} ariaLabel="errored" error="upstream timeout" />
    );
    expect(screen.getByText("upstream timeout")).toBeInTheDocument();
  });

  it("renders sr-only table fallback when tableFallback=true", () => {
    const { container } = render(
      <Chart
        series={SINGLE_LINE}
        ariaLabel="with table"
        tableFallback
      />
    );
    const table = container.querySelector("table.sr-only");
    expect(table).not.toBeNull();
    // Caption echoes the ariaLabel
    expect(table?.querySelector("caption")?.textContent).toBe("with table");
    // 10 data rows
    const dataRows = table?.querySelectorAll("tbody tr");
    expect(dataRows?.length).toBe(10);
  });

  it("does not render sr-only table when tableFallback omitted", () => {
    const { container } = render(
      <Chart series={SINGLE_LINE} ariaLabel="no table" />
    );
    expect(container.querySelector("table.sr-only")).toBeNull();
  });

  it("uses CSS var color tokens for series stroke (no hex literals)", () => {
    const { container } = render(
      <Chart series={SINGLE_LINE} ariaLabel="tokens" />
    );
    const paths = container.querySelectorAll("path");
    const strokes = Array.from(paths)
      .map((p) => p.getAttribute("stroke"))
      .filter((s): s is string => Boolean(s));
    // Every stroke should reference a CSS custom property — no literal hex
    expect(strokes.length).toBeGreaterThan(0);
    for (const s of strokes) {
      expect(s).toMatch(/var\(--color-/);
    }
  });

  it("is keyboard-focusable when tooltip is enabled (default)", () => {
    render(<Chart series={SINGLE_LINE} ariaLabel="focusable" />);
    const region = screen.getByRole("img");
    expect(region.getAttribute("tabindex")).toBe("0");
  });

  it("is not focusable when tooltip='none'", () => {
    render(
      <Chart series={SINGLE_LINE} ariaLabel="static" tooltip="none" />
    );
    const region = screen.getByRole("img");
    expect(region.getAttribute("tabindex")).toBe("-1");
  });

  it("downsamples series longer than the cap", () => {
    const long = Array.from({ length: 5000 }, (_, i) => ({ x: i, y: i * 0.1 }));
    const { container } = render(
      <Chart
        series={[{ id: "long", data: long }]}
        ariaLabel="downsampled"
        downsample={500}
        tableFallback
      />
    );
    const dataRows = container.querySelectorAll("table.sr-only tbody tr");
    // Bucketed min/max should yield strictly fewer rows than the input
    expect(dataRows.length).toBeLessThan(5000);
    expect(dataRows.length).toBeGreaterThan(0);
  });
});
