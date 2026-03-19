"use client";

import { useEffect, useRef, useId, useState } from "react";

interface MermaidDiagramProps {
  code: string;
}

let mermaidInitialized = false;

async function initMermaid() {
  if (mermaidInitialized) return;
  const mermaid = (await import("mermaid")).default;
  mermaid.initialize({
    startOnLoad: false,
    theme: "dark",
    themeVariables: {
      primaryColor: "#6366f1",
      primaryTextColor: "#e2e8f0",
      primaryBorderColor: "#4f46e5",
      lineColor: "#475569",
      secondaryColor: "#1e1b4b",
      tertiaryColor: "#0f172a",
      background: "#0f172a",
      mainBkg: "#1e1b4b",
      nodeBorder: "#4f46e5",
      clusterBkg: "#1e1b4b",
      titleColor: "#e2e8f0",
      edgeLabelBackground: "#1e293b",
    },
    fontFamily: "ui-monospace, monospace",
    flowchart: { htmlLabels: true, curve: "basis" },
    sequence: { actorMargin: 50, mirrorActors: false },
  });
  mermaidInitialized = true;
}

export function MermaidDiagram({ code }: MermaidDiagramProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const uniqueId = useId().replace(/:/g, "_");
  const [svg, setSvg] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

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

  if (error) {
    return (
      <div className="my-4 rounded-lg border border-amber-800/50 bg-amber-950/20 p-4">
        <p className="mb-2 text-xs font-medium text-amber-400">
          Diagram render error
        </p>
        <pre className="overflow-x-auto text-xs text-slate-400">
          <code>{code.trim()}</code>
        </pre>
      </div>
    );
  }

  if (!svg) {
    return (
      <div className="my-4 flex h-48 items-center justify-center rounded-lg border border-slate-800 bg-slate-900/50">
        <div className="h-5 w-5 animate-spin rounded-full border-2 border-indigo-500 border-t-transparent" />
      </div>
    );
  }

  return (
    <div className="my-4 overflow-x-auto rounded-lg border border-slate-800 bg-slate-900/50 p-4">
      <div
        ref={containerRef}
        dangerouslySetInnerHTML={{ __html: svg }}
        className="flex justify-center [&_svg]:max-w-full"
      />
    </div>
  );
}
