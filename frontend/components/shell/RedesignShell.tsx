"use client";

import { Suspense, useEffect, useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { WifiOff, FlaskConical, X } from "lucide-react";
import { LeftRail } from "./LeftRail";
import { ChromeBar } from "./ChromeBar";
import { CommandPalette } from "./CommandPalette";
import { KillSwitchModal } from "./KillSwitchModal";
import { PageLoading } from "./PageLoading";
import { useKillSwitch } from "@/lib/api/hooks";
import {
  parseHaltLevel,
  severity,
  useKillSwitchStore,
} from "@/lib/stores/killSwitchStore";
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
  const killLevel = useKillSwitchStore((s) => s.level);
  const setKillLevel = useKillSwitchStore((s) => s.setLevel);
  const toggleKillModal = useKillSwitchStore((s) => s.toggleModal);
  const backendStatus = useConnectionStore((s) => s.backendStatus);
  const [bannerDismissed, setBannerDismissed] = useState(false);

  // Canonical kill-switch sync: the 10s useKillSwitch poll is mounted HERE,
  // once, so the ["killSwitch"] React Query cache is live on EVERY
  // authenticated surface — this is what makes the modal's optimistic
  // snapshot/rollback/invalidate machinery real (the modal reconciles
  // against this poll), including on surfaces with no page-local poller
  // (/settings, /agents, /performance). The store mirror below keeps the
  // chrome (StatusPills, body overlay) coherent. The page-local setInterval
  // pollers on /hot and /risk write the same store and can be retired in
  // FE-W2.
  const { data: killStatus } = useKillSwitch();
  useEffect(() => {
    if (!killStatus) return;
    setKillLevel(parseHaltLevel(killStatus.level, killStatus.active));
  }, [killStatus, setKillLevel]);

  // Danger severity (NEUTRALIZE / FLATTEN — position-closing verbs) fires
  // the body overlay; warn levels (STOP_OPENING / DE_RISK) only tint chrome.
  useEffect(() => {
    if (severity(killLevel) === "danger") {
      document.body.setAttribute("data-kill-switch", "hard");
    } else {
      document.body.removeAttribute("data-kill-switch");
    }
    return () => {
      document.body.removeAttribute("data-kill-switch");
    };
  }, [killLevel]);

  // Global Cmd/Ctrl+Shift+K — kill-switch modal toggle. Mounted here so
  // every authenticated surface gets it without per-page wiring (closes the
  // §8.5 accessibility gate: "kill switch ≤2 keystrokes from any surface").
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.shiftKey && e.key.toLowerCase() === "k") {
        e.preventDefault();
        toggleKillModal();
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [toggleKillModal]);

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
          {/* Root boundary (FE-W0). Today this is forward-scaffolding plus
              the CSR-bailout boundary for useSearchParams; nothing in the
              tree suspends into it yet (dynamic() imports supply their own
              `loading:`), and per-route loading.tsx files (FE-W3) create
              segment boundaries BELOW this one that absorb suspensions
              before they reach this fallback. */}
          <Suspense fallback={<PageLoading />}>{children}</Suspense>
        </main>
      </div>

      <CommandPalette />
      <KillSwitchModal />
    </div>
  );
}
