import katex from "katex";

/** Renders a LaTeX string with KaTeX (server-safe: uses renderToString). */
export function Formula({
  latex,
  caption,
  display = true,
  className,
}: {
  latex: string;
  caption?: string | null;
  display?: boolean;
  className?: string;
}) {
  let html: string;
  try {
    html = katex.renderToString(latex, { displayMode: display, throwOnError: false, strict: "ignore" });
  } catch {
    html = `<code>${latex}</code>`;
  }
  return (
    <figure className={className ?? (display ? "my-3" : "inline")}>
      <div
        className={display ? "overflow-x-auto rl-scroll py-1 text-[15px]" : "inline"}
        dangerouslySetInnerHTML={{ __html: html }}
      />
      {caption ? <figcaption className="text-xs text-muted mt-1">{caption}</figcaption> : null}
    </figure>
  );
}
