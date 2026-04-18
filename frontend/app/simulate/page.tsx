"use client";

import { Suspense } from "react";
import { TabLayout } from "@/components/ui/TabLayout";
import { FlaskConical, Loader2 } from "lucide-react";
import { motion } from "framer-motion";
import { pageEnter } from "@/lib/motion";
import dynamic from "next/dynamic";

const BacktestContent = dynamic(() => import("../backtest/page"), { ssr: false, loading: () => <Loader2 className="w-5 h-5 animate-spin text-muted-foreground mx-auto mt-12" /> });
const PaperTradingContent = dynamic(() => import("../paper-trading/page"), { ssr: false, loading: () => <Loader2 className="w-5 h-5 animate-spin text-muted-foreground mx-auto mt-12" /> });
const ApprovalContent = dynamic(() => import("../approval/page"), { ssr: false, loading: () => <Loader2 className="w-5 h-5 animate-spin text-muted-foreground mx-auto mt-12" /> });

const TABS = [
  { id: "backtest", label: "Backtest" },
  { id: "paper-trading", label: "Paper Trading" },
  { id: "approval", label: "Approval" },
];

export default function SimulatePage() {
  return (
    <motion.div
      className="p-3 md:p-6 max-w-[1600px] mx-auto"
      variants={pageEnter}
      initial="hidden"
      animate="show"
    >
      <div className="flex items-center gap-3 mb-4">
        <FlaskConical className="w-5 h-5 text-primary" />
        <h1 className="text-xl font-semibold tracking-tight text-foreground">Simulate</h1>
      </div>

      <Suspense fallback={<div className="flex justify-center py-12"><Loader2 className="w-5 h-5 animate-spin text-muted-foreground" /></div>}>
        <TabLayout tabs={TABS} defaultTab="backtest">
          {(activeTab) => (
            <>
              {activeTab === "backtest" && <BacktestContent />}
              {activeTab === "paper-trading" && <PaperTradingContent />}
              {activeTab === "approval" && <ApprovalContent />}
            </>
          )}
        </TabLayout>
      </Suspense>
    </motion.div>
  );
}
