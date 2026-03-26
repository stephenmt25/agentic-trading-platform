"use client";

import { useEffect, useId, useState } from "react";

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

export function MermaidDiagram({ code }: MermaidDiagramProps) {
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
    <div className="my-4 overflow-x-auto rounded-md border border-slate-200 bg-white p-4">
      <div
        dangerouslySetInnerHTML={{ __html: svg }}
        className="flex justify-center [&_svg]:max-w-full [&_svg]:min-h-[300px]"
      />
    </div>
  );
}
