"use client";

import { Suspense } from "react";
import { TabLayout } from "@/components/ui/TabLayout";
import { BarChart3, Loader2 } from "lucide-react";
import { motion } from "framer-motion";
import { pageEnter } from "@/lib/motion";
import AnalysisContent from "./AnalysisContent";
import PerformanceContent from "./PerformanceContent";

const TABS = [
  { id: "charts", label: "Charts" },
  { id: "performance", label: "Performance" },
];

export default function AnalyticsPage() {
  return (
    <motion.div
      className="p-3 md:p-6 max-w-[1600px] mx-auto"
      variants={pageEnter}
      initial="hidden"
      animate="show"
    >
      <div className="flex items-center gap-3 mb-4">
        <BarChart3 className="w-5 h-5 text-primary" />
        <h1 className="text-xl font-semibold tracking-tight text-foreground">Analytics</h1>
      </div>

      <Suspense fallback={<div className="flex justify-center py-12"><Loader2 className="w-5 h-5 animate-spin text-muted-foreground" /></div>}>
        <TabLayout tabs={TABS} defaultTab="charts">
          {(activeTab) => (
            <>
              {activeTab === "charts" && <AnalysisContent />}
              {activeTab === "performance" && <PerformanceContent />}
            </>
          )}
        </TabLayout>
      </Suspense>
    </motion.div>
  );
}
