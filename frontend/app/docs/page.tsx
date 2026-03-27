import { getDocBySlug } from "@/lib/docs/loader";
import { MarkdownRenderer } from "@/components/docs/MarkdownRenderer";
import { notFound } from "next/navigation";

export const metadata = {
  title: "Documentation | Praxis Trading Platform",
  description: "Comprehensive documentation for the Praxis Trading Platform.",
};

export default function DocsIndexPage() {
  const doc = getDocBySlug(["README"]);

  if (!doc) {
    notFound();
  }

  return <MarkdownRenderer content={doc.content} />;
}
