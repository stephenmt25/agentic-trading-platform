"use client";

import { Suspense } from "react";
import { TabLayout } from "@/components/ui/TabLayout";
import { Layers, Loader2 } from "lucide-react";
import { motion } from "framer-motion";
import { pageEnter } from "@/lib/motion";
import dynamic from "next/dynamic";
import { RawProfileView } from "@/components/strategies/RawProfileView";

const BuilderContent = dynamic(() => import("../pipeline/page"), {
  ssr: false,
  loading: () => <Loader2 className="w-5 h-5 animate-spin text-muted-foreground mx-auto mt-12" />,
});
const VerifyContent = dynamic(() => import("../backtest/page"), {
  ssr: false,
  loading: () => <Loader2 className="w-5 h-5 animate-spin text-muted-foreground mx-auto mt-12" />,
});
const ProfilesContent = dynamic(() => import("../profiles/page"), {
  ssr: false,
  loading: () => <Loader2 className="w-5 h-5 animate-spin text-muted-foreground mx-auto mt-12" />,
});

const TABS = [
  { id: "profiles", label: "Profiles" },
  { id: "builder", label: "Builder" },
  { id: "verify", label: "Verify" },
  { id: "raw", label: "Raw" },
];

export default function StrategiesPage() {
  return (
    <motion.div
      className="p-3 md:p-6 max-w-[1600px] mx-auto"
      variants={pageEnter}
      initial="hidden"
      animate="show"
    >
      <div className="flex items-center gap-3 mb-1">
        <Layers className="w-5 h-5 text-primary" />
        <h1 className="text-xl font-semibold tracking-tight text-foreground">Strategies</h1>
      </div>
      <p className="text-xs text-muted-foreground mb-4">
        Build your strategy on the canvas. Verify with a backtest before running.
      </p>

      <Suspense fallback={<div className="flex justify-center py-12"><Loader2 className="w-5 h-5 animate-spin text-muted-foreground" /></div>}>
        <TabLayout tabs={TABS} defaultTab="profiles">
          {(activeTab) => (
            <>
              {activeTab === "profiles" && <ProfilesContent />}
              {activeTab === "builder" && <BuilderContent />}
              {activeTab === "verify" && <VerifyContent />}
              {activeTab === "raw" && <RawProfileView />}
            </>
          )}
        </TabLayout>
      </Suspense>
    </motion.div>
  );
}
