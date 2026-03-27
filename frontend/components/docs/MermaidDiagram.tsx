"use client";

import { useCallback, useEffect, useId, useRef, useState } from "react";

interface MermaidDiagramProps {
  code: string;
}

let mermaidInitialized = false;

async function initMermaid() {
  if (mermaidInitialized) return;
  const mermaid = (await import("mermaid")).default;
  mermaid.initialize({
    startOnLoad: false,
    theme: "default",
    themeVariables: {
      primaryColor: "#dbeafe",
      primaryTextColor: "#1e293b",
      primaryBorderColor: "#3b82f6",
      lineColor: "#94a3b8",
      secondaryColor: "#f1f5f9",
      tertiaryColor: "#e2e8f0",
      background: "#ffffff",
      mainBkg: "#dbeafe",
      nodeBorder: "#3b82f6",
      clusterBkg: "#f8fafc",
      clusterBorder: "#cbd5e1",
      titleColor: "#0f172a",
      edgeLabelBackground: "#ffffff",
      textColor: "#1e293b",
      nodeTextColor: "#1e293b",
      labelTextColor: "#334155",
      loopTextColor: "#334155",
      noteBkgColor: "#fef9c3",
      noteTextColor: "#1e293b",
      actorTextColor: "#1e293b",
      signalTextColor: "#1e293b",
      fontSize: "16px",
    },
    fontFamily: "ui-sans-serif, system-ui, sans-serif",
    fontSize: 16,
    flowchart: { htmlLabels: true, curve: "basis" },
    sequence: { actorMargin: 50, mirrorActors: false },
    c4: { c4ShapeMargin: 20, c4ShapePadding: 10 },
  });
  mermaidInitialized = true;
}

const MIN_SCALE = 0.25;
const MAX_SCALE = 3;
const ZOOM_STEP = 0.25;

function DiagramControls({
  scale,
  onZoomIn,
  onZoomOut,
  onReset,
  onExpand,
  onCollapse,
  isExpanded,
  className,
}: {
  scale: number;
  onZoomIn: () => void;
  onZoomOut: () => void;
  onReset: () => void;
  onExpand?: () => void;
  onCollapse?: () => void;
  isExpanded: boolean;
  className?: string;
}) {
  return (
    <div className={`flex items-center gap-1 rounded-md border border-slate-200 bg-white/90 backdrop-blur-sm px-1 py-0.5 shadow-sm ${className ?? ""}`}>
      <button
        onClick={onZoomOut}
        className="px-2 py-0.5 text-sm text-slate-600 hover:text-slate-900 hover:bg-slate-100 rounded"
        aria-label="Zoom out"
      >
        −
      </button>
      <span className="text-xs text-slate-500 min-w-[3rem] text-center tabular-nums">
        {Math.round(scale * 100)}%
      </span>
      <button
        onClick={onZoomIn}
        className="px-2 py-0.5 text-sm text-slate-600 hover:text-slate-900 hover:bg-slate-100 rounded"
        aria-label="Zoom in"
      >
        +
      </button>
      <div className="w-px h-4 bg-slate-200 mx-0.5" />
      <button
        onClick={onReset}
        className="px-2 py-0.5 text-xs text-slate-500 hover:text-slate-900 hover:bg-slate-100 rounded"
        aria-label="Reset zoom"
      >
        Reset
      </button>
      <div className="w-px h-4 bg-slate-200 mx-0.5" />
      {isExpanded ? (
        <button
          onClick={onCollapse}
          className="px-2 py-0.5 text-xs text-slate-500 hover:text-slate-900 hover:bg-slate-100 rounded"
          aria-label="Close fullscreen"
        >
          Collapse
        </button>
      ) : (
        <button
          onClick={onExpand}
          className="px-2 py-0.5 text-xs text-slate-500 hover:text-slate-900 hover:bg-slate-100 rounded"
          aria-label="Expand to fullscreen"
        >
          Expand
        </button>
      )}
    </div>
  );
}

function useZoomPan() {
  const [scale, setScale] = useState(1);
  const [position, setPosition] = useState({ x: 0, y: 0 });
  const [isPanning, setIsPanning] = useState(false);
  const panStart = useRef({ x: 0, y: 0 });

  const clampScale = (s: number) => Math.min(MAX_SCALE, Math.max(MIN_SCALE, s));

  const handleMouseDown = useCallback((e: React.MouseEvent) => {
    if (e.button !== 0) return;
    setIsPanning(true);
    panStart.current = { x: e.clientX - position.x, y: e.clientY - position.y };
  }, [position]);

  const handleMouseMove = useCallback((e: React.MouseEvent) => {
    if (!isPanning) return;
    setPosition({
      x: e.clientX - panStart.current.x,
      y: e.clientY - panStart.current.y,
    });
  }, [isPanning]);

  const handleMouseUp = useCallback(() => {
    setIsPanning(false);
  }, []);

  const resetView = useCallback(() => {
    setScale(1);
    setPosition({ x: 0, y: 0 });
  }, []);

  const zoomIn = useCallback(() => {
    setScale((prev) => clampScale(prev + ZOOM_STEP));
  }, []);

  const zoomOut = useCallback(() => {
    setScale((prev) => clampScale(prev - ZOOM_STEP));
  }, []);

  return {
    scale, position, isPanning,
    handleMouseDown, handleMouseMove, handleMouseUp,
    resetView, zoomIn, zoomOut,
  };
}

function DiagramViewport({
  svg,
  zoom,
}: {
  svg: string;
  zoom: ReturnType<typeof useZoomPan>;
}) {
  return (
    <div
      className="overflow-hidden p-4 h-full"
      style={{ cursor: zoom.isPanning ? "grabbing" : "grab" }}
      onMouseDown={zoom.handleMouseDown}
      onMouseMove={zoom.handleMouseMove}
      onMouseUp={zoom.handleMouseUp}
      onMouseLeave={zoom.handleMouseUp}
      onDoubleClick={zoom.resetView}
    >
      <div
        style={{
          transform: `translate(${zoom.position.x}px, ${zoom.position.y}px) scale(${zoom.scale})`,
          transformOrigin: "0 0",
          transition: zoom.isPanning ? "none" : "transform 0.1s ease-out",
        }}
      >
        <div
          dangerouslySetInnerHTML={{ __html: svg }}
          className="flex justify-center [&_svg]:max-w-full [&_svg]:min-h-[300px]"
        />
      </div>
    </div>
  );
}

export function MermaidDiagram({ code }: MermaidDiagramProps) {
  const uniqueId = useId().replace(/:/g, "_");
  const [svg, setSvg] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [isExpanded, setIsExpanded] = useState(false);

  const inlineZoom = useZoomPan();
  const expandedZoom = useZoomPan();

  useEffect(() => {
    let cancelled = false;

    async function render() {
      try {
        await initMermaid();
        const mermaid = (await import("mermaid")).default;
        const id = `mermaid${uniqueId}`;
        const { svg: rendered } = await mermaid.render(id, code.trim());
        if (!cancelled) {
          setSvg(rendered);
          setError(null);
        }
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : "Mermaid rendering failed");
        }
      }
    }

    render();
    return () => {
      cancelled = true;
    };
  }, [code, uniqueId]);

  // Close expanded view on Escape
  useEffect(() => {
    if (!isExpanded) return;
    function handleKeyDown(e: KeyboardEvent) {
      if (e.key === "Escape") setIsExpanded(false);
    }
    document.addEventListener("keydown", handleKeyDown);
    return () => document.removeEventListener("keydown", handleKeyDown);
  }, [isExpanded]);

  // Lock body scroll when expanded
  useEffect(() => {
    if (isExpanded) {
      document.body.style.overflow = "hidden";
    } else {
      document.body.style.overflow = "";
    }
    return () => { document.body.style.overflow = ""; };
  }, [isExpanded]);

  if (error) {
    return (
      <div className="my-4 rounded-md border border-amber-300 bg-amber-50 p-4">
        <p className="mb-2 text-xs font-medium text-amber-700">
          Diagram render error
        </p>
        <pre className="overflow-x-auto text-xs text-amber-900">
          <code>{code.trim()}</code>
        </pre>
      </div>
    );
  }

  if (!svg) {
    return (
      <div className="my-4 h-48 rounded-md border border-slate-200 bg-slate-100 animate-pulse" />
    );
  }

  return (
    <>
      {/* Inline view */}
      <div className="my-4 rounded-md border border-slate-200 bg-white relative group">
        <DiagramControls
          scale={inlineZoom.scale}
          onZoomIn={inlineZoom.zoomIn}
          onZoomOut={inlineZoom.zoomOut}
          onReset={inlineZoom.resetView}
          onExpand={() => { expandedZoom.resetView(); setIsExpanded(true); }}
          isExpanded={false}
          className="absolute top-2 right-2 z-10 opacity-0 group-hover:opacity-100 transition-opacity"
        />
        <DiagramViewport svg={svg} zoom={inlineZoom} />
      </div>

      {/* Fullscreen overlay */}
      {isExpanded && (
        <div className="fixed inset-0 z-50 bg-black/60 backdrop-blur-sm flex items-center justify-center">
          <div className="absolute inset-4 bg-white rounded-lg shadow-2xl flex flex-col overflow-hidden">
            <div className="flex items-center justify-between px-4 py-2 border-b border-slate-200 bg-slate-50 shrink-0">
              <span className="text-sm font-medium text-slate-700">Diagram</span>
              <DiagramControls
                scale={expandedZoom.scale}
                onZoomIn={expandedZoom.zoomIn}
                onZoomOut={expandedZoom.zoomOut}
                onReset={expandedZoom.resetView}
                onCollapse={() => setIsExpanded(false)}
                isExpanded={true}
              />
            </div>
            <div className="flex-1 min-h-0">
              <DiagramViewport svg={svg} zoom={expandedZoom} />
            </div>
          </div>
        </div>
      )}
    </>
  );
}
