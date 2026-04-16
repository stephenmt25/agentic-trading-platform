export interface DocEntry {
  slug: string;
  label: string;
}

export interface DocSection {
  title: string;
  docs: DocEntry[];
}

export const DOC_SECTIONS: DocSection[] = [
  {
    title: "Architecture & Design",
    docs: [
      { slug: "architecture-overview", label: "Architecture Overview" },
      { slug: "trading-engine", label: "Trading Engine & Order Lifecycle" },
      { slug: "agent-architecture", label: "Agent Architecture" },
      { slug: "AGENT-FRAMEWORK", label: "Agent Framework" },
      { slug: "event-system", label: "Event Bus & Real-Time Data Flow" },
    ],
  },
  {
    title: "Data & Risk",
    docs: [
      { slug: "data-model", label: "Data Model & Schema Reference" },
      { slug: "risk-management", label: "Risk Management & Safety" },
    ],
  },
  {
    title: "Operations",
    docs: [
      { slug: "configuration", label: "Configuration & Environment" },
      { slug: "developer-guide", label: "Developer Setup & Operations" },
    ],
  },
  {
    title: "Module Deep Dives",
    docs: [
      { slug: "modules/hot-path", label: "Hot-Path Processor" },
      { slug: "modules/execution", label: "Execution Service" },
      { slug: "modules/validation", label: "Validation Service" },
      { slug: "modules/exchange", label: "Exchange Adapters" },
      { slug: "modules/messaging", label: "Messaging & Streams" },
      { slug: "modules/indicators", label: "Technical Indicators" },
      { slug: "modules/storage", label: "Storage & Repositories" },
      { slug: "modules/pnl", label: "PnL Service" },
    ],
  },
  {
    title: "SLM & AI",
    docs: [
      { slug: "SLM-Implementation-Rationale", label: "SLM Implementation Rationale" },
      { slug: "SLM-Multi-Agent-Implementation-Plan", label: "SLM Multi-Agent Plan" },
    ],
  },
  {
    title: "Reference",
    docs: [
      { slug: "glossary", label: "Glossary & Domain Model" },
      { slug: "DOCUMENTATION-GAPS", label: "Documentation Gaps & Defects" },
      { slug: "TECH-DEBT-REGISTRY", label: "Tech Debt Registry" },
      { slug: "REFACTOR-READINESS", label: "Refactor Readiness" },
    ],
  },
  {
    title: "Legacy",
    docs: [
      { slug: "RUNTIME_ARCHITECTURE", label: "Runtime Architecture" },
      { slug: "WALKTHROUGH", label: "Feature Walkthrough" },
      { slug: "SHUTDOWN", label: "Shutdown Procedures" },
      { slug: "FRONTEND-AUDIT", label: "Frontend Audit" },
      { slug: "FRONTEND-AUDIT-FINAL", label: "Frontend Audit (Final)" },
    ],
  },
];
