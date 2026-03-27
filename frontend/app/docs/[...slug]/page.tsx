import { getDocBySlug, getAllDocSlugs } from "@/lib/docs/loader";
import { MarkdownRenderer } from "@/components/docs/MarkdownRenderer";
import { notFound } from "next/navigation";
import type { Metadata } from "next";

interface DocPageProps {
  params: Promise<{ slug: string[] }>;
}

export async function generateStaticParams() {
  return getAllDocSlugs().map((slug) => ({ slug }));
}

export async function generateMetadata({
  params,
}: DocPageProps): Promise<Metadata> {
  const { slug } = await params;
  const doc = getDocBySlug(slug);

  if (!doc) {
    return { title: "Not Found" };
  }

  return {
    title: `${doc.title} | Praxis Docs`,
    description: `Documentation: ${doc.title}`,
  };
}

export default async function DocPage({ params }: DocPageProps) {
  const { slug } = await params;
  const doc = getDocBySlug(slug);

  if (!doc) {
    notFound();
  }

  return (
    <article>
      <MarkdownRenderer content={doc.content} />
    </article>
  );
}
