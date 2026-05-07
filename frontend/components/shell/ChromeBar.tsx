"use client";

import { useState, useRef, useEffect } from "react";
import { usePathname } from "next/navigation";
import { useSession, signOut } from "next-auth/react";
import Link from "next/link";
import { Search, LogOut, Settings as SettingsIcon } from "lucide-react";
import { cn } from "@/lib/utils";
import { StatusPills } from "./StatusPills";
import { useCommandPalette } from "./CommandPalette";

const SURFACE_NAMES: Record<string, string> = {
  hot: "Hot Trading",
  agents: "Agent Observatory",
  canvas: "Pipeline Canvas",
  backtests: "Backtesting",
  risk: "Risk Control",
  settings: "Profiles & Settings",
  login: "Sign In",
};

function breadcrumbForPath(pathname: string | null): string[] {
  if (!pathname || pathname === "/") return ["Praxis"];
  const segments = pathname.split("/").filter(Boolean);
  const head =
    SURFACE_NAMES[segments[0]] ??
    segments[0].replace(/^./, (c) => c.toUpperCase());
  const tail = segments.slice(1);
  return [head, ...tail];
}

export function ChromeBar() {
  const pathname = usePathname();
  const crumbs = breadcrumbForPath(pathname);
  const { data: session } = useSession();
  const [showUserMenu, setShowUserMenu] = useState(false);
  const menuRef = useRef<HTMLDivElement>(null);
  const openPalette = useCommandPalette((s) => s.open);

  useEffect(() => {
    const handle = (e: MouseEvent) => {
      if (menuRef.current && !menuRef.current.contains(e.target as Node)) {
        setShowUserMenu(false);
      }
    };
    document.addEventListener("mousedown", handle);
    return () => document.removeEventListener("mousedown", handle);
  }, []);

  const userInitials = session?.user?.name
    ? session.user.name
        .split(" ")
        .map((n) => n[0])
        .join("")
        .toUpperCase()
        .slice(0, 2)
    : "??";

  return (
    <header
      className={cn(
        "h-11 px-3 md:px-4 shrink-0 z-30",
        "border-b border-border-subtle bg-bg-panel",
        "flex items-center justify-between gap-3"
      )}
    >
      {/* Breadcrumb */}
      <nav
        aria-label="Breadcrumb"
        className="flex items-center gap-1.5 text-sm min-w-0"
      >
        {crumbs.map((c, i) => (
          <span key={i} className="flex items-center gap-1.5 truncate">
            {i > 0 && <span className="text-fg-muted text-xs">/</span>}
            <span
              className={cn(
                "truncate",
                i === crumbs.length - 1 ? "text-fg" : "text-fg-secondary"
              )}
            >
              {c}
            </span>
          </span>
        ))}
      </nav>

      <div className="flex items-center gap-3">
        <StatusPills />

        {/* Cmd+K trigger */}
        <button
          onClick={openPalette}
          aria-label="Open command palette (Cmd+K)"
          className={cn(
            "h-8 px-2.5 flex items-center gap-2 rounded-md",
            "border border-border-subtle bg-bg-canvas hover:bg-bg-raised",
            "text-fg-muted hover:text-fg text-xs",
            "focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent-500"
          )}
        >
          <Search className="w-3.5 h-3.5" strokeWidth={1.5} aria-hidden />
          <span className="hidden md:inline">Search</span>
          <kbd className="hidden md:inline-flex items-center px-1.5 py-0.5 rounded border border-border-subtle bg-bg-panel text-[10px] num-tabular text-fg-muted">
            ⌘K
          </kbd>
        </button>

        {/* User menu */}
        <div className="relative" ref={menuRef}>
          <button
            onClick={() => setShowUserMenu((v) => !v)}
            aria-label="User menu"
            aria-expanded={showUserMenu}
            className={cn(
              "h-8 w-8 flex items-center justify-center rounded-full",
              "border border-border-subtle bg-bg-canvas",
              "focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent-500"
            )}
          >
            {session?.user?.image ? (
              // eslint-disable-next-line @next/next/no-img-element
              <img
                src={session.user.image}
                alt=""
                className="h-7 w-7 rounded-full"
              />
            ) : (
              <span className="text-xs font-medium text-fg-secondary">
                {userInitials}
              </span>
            )}
          </button>

          {showUserMenu && (
            <div
              role="menu"
              className="absolute right-0 top-10 w-60 z-50 rounded-md border border-border-subtle bg-bg-panel"
            >
              <div className="px-3 py-2.5 border-b border-border-subtle">
                <p className="text-sm font-medium text-fg truncate">
                  {session?.user?.name || "User"}
                </p>
                <p className="text-xs text-fg-muted truncate">
                  {session?.user?.email || ""}
                </p>
              </div>
              <div className="py-1">
                <Link
                  href="/settings"
                  onClick={() => setShowUserMenu(false)}
                  role="menuitem"
                  className="flex items-center gap-2.5 px-3 py-2 text-sm text-fg-secondary hover:bg-bg-raised hover:text-fg"
                >
                  <SettingsIcon
                    className="w-4 h-4 text-fg-muted"
                    strokeWidth={1.5}
                  />
                  Settings
                </Link>
              </div>
              <div className="border-t border-border-subtle py-1">
                <button
                  onClick={() => signOut({ callbackUrl: "/login" })}
                  role="menuitem"
                  className="flex items-center gap-2.5 px-3 py-2 text-sm text-ask-500 hover:bg-bg-raised w-full text-left"
                >
                  <LogOut className="w-4 h-4" strokeWidth={1.5} />
                  Sign Out
                </button>
              </div>
            </div>
          )}
        </div>
      </div>
    </header>
  );
}
