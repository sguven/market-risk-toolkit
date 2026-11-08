import ReactMarkdown from "react-markdown";
import remarkMath from "remark-math";
import remarkGfm from "remark-gfm";
import rehypeKatex from "rehype-katex";
import { cn } from "@/lib/utils";

/** Markdown with GFM tables and $...$ / $$...$$ LaTeX. */
export function Markdown({ children, className }: { children: string; className?: string }) {
  return (
    <div className={cn("rl-prose", className)}>
      <ReactMarkdown remarkPlugins={[remarkGfm, remarkMath]} rehypePlugins={[rehypeKatex]}>
        {children}
      </ReactMarkdown>
    </div>
  );
}
