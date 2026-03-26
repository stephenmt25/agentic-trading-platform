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
          className={`block rounded-md px-2 py-1 text-sm font-medium transition-colors ${
            pathname === "/docs"
              ? "bg-blue-50 text-blue-700"
              : "text-slate-500 hover:text-slate-900"
          }`}
        >
          Documentation Index
        </Link>
      </div>

      {DOC_SECTIONS.map((section) => (
        <div key={section.title}>
          <h3 className="mb-1.5 px-2 text-xs font-semibold uppercase tracking-wider text-slate-400">
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
                    className={`block rounded-md px-2 py-1 text-sm transition-colors ${
                      isActive
                        ? "bg-blue-50 text-blue-700"
                        : "text-slate-500 hover:bg-slate-100 hover:text-slate-900"
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
