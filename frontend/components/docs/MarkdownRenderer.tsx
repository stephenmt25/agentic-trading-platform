import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import rehypeRaw from "rehype-raw";
import rehypeSlug from "rehype-slug";
import Link from "next/link";
import type { Components } from "react-markdown";
import { MermaidDiagram } from "./MermaidDiagram";

interface MarkdownRendererProps {
  content: string;
}

function rewriteDocLink(href: string): string {
  // Strip .md extension, strip leading ./
  return (
    "/docs/" +
    href
      .replace(/\.md$/, "")
      .replace(/^\.\//, "")
  );
}

const components: Components = {
  a({ href, children, ...props }) {
    if (!href) return <span {...props}>{children}</span>;

    // Cross-document .md links → /docs/ routes
    if (href.endsWith(".md") && !href.startsWith("http")) {
      return (
        <Link href={rewriteDocLink(href)} {...props}>
          {children}
        </Link>
      );
    }

    // Anchor links (same page)
    if (href.startsWith("#")) {
      return (
        <a href={href} {...props}>
          {children}
        </a>
      );
    }

    // External links
    return (
      <a href={href} target="_blank" rel="noopener noreferrer" {...props}>
        {children}
      </a>
    );
  },

  // Detect mermaid code blocks and render with MermaidDiagram
  code({ className, children, ...props }) {
    const match = /language-mermaid/.exec(className || "");
    const codeString = String(children).replace(/\n$/, "");

    if (match) {
      return <MermaidDiagram code={codeString} />;
    }

    // Inline code (no className = no language)
    if (!className) {
      return (
        <code
          className="rounded bg-slate-800/60 px-1.5 py-0.5 text-sm text-violet-300"
          {...props}
        >
          {children}
        </code>
      );
    }

    // Fenced code block
    return (
      <code className={className} {...props}>
        {children}
      </code>
    );
  },

  // Wrap pre blocks (code blocks) in styled container
  pre({ children, ...props }) {
    return (
      <pre
        className="overflow-x-auto rounded-lg border border-slate-800 bg-[oklch(0.14_0.01_270)] p-4 text-sm"
        {...props}
      >
        {children}
      </pre>
    );
  },

  // Horizontally scrollable tables
  table({ children, ...props }) {
    return (
      <div className="my-4 overflow-x-auto">
        <table className="w-full" {...props}>
          {children}
        </table>
      </div>
    );
  },

  th({ children, ...props }) {
    return (
      <th
        className="border border-slate-700 bg-slate-800/50 px-4 py-2 text-left text-sm font-semibold text-slate-300"
        {...props}
      >
        {children}
      </th>
    );
  },

  td({ children, ...props }) {
    return (
      <td
        className="border border-slate-700 px-4 py-2 text-sm"
        {...props}
      >
        {children}
      </td>
    );
  },
};

export function MarkdownRenderer({ content }: MarkdownRendererProps) {
  return (
    <div
      className={[
        "prose prose-invert prose-slate max-w-none",
        "prose-headings:font-bold prose-headings:tracking-tight prose-headings:text-slate-100",
        "prose-h1:text-3xl prose-h1:border-b prose-h1:border-slate-800 prose-h1:pb-3 prose-h1:mb-6",
        "prose-h2:text-2xl prose-h2:mt-10 prose-h2:mb-4",
        "prose-h3:text-xl prose-h3:mt-8 prose-h3:mb-3",
        "prose-a:text-indigo-400 prose-a:no-underline hover:prose-a:text-indigo-300 hover:prose-a:underline",
        "prose-strong:text-slate-200",
        "prose-p:text-slate-300 prose-p:leading-relaxed",
        "prose-li:text-slate-300",
        "prose-hr:border-slate-800",
        "prose-blockquote:border-indigo-500/50 prose-blockquote:text-slate-400",
      ].join(" ")}
    >
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        rehypePlugins={[rehypeRaw, rehypeSlug]}
        components={components}
      >
        {content}
      </ReactMarkdown>
    </div>
  );
}
