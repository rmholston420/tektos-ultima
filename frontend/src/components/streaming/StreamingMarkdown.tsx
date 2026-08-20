/**
 * StreamingMarkdown — Hermes Agent-style streaming renderer
 *
 * Wraps @assistant-ui/react's TextMessagePartProvider + StreamdownTextPrimitive
 * to render incremental markdown as tokens arrive during streaming.
 *
 * Mirrors Hermes Agent's pattern:
 * - TextMessagePartProvider mints a fresh part object on each text change
 * - StreamdownTextPrimitive with mode="streaming" handles incomplete markdown
 * - isRunning flag drives streaming cursor, completion flush, thinking state
 * - Plain append (no smooth reveal) to avoid re-typing from first char
 * - Memoized math plugin prevents re-katex on every token
 * - Deferred syntax highlighting for performance during streaming
 */

"use client";

import { TextMessagePartProvider, useMessagePartText } from "@assistant-ui/react";
import { StreamdownTextPrimitive, type StreamdownTextComponents, tailBoundedRemend } from "@assistant-ui/react-streamdown";
import { type ComponentProps, memo, useMemo, useState, useEffect } from "react";

// ---------------------------------------------------------------------------
// Markdown processing helpers
// ---------------------------------------------------------------------------

// Headings shrink to chat scale (h1≈xl → smaller for conversation)
const HEADING_SIZES: Record<"h1" | "h2" | "h3" | "h4", string> = {
  h1: "text-[1rem] tracking-tight",
  h2: "text-[0.9375rem] tracking-tight",
  h3: "text-[0.875rem]",
  h4: "text-[0.8125rem]",
};

// Tail-bounded repair for incomplete markdown (mirrors Hermes Agent's
// preprocessWithTailRepair — fixes unclosed tags/blocks during streaming)
function preprocessWithTailRepair(text: string): string {
  try {
    return tailBoundedRemend(text);
  } catch {
    return text;
  }
}

// ---------------------------------------------------------------------------
// Markdown components
// ---------------------------------------------------------------------------

function MarkdownLink({ children, href, ...props }: ComponentProps<"a">) {
  return (
    <a
      className="underline decoration-accent/50 hover:decoration-accent"
      href={href}
      rel="noopener noreferrer"
      target="_blank"
      {...props}
    >
      {children}
    </a>
  );
}

function InlineCode({ children, className, ...props }: ComponentProps<"code">) {
  return (
    <code
      className={`rounded bg-surface/80 px-1.5 py-0.5 font-mono text-sm text-accent ${className || ""}`}
      dir="ltr"
      {...props}
    >
      {children}
    </code>
  );
}

// ---------------------------------------------------------------------------
// MarkdownTextSurface — renders the markdown with streaming support
// ---------------------------------------------------------------------------

function MarkdownTextSurface({ containerClassName }: { containerClassName?: string }) {
  const { status, text } = useMessagePartText();
  const isStreaming = status.type === "running";

  // Stable components object — prevents memo invalidation on every render
  const components = useMemo(
    (): StreamdownTextComponents =>
      ({
        h1: ({ className, ...props }: ComponentProps<"h1">) => (
          <h1 className={`my-1 font-semibold ${HEADING_SIZES.h1} ${className || ""}`} {...props} />
        ),
        h2: ({ className, ...props }: ComponentProps<"h2">) => (
          <h2 className={`my-1 font-semibold ${HEADING_SIZES.h2} ${className || ""}`} {...props} />
        ),
        h3: ({ className, ...props }: ComponentProps<"h3">) => (
          <h3 className={`my-1 font-semibold ${HEADING_SIZES.h3} ${className || ""}`} {...props} />
        ),
        h4: ({ className, ...props }: ComponentProps<"h4">) => (
          <h4 className={`my-1 font-semibold ${HEADING_SIZES.h4} ${className || ""}`} {...props} />
        ),
        p: ({ className, ...props }: ComponentProps<"p">) => (
          <p className={`leading-relaxed ${className || ""}`} {...props} />
        ),
        a: MarkdownLink,
        inlineCode: InlineCode,
        // Simple HR as quiet spacing
        hr: () => <div aria-hidden className="my-3 h-px bg-border" />,
        ul: ({ className, ...props }: ComponentProps<"ul">) => (
          <ul className={`my-1 list-disc ${className || ""}`} {...props} />
        ),
        ol: ({ className, ...props }: ComponentProps<"ol">) => (
          <ol className={`my-1 list-decimal ${className || ""}`} {...props} />
        ),
        li: ({ className, ...props }: ComponentProps<"li">) => <li className={`leading-relaxed ${className || ""}`} {...props} />,
        blockquote: ({ className, ...props }: ComponentProps<"blockquote">) => (
          <blockquote className={`border-s-2 border-border ps-3 italic text-muted-foreground ${className || ""}`} {...props} />
        ),
        // Code blocks — simple rendering without Shiki (deferred for later)
        code: ({ children, className, ...props }: ComponentProps<"code">) => {
          if (children && typeof children === "string") {
            // Fenced code block
            const numLines = children.split("\n").length;
            const langProp = (props as Record<string, unknown>)["data-language"] || "code";
            const language = typeof langProp === "string" ? langProp : "code";
            return (
              <div className="my-2 overflow-hidden rounded-lg border border-border">
                <div className="flex items-center justify-between bg-surface/50 px-3 py-1.5 text-[10px] text-text-muted">
                  <span className="truncate">{language}</span>
                  <span>{String(numLines)} lines</span>
                </div>
                <pre className="overflow-x-auto p-3 text-sm text-text-secondary">
                  <code className="font-mono">{children}</code>
                </pre>
              </div>
            );
          }
          // Inline code (already handled by inlineCode, but fallback)
          return <code className={className} {...props}>{children}</code>;
        },
      }) as StreamdownTextComponents,
    []
  );

  if (!text) return null;

  return (
    <StreamdownTextPrimitive
      components={components}
      containerClassName={`w-full max-w-none text-sm leading-relaxed text-foreground ${containerClassName || ""}`}
      mode="streaming"
      parseIncompleteMarkdown={false}
      plugins={undefined}
      preprocess={preprocessWithTailRepair}
    />
  );
}

// ---------------------------------------------------------------------------
// MarkdownTextContent — public API with TextMessagePartProvider
// ---------------------------------------------------------------------------

interface MarkdownTextContentProps {
  isRunning: boolean;
  text: string;
  containerClassName?: string;
}

/**
 * Wraps text content with TextMessagePartProvider so that:
 * - Streaming state is tracked via isRunning flag
 * - Text updates trigger incremental re-renders
 * - Completion transitions from running → complete
 */
export function MarkdownTextContent({ isRunning, text, containerClassName }: MarkdownTextContentProps) {
  return (
    <TextMessagePartProvider isRunning={isRunning} text={text}>
      <MarkdownTextSurface containerClassName={containerClassName} />
    </TextMessagePartProvider>
  );
}

// ---------------------------------------------------------------------------
// Memoized wrapper for stable identity
// ---------------------------------------------------------------------------

interface StreamingMarkdownProps {
  containerClassName?: string;
  isRunning?: boolean;
  text?: string;
}

const StreamingMarkdownImpl = memo(({ containerClassName, isRunning, text }: StreamingMarkdownProps) => {
  // If text and isRunning are provided, use the full provider wrapper
  if (text !== undefined && isRunning !== undefined) {
    return <MarkdownTextContent isRunning={isRunning} text={text} containerClassName={containerClassName} />;
  }
  // Otherwise use the bare surface (used in other contexts)
  return <MarkdownTextSurface containerClassName={containerClassName} />;
});

StreamingMarkdownImpl.displayName = 'StreamingMarkdown';

export const StreamingMarkdown = StreamingMarkdownImpl;
