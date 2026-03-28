"use client";

import { useSession, signOut } from "next-auth/react";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useState, useRef } from "react";
import Link from "next/link";
import { AlertTray } from "@/components/validation/AlertTray";
import { wsClient } from "@/lib/ws/client";
import { useAuthStore } from "@/lib/stores/authStore";
import { LogOut, Settings, Menu, X } from "lucide-react";

const PUBLIC_PATHS = ["/login"];

const NAV_ITEMS = [
  { href: "/", label: "Dashboard" },
  { href: "/agent-view", label: "Agent View" },
  { href: "/profiles", label: "Profiles" },
  { href: "/backtest", label: "Backtest" },
  { href: "/paper-trading", label: "Paper Trading" },
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
  const menuRef = useRef<HTMLDivElement>(null);
  const jwt = useAuthStore((s) => s.jwt);

  const isPublic = PUBLIC_PATHS.some((p) => pathname.startsWith(p));

  // Connect/disconnect WebSocket based on auth state
  useEffect(() => {
    if (jwt) {
      wsClient.connect();
    } else {
      wsClient.disconnect();
    }
    return () => {
      wsClient.disconnect();
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
            <Link
              key={item.href}
              href={item.href}
              className={`px-3 py-2.5 rounded-md font-medium text-sm transition-colors min-h-[44px] flex items-center focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary ${
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
            className={`px-3 py-2.5 rounded-md font-medium text-sm transition-colors mt-auto min-h-[44px] flex items-center focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary ${
              isActive(SETTINGS_ITEM.href)
                ? "bg-primary/10 text-primary"
                : "text-muted-foreground hover:text-foreground hover:bg-accent"
            }`}
          >
            {SETTINGS_ITEM.label}
          </Link>
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
                {wsConnected ? (
                  <span className="inline-flex rounded-full h-2 w-2 bg-emerald-500" />
                ) : (
                  <span className="inline-flex rounded-full h-2 w-2 bg-muted-foreground/50" />
                )}
              </span>
              <span className={`font-mono tabular-nums uppercase font-medium text-xs tracking-wider ${wsConnected ? "text-emerald-500/80" : "text-muted-foreground"}`}>
                {wsConnected ? "Live" : "Offline"}
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
              {showUserMenu && (
                <div className="absolute right-0 top-12 w-60 bg-card border border-border rounded-md py-1 z-50 animate-in fade-in slide-in-from-top-2 duration-150">
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
                </div>
              )}
            </div>
          </div>
        </header>

        {/* Page Content */}
        <main className="flex-1 relative overflow-y-auto w-full h-full p-3 md:p-6">
          {children}
        </main>
      </div>
    </div>
  );
}
