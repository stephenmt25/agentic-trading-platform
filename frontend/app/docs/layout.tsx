import { DocsNav } from "@/components/docs/DocsNav";

export default function DocsLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <div className="flex min-h-full bg-white text-slate-900">
      {/* Docs sidebar */}
      <aside className="hidden w-56 shrink-0 overflow-y-auto border-r border-slate-200 bg-slate-50 p-4 lg:block">
        <DocsNav />
      </aside>

      {/* Document content */}
      <main className="min-w-0 flex-1 overflow-y-auto bg-white p-6 lg:p-10">
        <div className="mx-auto max-w-4xl">{children}</div>
      </main>
    </div>
  );
}
