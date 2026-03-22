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
      primaryColor: "#3b82f6",
      primaryTextColor: "#e2e8f0",
      primaryBorderColor: "#2563eb",
      lineColor: "#3f3f46",
      secondaryColor: "#1c1c22",
      tertiaryColor: "#111116",
      background: "#111116",
      mainBkg: "#1c1c22",
      nodeBorder: "#2563eb",
      clusterBkg: "#1c1c22",
      titleColor: "#e2e8f0",
      edgeLabelBackground: "#1c1c22",
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
      <div className="my-4 rounded-md border border-amber-500/30 p-4">
        <p className="mb-2 text-xs font-medium text-amber-500">
          Diagram render error
        </p>
        <pre className="overflow-x-auto text-xs text-muted-foreground">
          <code>{code.trim()}</code>
        </pre>
      </div>
    );
  }

  if (!svg) {
    return (
      <div className="my-4 h-48 rounded-md border border-border bg-accent animate-pulse" />
    );
  }

  return (
    <div className="my-4 overflow-x-auto rounded-md border border-border bg-card p-4">
      <div
        ref={containerRef}
        dangerouslySetInnerHTML={{ __html: svg }}
        className="flex justify-center [&_svg]:max-w-full"
      />
    </div>
  );
}
