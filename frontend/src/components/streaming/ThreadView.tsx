/**
 * Tektos-Ultima v1 — ThreadView (Hermes Agent desktop rendering)
 *
 * Matches Hermes Agent chat rendering:
 * - Compact Streamdown typography (chat-scale)
 * - Directive chips (@file:, @image:, @skill:, @session:)
 * - Expandable code blocks (7.5rem collapsed max)
 * - Scaffold rows for tool calls, thinking, reasoning
 * - Status rows for subagents, background tasks
 * - Stable text rendering for tool output
 * - Personality-based intro copy for empty state
 * - Proper streaming indicators (pulsing dots + "typing...")
 */

import {
  ThreadPrimitive,
  MessagePrimitive,
  useAuiState,
  useMessageRuntime,
} from "@assistant-ui/react";
import { StreamdownTextPrimitive, type StreamdownTextComponents } from "@assistant-ui/react-streamdown";
import { memo, useCallback, useEffect, useMemo, useRef, useState } from "react";

// ---------------------------------------------------------------------------
// Directive chips — @file:, @image:, @skill:, @session: refs
// ---------------------------------------------------------------------------

const REF_SVGS: Record<string, string> = {
  file: '<path d="M13 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V9Z"/><path d="M14 2v7a2 2 0 0 1-2 2H9"/>',
  folder: '<path d="M4 20h16a2 2 0 0 0 2-2V8a2 2 0 0 0-2-2h-7.93a2 2 0 0 1-1.66-.9l-.82-1.2A2 2 0 0 0 7.93 3H4a2 2 0 0 0-2 2v13c0 1.1.9 2 2 2Z"/>',
  url: '<path d="M10 13a5 5 0 0 0 7.54.54l3-3a5 5 0 0 0-7.07-7.07l-1.72 1.71"/><path d="M14 11a5 5 0 0 0-7.54-.54l-3 3a5 5 0 0 0 7.07 7.07l1.71-1.71"/>',
  image: '<rect width="18" height="18" x="3" y="3" rx="2" ry="2"/><circle cx="9" cy="9" r="2"/><path d="m21 15-3.086-3.086a2 2 0 0 0-2.828 0L6 21"/>',
  skill: '<path d="M12 3v18"/><path d="M3 12h18"/><rect x="6" y="6" width="12" height="12" rx="2"/>',
  session: '<path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M22 21v-2a4 4 0 0 0-3-3.87"/><path d="M16 3.13a4 4 0 0 1 0 7.75"/>',
  tool: '<path d="M14.7 6.3a1 1 0 0 0 0 1.4l1.6 1.6a1 1 0 0 0 1.4 0l3.77-3.77a6 6 0 0 1-7.94 7.94l-6.91 6.91a2.12 2.12 0 0 1-3-3l6.91-6.91a6 6 0 0 1 7.94-7.94l-3.76 3.76z"/>',
  terminal: '<polyline points="4 17 10 11 4 5"/><line x1="12" x2="20" y1="19" y2="19"/>',
};

function refLabel(type: string, id: string): string {
  const clean = id.replace(/^\.\/|`|"|'/g, "").replace(/["']$/g, "");
  if (type === "url") {
    try {
      const u = new URL(clean);
      return `${u.hostname}${u.pathname}`.replace(/\/$/, "").slice(0, 40);
    } catch {
      return clean.slice(0, 40);
    }
  }
  if (type === "terminal") return clean || "terminal";
  return clean || type;
}

const DirectiveChip = memo(function DirectiveChip({
  type,
  label,
  id,
}: {
  type: string;
  label: string;
  id: string;
}) {
  const svg = REF_SVGS[type] || REF_SVGS.file;
  return (
    <span
      className="inline-flex shrink-0 items-center gap-0.5 rounded bg-muted/60 px-1 py-0.5 text-xs font-mono text-muted-foreground/80"
    >
      <svg
        className="size-3 shrink-0"
        fill="none"
        stroke="currentColor"
        strokeLinecap="round"
        strokeLinejoin="round"
        strokeWidth={2}
        viewBox="0 0 24 24"
      >
        <path d={svg} />
      </svg>
      <span className="max-w-[120px] truncate">{label}</span>
    </span>
  );
});

// Parse @type:value directives from text
const DIRECTIVE_RE = /@([a-z][\w-]*):(`[^`]+`|"[^"]+"|'[^']+'|\S+)/g;

function parseDirectives(text: string) {
  type Segment = { kind: "text"; text: string } | { kind: "ref"; type: string; id: string };
  const segments: Segment[] = [];
  let cursor = 0;
  for (const match of text.matchAll(DIRECTIVE_RE)) {
    if (match.index !== undefined && match.index > cursor) {
      segments.push({ kind: "text", text: text.slice(cursor, match.index) });
    }
    const type = match[1];
    const raw = match[2].replace(/^[`"']|[`"']$/g, "");
    segments.push({ kind: "ref", type, id: raw });
    cursor = (match.index ?? 0) + match[0].length;
  }
  if (cursor < text.length) {
    segments.push({ kind: "text", text: text.slice(cursor) });
  }
  return segments;
}

const DirectiveContent = memo(function DirectiveContent({ text }: { text: string }) {
  const segments = useMemo(() => parseDirectives(text), [text]);
  return (
    <span className="whitespace-pre-line">
      {segments.map((seg, i) =>
        seg.kind === "text" ? (
          <span key={`t-${i}`}>{seg.text}</span>
        ) : (
          <DirectiveChip
            key={`r-${i}`}
            type={seg.type}
            label={refLabel(seg.type, seg.id)}
            id={seg.id}
          />
        ),
      )}
    </span>
  );
});

// ---------------------------------------------------------------------------
// Expandable block — collapsible container (7.5rem collapsed, expandable)
// ---------------------------------------------------------------------------

const ExpandableBlock = memo(function ExpandableBlock({
  children,
  className,
}: {
  children: React.ReactNode;
  className?: string;
}) {
  const ref = useRef<HTMLDivElement>(null);
  const [expanded, setExpanded] = useState(false);
  const [overflowing, setOverflowing] = useState(false);

  useEffect(() => {
    const el = ref.current;
    if (el) setOverflowing(el.scrollHeight > 121);
  }, [children]);

  return (
    <div className="relative">
      <div
        ref={ref}
        className={["overflow-y-auto overflow-x-auto", expanded ? "max-h-[40dvh]" : "max-h-[7.5rem]", className].filter(Boolean).join(" ")}
      >
        {children}
      </div>
      {overflowing && (
        <div className="pointer-events-none absolute inset-x-0 bottom-0 flex h-7 justify-end bg-gradient-to-t from-[var(--ui-chat-surface-background)] to-transparent">
          <button
            aria-expanded={expanded}
            aria-label={expanded ? "Collapse" : "Expand"}
            className="pointer-events-auto flex h-7 w-9 cursor-pointer items-end justify-center pb-1 text-muted-foreground/70 transition-colors hover:text-foreground"
            onClick={() => setExpanded((v) => !v)}
            type="button"
          >
            <svg className={`size-3.5 transition-transform ${expanded ? "rotate-180" : ""}`} fill="none" stroke="currentColor" viewBox="0 0 24 24" strokeWidth={2}>
              <path d="m6 9 6 6 6-6" />
            </svg>
          </button>
        </div>
      )}
    </div>
  );
});

// ---------------------------------------------------------------------------
// Scaffold row — thinking header, tool group header, activity timer
// ---------------------------------------------------------------------------

const ScaffoldRow = memo(function ScaffoldRow({
  children,
  onToggle,
  open,
  trailing,
}: {
  children: React.ReactNode;
  onToggle?: () => void;
  open?: boolean;
  trailing?: React.ReactNode;
}) {
  return (
    <div className="group/disclosure-row relative flex w-full max-w-full min-w-0 text-[var(--ui-text-tertiary)]">
      <button
        disabled={!onToggle}
        onClick={onToggle}
        type="button"
        className={`flex min-w-0 max-w-fit items-start gap-1.5 text-left transition-colors ${onToggle ? "hover:text-foreground focus-visible:text-foreground" : "cursor-default"}`}
      >
        <span className="flex min-w-0 flex-col gap-0.5">{children}</span>
        {onToggle && (
          <span className={`flex h-[var(--conversation-line-height)] shrink-0 items-center justify-center transition-opacity ${open ? "opacity-80" : "opacity-30 group-hover/disclosure-row:opacity-80"}`}>
            <svg className="size-3" fill="none" stroke="currentColor" viewBox="0 0 24 24" strokeWidth={2}>
              <path d="m6 9 6 6 6-6" />
            </svg>
          </span>
        )}
      </button>
      {trailing && <span className="flex h-[var(--conversation-line-height)] shrink-0 items-center pl-1.5">{trailing}</span>}
    </div>
  );
});

// ---------------------------------------------------------------------------
// Status row — subagents, background tasks, queued prompts
// ---------------------------------------------------------------------------

const StatusRow = memo(function StatusRow({
  children,
  leading,
  trailing,
  onActivate,
}: {
  children: React.ReactNode;
  leading?: React.ReactNode;
  trailing?: React.ReactNode;
  onActivate?: () => void;
}) {
  return (
    <div
      className={`group/status-row flex min-h-6 items-center gap-2 rounded-md px-1.5 py-1 ${onActivate ? "hover:bg-[var(--ui-row-hover-background)]" : "hover:bg-[var(--ui-row-hover-background)]"}`}
      onClick={onActivate}
    >
      {leading !== undefined && <span className="flex size-3.5 shrink-0 items-center justify-center">{leading}</span>}
      <div className="flex min-w-0 flex-1 items-center gap-2">{children}</div>
      {trailing && (
        <div className="flex shrink-0 items-center gap-0.5 opacity-0 group-hover/status-row:opacity-100">{trailing}</div>
      )}
    </div>
  );
});

// ---------------------------------------------------------------------------
// Stable text — for tool output, terminal output
// ---------------------------------------------------------------------------

const StableText = memo(function StableText({ text }: { text: string }) {
  const lines = text.split("\n").filter(Boolean);
  if (lines.length === 0) return null;
  return (
    <div className="group/stable relative">
      <pre className="font-mono text-[0.75rem] leading-relaxed text-muted-foreground/80">
        <code className="whitespace-pre-wrap break-words">{text}</code>
      </pre>
    </div>
  );
});

// ---------------------------------------------------------------------------
// Markdown text part — compact Streamdown rendering (Hermes Agent style)
// ---------------------------------------------------------------------------

const MARKDOWN_CONTAINER_CLASS =
  "aui-md w-full max-w-none overflow-hidden text-sm leading-relaxed text-foreground";

// Heading sizes matching Hermes Agent desktop (chat-scale, not prose)
const HEADING_SIZES: Record<"h1" | "h2" | "h3" | "h4", string> = {
  h1: "text-[1rem] tracking-tight my-1 font-semibold",
  h2: "text-[0.9375rem] tracking-tight my-1 font-semibold",
  h3: "text-[0.875rem] my-1 font-semibold",
  h4: "text-[0.8125rem] my-1 font-semibold",
};

// Shared streamdown components config
const STREAMDOWN_COMPONENTS: StreamdownTextComponents = {
  h1: ({ className, ...props }) => <h1 className={`${HEADING_SIZES.h1} ${className ?? ""}`} {...props} />,
  h2: ({ className, ...props }) => <h2 className={`${HEADING_SIZES.h2} ${className ?? ""}`} {...props} />,
  h3: ({ className, ...props }) => <h3 className={`${HEADING_SIZES.h3} ${className ?? ""}`} {...props} />,
  h4: ({ className, ...props }) => <h4 className={`${HEADING_SIZES.h4} ${className ?? ""}`} {...props} />,
  p: ({ className, ...props }) => <p className={`leading-relaxed ${className ?? ""}`} {...props} />,
  code: ({ className, ...props }) => (
    <code className="rounded bg-muted/80 px-1 py-0.5 font-mono text-[0.9em] text-muted-foreground" {...props} />
  ),
  pre: ({ children, className, ...props }) => (
    <ExpandableBlock className="rounded-md border border-[var(--ui-stroke-tertiary)] bg-muted/35 p-2">
      <pre className={`overflow-x-auto font-mono text-[0.75rem] leading-relaxed ${className ?? ""}`} {...props}>
        {children}
      </pre>
    </ExpandableBlock>
  ),
  blockquote: ({ className, ...props }) => (
    <blockquote className={`mt-2 mb-2 border-l-2 border-[var(--ui-stroke-tertiary)] pl-2.5 italic text-muted-foreground/85 ${className ?? ""}`} {...props} />
  ),
  hr: () => <hr className="my-2 border-[var(--ui-stroke-tertiary)]" />,
  ul: ({ className, ...props }) => <ul className={`mb-2 list-disc pl-5 last:mb-0 ${className ?? ""}`} {...props} />,
  ol: ({ className, ...props }) => <ol className={`mb-2 list-decimal pl-5 last:mb-0 ${className ?? ""}`} {...props} />,
  li: ({ className, ...props }) => <li className={`marker:text-muted-foreground/60 ${className ?? ""}`} {...props} />,
  table: ({ children, className, ...props }) => (
    <div className="mb-2 max-w-full overflow-x-auto rounded-md border border-[var(--ui-stroke-tertiary)] last:mb-0">
      <table className={`w-full border-collapse text-xs [&_tr]:border-b [&_tr]:border-[var(--ui-stroke-tertiary)] last:[&_tr]:border-0 ${className ?? ""}`} {...props}>
        {children}
      </table>
    </div>
  ),
  th: ({ className, ...props }) => <th className={`px-2 py-1 text-left text-[0.62rem] font-semibold uppercase tracking-[0.08em] text-muted-foreground/80 ${className ?? ""}`} {...props} />,
  td: ({ className, ...props }) => <td className={`px-2 py-1 align-top leading-snug ${className ?? ""}`} {...props} />,
  a: ({ href, children, className, ...props }) => {
    const isLocal = href?.startsWith("/") || href?.startsWith("http://localhost");
    return (
      <a
        className={`text-accent hover:underline ${className ?? ""}`}
        href={href}
        target={isLocal ? "_self" : "_blank"}
        rel={isLocal ? undefined : "noopener noreferrer"}
        {...props}
      >
        {children}
      </a>
    );
  },
};

const StreamingTextPart = memo(function StreamingTextPart() {
  return (
    <div className={MARKDOWN_CONTAINER_CLASS}>
      <StreamdownTextPrimitive components={STREAMDOWN_COMPONENTS} />
    </div>
  );
});

// ---------------------------------------------------------------------------
// Message components — assistant and user
// ---------------------------------------------------------------------------

const AssistantMessage = memo(function AssistantMessage() {
  const messageId = useAuiState((s) => s.message.id);
  const isRunning = useAuiState((s) => s.message.status?.type === "running");
  const isPlaceholder = useAuiState((s) => s.message.status?.type === "running" && s.message.content.length === 0);
  const isLastMessage = useAuiState((s) => s.thread.messages[s.thread.messages.length - 1]?.id === messageId);
  const messageRuntime = useMessageRuntime();

  const getMessageText = useCallback(() => {
    const state = messageRuntime.getState();
    const textParts = state.content
      .filter((p) => typeof p === "object" && p !== null && "type" in p && (p as any).type === "text")
      .map((p) => (typeof p === "object" && p !== null && "text" in p ? (p as any).text : ""));
    return textParts.join("");
  }, [messageRuntime]);

  return (
    <MessagePrimitive.Root
      className="group flex w-full min-w-0 max-w-full flex-col gap-0 self-start overflow-hidden"
      data-role="assistant"
      data-streaming={isRunning ? "true" : undefined}
    >
      {/* Message content */}
      <div
        className="wrap-anywhere min-w-0 max-w-full overflow-hidden text-pretty text-sm leading-relaxed text-foreground"
      >
        <MessagePrimitive.Parts
          components={{
            Text: () => <StreamingTextPart />,
          }}
        />
      </div>

      {/* Streaming indicator */}
      {isLastMessage && (isPlaceholder ? (
        <div className="mt-2 flex items-center gap-1.5">
          <div className="w-2 h-2 rounded-full bg-accent animate-pulse" />
          <span className="text-xs text-muted-foreground">AI is thinking...</span>
        </div>
      ) : isRunning ? (
        <div className="mt-2 flex items-center gap-1.5">
          <div className="flex gap-1">
            <div className="w-1.5 h-1.5 rounded-full bg-accent animate-bounce" style={{ animationDelay: "0ms" }} />
            <div className="w-1.5 h-1.5 rounded-full bg-accent animate-bounce" style={{ animationDelay: "150ms" }} />
            <div className="w-1.5 h-1.5 rounded-full bg-accent animate-bounce" style={{ animationDelay: "300ms" }} />
          </div>
          <span className="text-xs text-muted-foreground">typing...</span>
        </div>
      ) : null)}

      {/* Footer — copy button (only after completion) */}
      {!isRunning && (
        <div className="flex items-center gap-2 mt-2 px-4">
          <button
            onClick={() => navigator.clipboard?.writeText(getMessageText())}
            className="text-xs text-muted-foreground hover:text-foreground transition-colors"
          >
            Copy
          </button>
        </div>
      )}
    </MessagePrimitive.Root>
  );
});

const UserMessage = memo(function UserMessage() {
  return (
    <MessagePrimitive.Root
      className="group flex w-full min-w-0 max-w-full flex-col gap-0 self-end overflow-hidden"
      data-role="user"
    >
      <div className="max-w-[80%] rounded-2xl bg-accent/10 border-accent/20 border px-4 py-3">
        <MessagePrimitive.Parts
          components={{
            Text: ({ text }: { text: string }) => (
              <p className="text-sm leading-relaxed whitespace-pre-wrap">{text}</p>
            ),
          }}
        />
      </div>
    </MessagePrimitive.Root>
  );
});

// ---------------------------------------------------------------------------
// Intro — empty state (Hermes Agent personality-based copy)
// ---------------------------------------------------------------------------

const WORDMARK = 'TEKTOS';

const INTRO_COPIES = [
  { headline: "What are we moving today?", body: "Send a bug, branch, plan, or rough idea. I'll inspect the repo and turn it into the next concrete step." },
  { headline: "What's on your mind?", body: "Bring the code, question, or stuck part. I'll read the room before making changes." },
  { headline: "What should Tektos look at?", body: "Send the task, failing path, or half-formed plan. I'll help turn it into action." },
  { headline: "Where should we start?", body: "Send the context you have. I'll help sort it into a plan or a fix." },
  { headline: "What needs attention?", body: "Send the context you have. I'll help sort it into a plan or a fix." },
];

const Intro = memo(function Intro() {
  const copy = INTRO_COPIES[Math.floor(Math.random() * INTRO_COPIES.length)];
  return (
    <div
      className="pointer-events-none flex w-full min-w-0 flex-col items-center justify-center px-0.5 py-6 text-center text-muted-foreground sm:px-6 lg:px-8"
      data-slot="aui_intro"
    >
      <div className="w-full min-w-0">
        <p
          aria-label={WORDMARK}
          className="fit-text mx-auto mb-1 w-[calc(100%-1rem)] font-['Collapse'] font-bold uppercase leading-[0.9] tracking-[0.08em] text-midground mix-blend-plus-lighter dark:text-foreground/90"
          style={{ '--fit-min': '2.75rem' } as React.CSSProperties}
        >
          <span>{WORDMARK}</span>
          <span aria-hidden="true">{WORDMARK}</span>
        </p>
        <p className="m-0 text-center leading-normal tracking-tight max-w-[34rem] mx-auto" style={{ color: 'var(--text-tertiary)' }}>{copy.body}</p>
      </div>
    </div>
  );
});

// ---------------------------------------------------------------------------
// Thread component — container with viewport, messages, streaming indicator
// ---------------------------------------------------------------------------

export function ThreadView() {
  const isStreaming = useAuiState((s) => s.thread.isRunning);
  const messages = useAuiState((s) => s.thread.messages);
  const hasMessages = messages.length > 0;

  if (!hasMessages) {
    return <Intro />;
  }

  return (
    <ThreadPrimitive.Root className="relative flex-1 min-h-0">
      <ThreadPrimitive.Viewport className="flex-1 overflow-y-auto">
        <ThreadPrimitive.Messages
          components={{
            UserMessage: UserMessage,
            AssistantMessage: AssistantMessage,
          }}
        />
      </ThreadPrimitive.Viewport>
      {isStreaming && (
        <div className="sticky bottom-0 left-0 right-0 flex items-center gap-2 px-4 py-2 bg-surface/80 backdrop-blur-sm border-t border-border/50">
          <div className="flex-1 h-1 bg-border rounded-full overflow-hidden">
            <div className="h-full bg-accent/60 animate-pulse rounded-full" />
          </div>
          <span className="text-xs text-muted-foreground">AI is thinking</span>
        </div>
      )}
    </ThreadPrimitive.Root>
  );
}
