"use client";

import { useSession, signOut } from "next-auth/react";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useState, useRef } from "react";
import Link from "next/link";
import { AlertTray } from "@/components/validation/AlertTray";
import { wsClient } from "@/lib/ws/client";
import { useAuthStore } from "@/lib/stores/authStore";
import { useConnectionStore } from "@/lib/stores/connectionStore";
import { LogOut, Settings, Menu, X, WifiOff, FlaskConical } from "lucide-react";
import { motion, AnimatePresence } from "framer-motion";
import { tapScale, tapTransition, navIndicatorTransition, easing, duration } from "@/lib/motion";

const PUBLIC_PATHS = ["/login"];
const IS_MOCK_DATA = process.env.NEXT_PUBLIC_AGENT_VIEW_MOCK === "true";

// Trade is the primary surface and default landing page.
// Backtest lives inside Strategies → Verify. Analyze is absorbed into Trade.
const NAV_ITEMS = [
  { href: "/trade", label: "Trade" },
  { href: "/strategies", label: "Strategies" },
  { href: "/docs", label: "Docs" },
];

const SETTINGS_ITEM = { href: "/settings", label: "Settings" };

export function AppShell({ children }: { children: React.ReactNode }) {
  const { data: session, status } = useSession();
  const pathname = usePathname();
  const router = useRouter();
  const [showUserMenu, setShowUserMenu] = useState(false);
  const [mobileNavOpen, setMobileNavOpen] = useState(false);
  const [wsConnected, setWsConnected] = useState(false);
  const [bannerDismissed, setBannerDismissed] = useState(false);
  const menuRef = useRef<HTMLDivElement>(null);
  const jwt = useAuthStore((s) => s.jwt);
  const backendStatus = useConnectionStore((s) => s.backendStatus);

  const isPublic = PUBLIC_PATHS.some((p) => pathname.startsWith(p));

  // Connect/disconnect WebSocket and health polling based on auth state
  useEffect(() => {
    if (jwt) {
      wsClient.connect();
      useConnectionStore.getState().startHealthPolling();
    } else {
      wsClient.disconnect();
      useConnectionStore.getState().stopHealthPolling();
    }
    return () => {
      wsClient.disconnect();
      useConnectionStore.getState().stopHealthPolling();
    };
  }, [jwt]);

  // Poll WS connection status for the indicator
  useEffect(() => {
    const interval = setInterval(() => {
      setWsConnected(wsClient.isConnected());
    }, 2000);
    return () => clearInterval(interval);
  }, []);

  useEffect(() => {
    if (status === "loading") return;
    if (!session && !isPublic) {
      router.replace("/login");
    }
  }, [session, status, isPublic, router]);

  // Close mobile nav on route change
  useEffect(() => {
    setMobileNavOpen(false);
  }, [pathname]);

  // Reset banner dismissal when backend reconnects
  useEffect(() => {
    if (backendStatus === 'connected') {
      setBannerDismissed(false);
    }
  }, [backendStatus]);

  // Close dropdown when clicking outside
  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (menuRef.current && !menuRef.current.contains(e.target as Node)) {
        setShowUserMenu(false);
      }
    };
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  // Loading state for protected routes
  if (status === "loading" && !isPublic) {
    return (
      <div className="flex items-center justify-center h-screen bg-background">
        <div className="flex flex-col items-center gap-4">
          <div className="h-8 w-8 rounded-full border-2 border-primary border-t-transparent animate-spin" />
          <p className="text-xs text-muted-foreground font-mono uppercase tracking-widest">
            Authenticating...
          </p>
        </div>
      </div>
    );
  }

  // Unauthenticated on protected route — don't render
  if (!session && !isPublic) {
    return null;
  }

  // PUBLIC route (login) — render children directly without shell
  if (isPublic) {
    return <>{children}</>;
  }

  // AUTHENTICATED route — render full app shell
  const isActive = (href: string) => {
    if (href === "/") return pathname === "/";
    return pathname.startsWith(href);
  };

  const userInitials = session?.user?.name
    ? session.user.name
        .split(" ")
        .map((n) => n[0])
        .join("")
        .toUpperCase()
        .slice(0, 2)
    : "??";

  return (
    <div className="flex h-screen overflow-hidden">
      {/* Desktop Sidebar — hidden on mobile */}
      <aside className="hidden md:flex w-56 shrink-0 bg-card border-r border-border flex-col py-6 h-full z-20">
        <div className="px-6 mb-8">
          <span className="text-lg font-bold text-foreground tracking-tight">PRAXIS</span>
          <span className="text-xs text-muted-foreground font-mono uppercase tracking-widest ml-2">
            Trading
          </span>
        </div>

        <nav className="flex flex-col w-full px-3 space-y-1 flex-1">
          {NAV_ITEMS.map((item) => (
            <motion.div key={item.href} whileTap={tapScale} transition={tapTransition}>
              <Link
                href={item.href}
                className={`relative px-3 py-2.5 rounded-md font-medium text-sm transition-colors min-h-[44px] flex items-center focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary ${
                  isActive(item.href)
                    ? "text-primary"
                    : "text-muted-foreground hover:text-foreground hover:bg-accent"
                }`}
              >
                {isActive(item.href) && (
                  <motion.span
                    layoutId="nav-active"
                    className="absolute inset-0 bg-primary/10 rounded-md"
                    transition={navIndicatorTransition}
                  />
                )}
                <span className="relative z-10">{item.label}</span>
              </Link>
            </motion.div>
          ))}

          <motion.div whileTap={tapScale} transition={tapTransition} className="mt-auto">
            <Link
              href={SETTINGS_ITEM.href}
              className={`relative px-3 py-2.5 rounded-md font-medium text-sm transition-colors min-h-[44px] flex items-center focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary ${
                isActive(SETTINGS_ITEM.href)
                  ? "text-primary"
                  : "text-muted-foreground hover:text-foreground hover:bg-accent"
              }`}
            >
              {isActive(SETTINGS_ITEM.href) && (
                <motion.span
                  layoutId="nav-active"
                  className="absolute inset-0 bg-primary/10 rounded-md"
                  transition={navIndicatorTransition}
                />
              )}
              <span className="relative z-10">{SETTINGS_ITEM.label}</span>
            </Link>
          </motion.div>
        </nav>
      </aside>

      {/* Mobile Nav Overlay */}
      {mobileNavOpen && (
        <div className="fixed inset-0 z-40 md:hidden">
          <div className="absolute inset-0 bg-black/50" onClick={() => setMobileNavOpen(false)} />
          <nav className="absolute left-0 top-0 bottom-0 w-64 bg-card border-r border-border p-4 flex flex-col gap-1">
            <div className="flex items-center justify-between mb-6 px-2">
              <span className="text-lg font-bold text-foreground tracking-tight">PRAXIS</span>
              <button onClick={() => setMobileNavOpen(false)} className="p-2 min-h-[44px] min-w-[44px] flex items-center justify-center focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary" aria-label="Close navigation">
                <X className="w-5 h-5 text-muted-foreground" />
              </button>
            </div>
            {NAV_ITEMS.map((item) => (
              <Link
                key={item.href}
                href={item.href}
                className={`px-3 py-3 rounded-md font-medium text-sm transition-colors min-h-[44px] flex items-center ${
                  isActive(item.href)
                    ? "bg-primary/10 text-primary"
                    : "text-muted-foreground hover:text-foreground hover:bg-accent"
                }`}
              >
                {item.label}
              </Link>
            ))}
            <Link
              href={SETTINGS_ITEM.href}
              className={`px-3 py-3 rounded-md font-medium text-sm transition-colors mt-auto min-h-[44px] flex items-center ${
                isActive(SETTINGS_ITEM.href)
                  ? "bg-primary/10 text-primary"
                  : "text-muted-foreground hover:text-foreground hover:bg-accent"
              }`}
            >
              {SETTINGS_ITEM.label}
            </Link>
          </nav>
        </div>
      )}

      {/* Main Area */}
      <div className="flex-1 flex flex-col min-w-0 overflow-hidden bg-background">
        {/* Top Header */}
        <header className="h-14 px-3 md:px-6 border-b border-border bg-card flex items-center justify-between shrink-0 z-30">
          {/* Mobile hamburger */}
          <button
            onClick={() => setMobileNavOpen(true)}
            className="md:hidden p-2 min-h-[44px] min-w-[44px] flex items-center justify-center focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary"
            aria-label="Open navigation"
          >
            <Menu className="w-5 h-5 text-muted-foreground" />
          </button>
          <div className="hidden md:block" />

          <div className="flex items-center gap-4">
            {/* Connection Status */}
            <div className="hidden md:flex items-center gap-2 px-3 py-1.5 text-xs text-muted-foreground">
              <span className="relative flex h-2 w-2">
                {IS_MOCK_DATA ? (
                  <span className="inline-flex rounded-full h-2 w-2 bg-amber-500 animate-pulse" />
                ) : backendStatus === 'connected' && wsConnected ? (
                  <span className="inline-flex rounded-full h-2 w-2 bg-emerald-500" />
                ) : backendStatus === 'connected' ? (
                  <span className="inline-flex rounded-full h-2 w-2 bg-amber-500" />
                ) : (
                  <span className="inline-flex rounded-full h-2 w-2 bg-red-500" />
                )}
              </span>
              <span className={`font-mono tabular-nums uppercase font-medium text-xs tracking-wider ${
                IS_MOCK_DATA
                  ? "text-amber-500/80"
                  : backendStatus === 'connected' && wsConnected
                  ? "text-emerald-500/80"
                  : backendStatus === 'connected'
                  ? "text-amber-500/80"
                  : "text-red-500/80"
              }`}>
                {IS_MOCK_DATA
                  ? "Mock Data"
                  : backendStatus === 'connected' && wsConnected
                  ? "Live"
                  : backendStatus === 'connected'
                  ? "API Only"
                  : "Backend Offline"}
              </span>
            </div>

            <AlertTray />

            {/* User Avatar with Dropdown */}
            <div className="relative" ref={menuRef}>
              <button
                onClick={() => setShowUserMenu(!showUserMenu)}
                className="focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary min-h-[44px] min-w-[44px] flex items-center justify-center"
                aria-label="User menu"
              >
                {session?.user?.image ? (
                  <img
                    src={session.user.image}
                    alt="User avatar"
                    className="h-8 w-8 rounded-full border border-border cursor-pointer"
                  />
                ) : (
                  <div className="h-8 w-8 rounded-full bg-accent border border-border flex items-center justify-center text-xs font-medium text-muted-foreground cursor-pointer hover:text-foreground transition-colors">
                    {userInitials}
                  </div>
                )}
              </button>

              {/* Dropdown Menu */}
              <AnimatePresence>
                {showUserMenu && (
                  <motion.div
                    initial={{ opacity: 0, y: -8, scale: 0.96 }}
                    animate={{ opacity: 1, y: 0, scale: 1 }}
                    exit={{ opacity: 0, y: -8, scale: 0.96 }}
                    transition={{ duration: duration.fast, ease: easing.enter }}
                    className="absolute right-0 top-12 w-60 bg-card border border-border rounded-md py-1 z-50"
                  >
                    {/* User Info */}
                    <div className="px-4 py-3 border-b border-border">
                      <p className="text-sm font-medium text-foreground truncate">
                        {session?.user?.name || "User"}
                      </p>
                      <p className="text-xs text-muted-foreground truncate">
                        {session?.user?.email || ""}
                      </p>
                    </div>

                    {/* Menu Items */}
                    <div className="py-1">
                      <Link
                        href="/settings"
                        className="flex items-center gap-3 px-4 py-2.5 text-sm text-foreground/80 hover:bg-accent hover:text-foreground transition-colors min-h-[44px]"
                        onClick={() => setShowUserMenu(false)}
                      >
                        <Settings className="w-4 h-4 text-muted-foreground" />
                        Settings
                      </Link>
                    </div>

                    {/* Sign Out */}
                    <div className="border-t border-border pt-1">
                      <button
                        onClick={() => signOut({ callbackUrl: "/login" })}
                        className="flex items-center gap-3 px-4 py-2.5 text-sm text-red-500 hover:bg-accent transition-colors w-full text-left min-h-[44px]"
                      >
                        <LogOut className="w-4 h-4" />
                        Sign Out
                      </button>
                    </div>
                  </motion.div>
                )}
              </AnimatePresence>
            </div>
          </div>
        </header>

        {/* Mock Data Banner — non-dismissible, always visible when mock is active */}
        {IS_MOCK_DATA && (
          <div className="bg-amber-500/15 border-b border-amber-500/30 px-4 py-2 flex items-center gap-3 text-sm text-amber-400 shrink-0">
            <FlaskConical className="w-4 h-4 shrink-0" />
            <span className="font-mono text-xs uppercase tracking-wider font-semibold">Mock Data</span>
            <span className="text-amber-400/70 text-xs">
              Telemetry is simulated. Set <code className="bg-amber-500/10 px-1 rounded text-amber-400">NEXT_PUBLIC_AGENT_VIEW_MOCK=false</code> to use live data.
            </span>
          </div>
        )}

        {/* Backend Offline Banner */}
        <AnimatePresence>
          {backendStatus === 'disconnected' && !bannerDismissed && (
            <motion.div
              initial={{ height: 0, opacity: 0 }}
              animate={{ height: "auto", opacity: 1 }}
              exit={{ height: 0, opacity: 0 }}
              transition={{ duration: duration.normal, ease: easing.enter }}
              className="overflow-hidden shrink-0"
            >
              <div className="bg-red-500/10 border-b border-red-500/20 px-4 py-3 flex items-center justify-between">
                <div className="flex items-center gap-3 text-sm text-red-400">
                  <WifiOff className="w-4 h-4 shrink-0" />
                  <span>
                    <strong>Backend unreachable.</strong>{" "}
                    Make sure your local services are running and your tunnel is active.
                    The dashboard will reconnect automatically.
                  </span>
                </div>
                <button
                  onClick={() => setBannerDismissed(true)}
                  className="text-red-400/60 hover:text-red-400 p-1 min-h-[44px] min-w-[44px] flex items-center justify-center"
                  aria-label="Dismiss"
                >
                  <X className="w-4 h-4" />
                </button>
              </div>
            </motion.div>
          )}
        </AnimatePresence>

        {/* Page Content */}
        <main className="flex-1 relative overflow-y-auto w-full h-full p-3 md:p-6">
          {children}
        </main>
      </div>
    </div>
  );
}
