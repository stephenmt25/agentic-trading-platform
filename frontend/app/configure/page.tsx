"use client";

import { Suspense } from "react";
import { TabLayout } from "@/components/ui/TabLayout";
import { Settings2, Loader2 } from "lucide-react";
import { motion } from "framer-motion";
import { pageEnter } from "@/lib/motion";
import dynamic from "next/dynamic";

// Dynamic imports to avoid loading React Flow + heavy profile page upfront
const ProfilesContent = dynamic(() => import("../profiles/page"), { ssr: false, loading: () => <Loader2 className="w-5 h-5 animate-spin text-muted-foreground mx-auto mt-12" /> });
const PipelineContent = dynamic(() => import("../pipeline/page"), { ssr: false, loading: () => <Loader2 className="w-5 h-5 animate-spin text-muted-foreground mx-auto mt-12" /> });

const TABS = [
  { id: "profiles", label: "Profiles" },
  { id: "pipeline", label: "Pipeline" },
];

export default function ConfigurePage() {
  return (
    <motion.div
      className="p-3 md:p-6 max-w-[1600px] mx-auto"
      variants={pageEnter}
      initial="hidden"
      animate="show"
    >
      <div className="flex items-center gap-3 mb-4">
        <Settings2 className="w-5 h-5 text-primary" />
        <h1 className="text-xl font-semibold tracking-tight text-foreground">Configure</h1>
      </div>

      <Suspense fallback={<div className="flex justify-center py-12"><Loader2 className="w-5 h-5 animate-spin text-muted-foreground" /></div>}>
        <TabLayout tabs={TABS} defaultTab="profiles">
          {(activeTab) => (
            <>
              {activeTab === "profiles" && <ProfilesContent />}
              {activeTab === "pipeline" && <PipelineContent />}
            </>
          )}
        </TabLayout>
      </Suspense>
    </motion.div>
  );
}
