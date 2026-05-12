"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { cn } from "@/lib/utils";

interface NavItem {
  href: string;
  label: string;
  description?: string;
}

const NAV: NavItem[] = [
  { href: "/settings/profiles",      label: "Profiles" },
  { href: "/settings/exchange",      label: "Exchange keys" },
  { href: "/settings/risk",          label: "Risk defaults" },
  { href: "/settings/notifications", label: "Notifications" },
  { href: "/settings/tax",           label: "Tax" },
  { href: "/settings/account",       label: "Account" },
  { href: "/settings/sessions",      label: "Sessions / API" },
  { href: "/settings/audit",         label: "Audit log" },
];

function isActive(href: string, pathname: string | null): boolean {
  if (!pathname) return false;
  if (href === "/settings/profiles") {
    return pathname === "/settings" || pathname.startsWith("/settings/profiles");
  }
  return pathname === href || pathname.startsWith(href + "/");
}

/**
 * Profiles & Settings surface shell. CALM mode: 220px nav + max-w-720
 * content, generous whitespace, 15px body baseline. Per
 * docs/design/05-surface-specs/06-profiles-settings.md.
 */
export default function SettingsLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const pathname = usePathname();

  return (
    <div
      data-mode="calm"
      className="flex min-h-full bg-bg-canvas text-fg text-[15px] leading-relaxed"
    >
      <nav
        aria-label="Settings sections"
        className="w-[220px] shrink-0 border-r border-border-subtle py-8 px-4 hidden md:block"
      >
        <h2 className="text-[10px] font-semibold uppercase tracking-wider text-fg-muted px-3 mb-3">
          Settings
        </h2>
        <ul className="flex flex-col gap-0.5">
          {NAV.map((item) => {
            const active = isActive(item.href, pathname);
            return (
              <li key={item.href}>
                <Link
                  href={item.href}
                  aria-current={active ? "page" : undefined}
                  className={cn(
                    "relative block rounded-md px-3 py-2 text-[14px] transition-colors",
                    "focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent-500",
                    active
                      ? "bg-bg-raised text-fg"
                      : "text-fg-secondary hover:bg-bg-raised/60 hover:text-fg"
                  )}
                >
                  {active && (
                    <span
                      className="absolute left-0 top-1.5 bottom-1.5 w-0.5 bg-accent-500 rounded-full"
                      aria-hidden
                    />
                  )}
                  {item.label}
                </Link>
              </li>
            );
          })}
        </ul>
      </nav>

      {/* Content column. Bounded to 720px and centered (spec §2). */}
      <div className="flex-1 min-w-0 overflow-y-auto">
        <div className="max-w-[720px] mx-auto px-6 md:px-10 py-8 md:py-12">
          {/* Mobile section nav (md and below). Stays light per CALM. */}
          <nav
            aria-label="Settings sections"
            className="md:hidden mb-6 -mx-2 overflow-x-auto"
          >
            <ul className="flex gap-1 px-2 whitespace-nowrap">
              {NAV.map((item) => {
                const active = isActive(item.href, pathname);
                return (
                  <li key={item.href}>
                    <Link
                      href={item.href}
                      aria-current={active ? "page" : undefined}
                      className={cn(
                        "block rounded-md px-3 py-1.5 text-[13px] transition-colors",
                        active
                          ? "bg-bg-raised text-fg"
                          : "text-fg-secondary hover:text-fg"
                      )}
                    >
                      {item.label}
                    </Link>
                  </li>
                );
              })}
            </ul>
          </nav>

          {children}
        </div>
      </div>
    </div>
  );
}
