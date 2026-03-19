import fs from "node:fs";
import path from "node:path";

const DOCS_DIR = path.join(process.cwd(), "content", "docs");

export interface DocData {
  content: string;
  title: string;
  slug: string[];
}

/**
 * Read a markdown document by its slug segments.
 * e.g. ["architecture-overview"] → content/docs/architecture-overview.md
 * e.g. ["modules", "hot-path"] → content/docs/modules/hot-path.md
 */
export function getDocBySlug(slug: string[]): DocData | null {
  const filePath = path.join(DOCS_DIR, ...slug) + ".md";

  if (!fs.existsSync(filePath)) return null;

  const content = fs.readFileSync(filePath, "utf-8");

  // Extract title from first H1 heading
  const titleMatch = content.match(/^#\s+(.+)$/m);
  const title = titleMatch ? titleMatch[1] : slug[slug.length - 1];

  return { content, title, slug };
}

/**
 * Walk the docs directory and return all valid slug arrays
 * for use in generateStaticParams.
 */
export function getAllDocSlugs(): string[][] {
  const slugs: string[][] = [];

  function walk(dir: string, prefix: string[]) {
    if (!fs.existsSync(dir)) return;

    for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
      if (entry.isDirectory()) {
        walk(path.join(dir, entry.name), [...prefix, entry.name]);
      } else if (entry.name.endsWith(".md")) {
        const name = entry.name.replace(/\.md$/, "");
        slugs.push([...prefix, name]);
      }
    }
  }

  walk(DOCS_DIR, []);
  return slugs;
}

/**
 * Check if the docs content directory exists (i.e. copy-docs has run).
 */
export function docsExist(): boolean {
  return fs.existsSync(DOCS_DIR);
}
