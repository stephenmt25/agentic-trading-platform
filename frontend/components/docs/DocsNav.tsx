"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { DOC_SECTIONS } from "@/lib/docs/manifest";

function slugToPath(slug: string): string {
  return `/docs/${slug}`;
}

export function DocsNav() {
  const pathname = usePathname();

  return (
    <nav className="space-y-5">
      {/* Index link */}
      <div>
        <Link
          href="/docs"
          className={`block rounded px-2 py-1 text-sm font-medium transition-colors ${
            pathname === "/docs"
              ? "bg-indigo-500/10 text-indigo-400"
              : "text-slate-400 hover:text-slate-200"
          }`}
        >
          Documentation Index
        </Link>
      </div>

      {DOC_SECTIONS.map((section) => (
        <div key={section.title}>
          <h3 className="mb-1.5 px-2 text-xs font-semibold uppercase tracking-wider text-slate-500">
            {section.title}
          </h3>
          <ul className="space-y-0.5">
            {section.docs.map((doc) => {
              const href = slugToPath(doc.slug);
              const isActive =
                pathname === href ||
                pathname === href + "/" ||
                // Handle catch-all: /docs/modules/hot-path
                pathname === `/docs/${doc.slug}`;

              return (
                <li key={doc.slug}>
                  <Link
                    href={href}
                    className={`block rounded px-2 py-1 text-sm transition-colors ${
                      isActive
                        ? "bg-indigo-500/10 text-indigo-400"
                        : "text-slate-400 hover:bg-slate-800/50 hover:text-slate-200"
                    }`}
                  >
                    {doc.label}
                  </Link>
                </li>
              );
            })}
          </ul>
        </div>
      ))}
    </nav>
  );
}
