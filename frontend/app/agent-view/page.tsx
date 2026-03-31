"use client";

import { useAgentTelemetry } from "@/lib/hooks/useAgentTelemetry";
import { SystemStatusBar } from "@/components/agent-view/SystemStatusBar";
import { AgentRegistry } from "@/components/agent-view/AgentRegistry";
import { AgentDetail } from "@/components/agent-view/AgentDetail";
import { MessageFlowPanel } from "@/components/agent-view/MessageFlowPanel";
import { QuickStatsBar } from "@/components/agent-view/QuickStatsBar";
import { motion } from "framer-motion";
import { pageEnter } from "@/lib/motion";

export default function AgentViewPage() {
  const { slowMode } = useAgentTelemetry();

  return (
    <motion.div className="flex h-full flex-col bg-[#0d1117] text-slate-200"
      variants={pageEnter} initial="initial" animate="animate">
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
