"use client";

import { useMemo } from "react";
import { renderMarkdown } from "@/lib/markdown";
import { cn } from "@/lib/cn";

/**
 * Render Markdown safely. Wraps in a Tailwind typography-like scoped
 * class so we don't need @tailwindcss/typography as a dependency.
 */
export function Markdown({ children, className }: { children: string; className?: string }) {
  const html = useMemo(() => renderMarkdown(children ?? ""), [children]);
  return (
    <div
      className={cn("tektos-prose text-13 text-text-base leading-relaxed", className)}
      dangerouslySetInnerHTML={{ __html: html }}
    />
  );
}
