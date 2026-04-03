"use client";

import { useState } from "react";
import { useAgentTelemetry } from "@/lib/hooks/useAgentTelemetry";
import { useIsMobile } from "@/lib/hooks/useMediaQuery";
import { SystemStatusBar } from "@/components/agent-view/SystemStatusBar";
import { AgentRegistry } from "@/components/agent-view/AgentRegistry";
import { AgentDetail } from "@/components/agent-view/AgentDetail";
import { MessageFlowPanel } from "@/components/agent-view/MessageFlowPanel";
import { QuickStatsBar } from "@/components/agent-view/QuickStatsBar";
import { MobileBottomNav, type MobileTab } from "@/components/agent-view/MobileBottomNav";
import { MobileStatsPanel } from "@/components/agent-view/MobileStatsPanel";
import { motion } from "framer-motion";
import { pageEnter } from "@/lib/motion";

export default function AgentViewPage() {
  const { slowMode } = useAgentTelemetry();
  const isMobile = useIsMobile();
  const [activeTab, setActiveTab] = useState<MobileTab>("agents");

  // ── Mobile layout: single panel + bottom nav ──────────────────────────
  if (isMobile) {
    return (
      <motion.div
        className="flex h-full flex-col bg-[#0d1117] text-slate-200"
        variants={pageEnter}
        initial="initial"
        animate="animate"
      >
        {/* Condensed status bar */}
        <SystemStatusBar slowMode={slowMode} />

        {/* Active tab content */}
        <div className="flex-1 min-h-0 overflow-hidden">
          {activeTab === "agents" && <AgentRegistry />}
          {activeTab === "detail" && <AgentDetail />}
          {activeTab === "messages" && <MessageFlowPanel />}
          {activeTab === "stats" && <MobileStatsPanel slowMode={slowMode} />}
        </div>

        {/* Bottom navigation */}
        <MobileBottomNav activeTab={activeTab} onTabChange={setActiveTab} />
      </motion.div>
    );
  }

  // ── Desktop layout: 3-panel side-by-side ──────────────────────────────
  return (
    <motion.div
      className="flex h-full flex-col bg-[#0d1117] text-slate-200"
      variants={pageEnter}
      initial="initial"
      animate="animate"
    >
      {/* Top bar */}
      <SystemStatusBar slowMode={slowMode} />

      {/* Main workspace */}
      <div className="flex flex-1 min-h-0 overflow-hidden">
        {/* Left panel — agent registry */}
        <AgentRegistry />

        {/* Center panel — agent detail */}
        <div className="flex-1 min-w-0 overflow-hidden">
          <AgentDetail />
        </div>

        {/* Right panel — message flow */}
        <MessageFlowPanel />
      </div>

      {/* Bottom dock */}
      <QuickStatsBar />
    </motion.div>
  );
}
