"use client";

import { useEffect, useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { WifiOff, FlaskConical, X } from "lucide-react";
import { LeftRail } from "./LeftRail";
import { ChromeBar } from "./ChromeBar";
import { CommandPalette } from "./CommandPalette";
import { useKillSwitchStore } from "@/lib/stores/killSwitchStore";
import { useConnectionStore } from "@/lib/stores/connectionStore";

const IS_MOCK_DATA = process.env.NEXT_PUBLIC_AGENT_VIEW_MOCK === "true";

/**
 * The redesign chrome shell. Composes LeftRail + ChromeBar + page slot
 * + global CommandPalette overlay. Banners (mock data, backend offline)
 * sit between ChromeBar and the page content.
 *
 * The kill-switch overlay rule (data-kill-switch="hard" on body) is
 * activated here from the killSwitch store — the actual overlay CSS
 * lives in design-tokens.css.
 */
export function RedesignShell({ children }: { children: React.ReactNode }) {
  const killState = useKillSwitchStore((s) => s.state);
  const backendStatus = useConnectionStore((s) => s.backendStatus);
  const [bannerDismissed, setBannerDismissed] = useState(false);

  useEffect(() => {
    if (killState === "hard") {
      document.body.setAttribute("data-kill-switch", "hard");
    } else {
      document.body.removeAttribute("data-kill-switch");
    }
    return () => {
      document.body.removeAttribute("data-kill-switch");
    };
  }, [killState]);

  useEffect(() => {
    if (backendStatus === "connected") setBannerDismissed(false);
  }, [backendStatus]);

  return (
    <div className="flex h-screen overflow-hidden bg-bg-canvas text-fg">
      <LeftRail />

      <div className="flex-1 flex flex-col min-w-0 overflow-hidden">
        <ChromeBar />

        {IS_MOCK_DATA && (
          <div
            role="status"
            className="bg-warn-700/15 border-b border-warn-700 px-4 py-2 flex items-center gap-3 text-sm text-warn-400 shrink-0"
          >
            <FlaskConical
              className="w-4 h-4 shrink-0"
              strokeWidth={1.5}
              aria-hidden
            />
            <span className="font-mono text-xs uppercase tracking-wider font-semibold num-tabular">
              Mock Data
            </span>
            <span className="text-warn-400/70 text-xs">
              Telemetry is simulated. Set{" "}
              <code className="px-1 rounded bg-warn-700/20 text-warn-400">
                NEXT_PUBLIC_AGENT_VIEW_MOCK=false
              </code>{" "}
              for live data.
            </span>
          </div>
        )}

        <AnimatePresence>
          {backendStatus === "disconnected" && !bannerDismissed && (
            <motion.div
              initial={{ height: 0, opacity: 0 }}
              animate={{ height: "auto", opacity: 1 }}
              exit={{ height: 0, opacity: 0 }}
              transition={{ duration: 0.18 }}
              className="overflow-hidden shrink-0"
            >
              <div
                role="alert"
                className="bg-danger-700/10 border-b border-danger-700/40 px-4 py-3 flex items-center justify-between"
              >
                <div className="flex items-center gap-3 text-sm text-danger-500">
                  <WifiOff
                    className="w-4 h-4 shrink-0"
                    strokeWidth={1.5}
                    aria-hidden
                  />
                  <span>
                    <strong>Backend unreachable.</strong> Make sure your local
                    services are running. Reconnecting automatically.
                  </span>
                </div>
                <button
                  onClick={() => setBannerDismissed(true)}
                  className="text-danger-500/60 hover:text-danger-500 p-1"
                  aria-label="Dismiss"
                >
                  <X className="w-4 h-4" strokeWidth={1.5} />
                </button>
              </div>
            </motion.div>
          )}
        </AnimatePresence>

        <main className="flex-1 relative overflow-y-auto w-full h-full">
          {children}
        </main>
      </div>

      <CommandPalette />
    </div>
  );
}
