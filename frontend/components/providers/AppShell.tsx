"use client";

import { useSession, signOut } from "next-auth/react";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useState, useRef } from "react";
import { AlertTray } from "@/components/validation/AlertTray";
import { LogOut, Settings, User } from "lucide-react";

const PUBLIC_PATHS = ["/login"];

const NAV_ITEMS = [
  { href: "/", label: "Dashboard" },
  { href: "/profiles", label: "Profiles" },
  { href: "/backtest", label: "Backtest" },
  { href: "/paper-trading", label: "Paper Trading" },
];

const SETTINGS_ITEM = { href: "/settings", label: "Settings" };

export function AppShell({ children }: { children: React.ReactNode }) {
  const { data: session, status } = useSession();
  const pathname = usePathname();
  const router = useRouter();
  const [showUserMenu, setShowUserMenu] = useState(false);
  const menuRef = useRef<HTMLDivElement>(null);

  const isPublic = PUBLIC_PATHS.some((p) => pathname.startsWith(p));

  useEffect(() => {
    if (status === "loading") return;
    if (!session && !isPublic) {
      router.replace("/login");
    }
  }, [session, status, isPublic, router]);

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
      <div className="flex items-center justify-center h-screen bg-slate-950">
        <div className="flex flex-col items-center gap-4">
          <div className="h-8 w-8 rounded-full border-2 border-indigo-500 border-t-transparent animate-spin" />
          <p className="text-xs text-slate-600 font-mono uppercase tracking-widest">
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
      <aside className="w-64 shrink-0 bg-slate-900 border-r border-slate-800 flex flex-col items-center py-6 h-full shadow-2xl z-20">
        <div className="text-2xl font-black bg-clip-text text-transparent bg-gradient-to-r from-indigo-400 to-cyan-400 tracking-tighter mb-12">
          AGENTIC<br />
          <span className="text-sm text-slate-500 font-normal tracking-widest uppercase">
            TRADER
          </span>
        </div>

        <nav className="flex flex-col w-full px-4 space-y-2 flex-1">
          {NAV_ITEMS.map((item) => (
            <a
              key={item.href}
              href={item.href}
              className={`px-4 py-3 rounded-lg font-bold text-sm tracking-wide transition ${
                isActive(item.href)
                  ? "bg-primary/10 text-primary border border-primary/20"
                  : "text-muted-foreground hover:text-foreground hover:bg-slate-800/50"
              }`}
            >
              {item.label}
            </a>
          ))}

          <a
            href={SETTINGS_ITEM.href}
            className={`px-4 py-3 rounded-lg font-bold text-sm tracking-wide transition mt-auto ${
              isActive(SETTINGS_ITEM.href)
                ? "bg-primary/10 text-primary border border-primary/20"
                : "text-muted-foreground hover:text-foreground hover:bg-slate-800/50"
            }`}
          >
            {SETTINGS_ITEM.label}
          </a>
        </nav>
      </aside>

      {/* Main Area */}
      <div className="flex-1 flex flex-col min-w-0 overflow-hidden bg-background">
        {/* Top Header */}
        <header className="h-16 px-4 lg:px-8 border-b border-border bg-card flex items-center justify-between shrink-0 shadow-sm z-30">
          <div className="flex items-center gap-4" />

          <div className="flex items-center gap-6">
            {/* Connection Status */}
            <div className="hidden md:flex items-center gap-2 px-3 py-1.5 bg-black/20 border border-border rounded-full text-xs text-muted-foreground">
              <span className="relative flex h-2 w-2">
                <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75" />
                <span className="relative inline-flex rounded-full h-2 w-2 bg-emerald-500" />
              </span>
              <span className="font-mono uppercase font-bold text-[10px] tracking-widest text-emerald-500/80">
                Active
              </span>
              <span className="font-mono opacity-50 ml-1">wss://api/connect</span>
            </div>

            <AlertTray />

            {/* User Avatar with Dropdown */}
            <div className="relative" ref={menuRef}>
              <button
                onClick={() => setShowUserMenu(!showUserMenu)}
                className="focus:outline-none"
              >
                {session?.user?.image ? (
                  <img
                    src={session.user.image}
                    alt="User avatar"
                    className="h-8 w-8 rounded-full border border-slate-700 cursor-pointer hover:ring-2 hover:ring-primary/50 transition-all"
                  />
                ) : (
                  <div className="h-8 w-8 rounded-full bg-slate-800 border border-slate-700 flex items-center justify-center text-xs font-bold text-slate-400 cursor-pointer hover:bg-slate-700 hover:text-white transition-colors">
                    {userInitials}
                  </div>
                )}
              </button>

              {/* Dropdown Menu */}
              {showUserMenu && (
                <div className="absolute right-0 top-12 w-64 bg-slate-900 border border-slate-700 rounded-xl shadow-2xl py-2 z-50 animate-in fade-in slide-in-from-top-2 duration-150">
                  {/* User Info */}
                  <div className="px-4 py-3 border-b border-slate-800">
                    <p className="text-sm font-bold text-slate-200 truncate">
                      {session?.user?.name || "User"}
                    </p>
                    <p className="text-xs text-slate-500 truncate">
                      {session?.user?.email || ""}
                    </p>
                  </div>

                  {/* Menu Items */}
                  <div className="py-1">
                    <a
                      href="/settings"
                      className="flex items-center gap-3 px-4 py-2.5 text-sm text-slate-300 hover:bg-slate-800 hover:text-white transition-colors"
                      onClick={() => setShowUserMenu(false)}
                    >
                      <Settings className="w-4 h-4 text-slate-500" />
                      Settings
                    </a>
                  </div>

                  {/* Sign Out */}
                  <div className="border-t border-slate-800 pt-1">
                    <button
                      onClick={() => signOut({ callbackUrl: "/login" })}
                      className="flex items-center gap-3 px-4 py-2.5 text-sm text-red-400 hover:bg-red-900/20 hover:text-red-300 transition-colors w-full text-left"
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
        <main className="flex-1 relative overflow-y-auto w-full h-full p-4 lg:p-8">
          {children}
        </main>
      </div>
    </div>
  );
}
