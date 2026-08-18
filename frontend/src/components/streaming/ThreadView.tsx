/**
 * Tektos-Ultima v1 — Thread component (Hermes Agent pattern)
 * 
 * Uses @assistant-ui/react primitives:
 * - ThreadPrimitive.Root + Viewport for scrollable container
 * - MessagePrimitive.Root for individual messages
 * - useMessagePartText() + StreamdownTextPrimitive for streaming markdown
 * - useAuiState for reactive state selectors
 */

import {
  ThreadPrimitive,
  MessagePrimitive,
  useMessagePartText,
  useAuiState,
  useMessageRuntime,
  ThreadListItemPrimitive,
} from "@assistant-ui/react";
import { StreamdownTextPrimitive } from "@assistant-ui/react-streamdown";
import { memo, useCallback } from "react";

// ---------------------------------------------------------------------------
// Text part — streaming-aware markdown rendering
//
// MessagePrimitive.Parts automatically wraps Text components in
// TextMessagePartProvider context. useMessagePartText() reads from it.
// ---------------------------------------------------------------------------

const StreamingTextPart = memo(() => {
  return (
    <StreamdownTextPrimitive
      mode="streaming"
      defer
      components={{
        code: ({ children, className, ...props }: any) => {
          if (children && typeof children === "string" && children.length < 100) {
            return (
              <code
                className="bg-foreground/10 text-foreground px-1.5 py-0.5 rounded text-sm font-mono"
                {...props}
              >
                {children}
              </code>
            );
          }
          return (
            <pre className="bg-foreground/5 border-border border rounded-lg p-4 my-2 overflow-x-auto">
              <code className={className} {...props}>
                {children}
              </code>
            </pre>
          );
        },
        h1: (props: any) => <h1 className="text-xl font-bold mt-6 mb-3" {...props} />,
        h2: (props: any) => <h2 className="text-lg font-semibold mt-5 mb-2" {...props} />,
        h3: (props: any) => <h3 className="text-base font-semibold mt-4 mb-2" {...props} />,
        ul: (props: any) => <ul className="list-disc list-inside my-2 space-y-1" {...props} />,
        ol: (props: any) => <ol className="list-decimal list-inside my-2 space-y-1" {...props} />,
        li: (props: any) => <li className="ml-2" {...props} />,
        p: (props: any) => <p className="my-2" {...props} />,
        a: ({ href, children, ...props }: any) => {
          const isLocal = href?.startsWith("/") || href?.startsWith("http://localhost") || href?.startsWith("http://127.0.0.1");
          return (
            <a
              href={href}
              target={isLocal ? "_self" : "_blank"}
              rel={isLocal ? undefined : "noopener noreferrer"}
              className="text-accent hover:underline"
              {...props}
            >
              {children}
            </a>
          );
        },
        table: (props: any) => (
          <div className="my-3 overflow-x-auto">
            <table className="min-w-full border-collapse border border-border/50 text-sm" {...props} />
          </div>
        ),
        thead: (props: any) => <thead className="bg-foreground/5" {...props} />,
        th: (props: any) => <th className="border border-border/50 px-3 py-2 text-left font-semibold" {...props} />,
        td: (props: any) => <td className="border border-border/50 px-3 py-2" {...props} />,
        blockquote: (props: any) => (
          <blockquote className="border-l-4 border-accent/30 pl-4 italic text-foreground/80 my-3" {...props} />
        ),
        hr: () => <hr className="border-border/50 my-4" />,
        strong: (props: any) => <strong className="font-semibold" {...props} />,
        em: (props: any) => <em className="italic" {...props} />,
      }}
    />
  );
});

// ---------------------------------------------------------------------------
// Message components
// ---------------------------------------------------------------------------

const AssistantMessage = memo(() => {
  const messageId = useAuiState((s) => s.message.id);
  const messageRuntime = useMessageRuntime();
  const isRunning = useAuiState((s) => s.message.status?.type === "running");
  const isPlaceholder = useAuiState(
    (s) => s.message.status?.type === "running" && s.message.content.length === 0
  );
  const isLastMessage = useAuiState(
    (s) => s.thread.messages[s.thread.messages.length - 1]?.id === messageId
  );

  // Stable text getter for actions — avoids per-token re-renders
  const getMessageText = useCallback(
    () => {
      const state = messageRuntime.getState();
      const textParts = state.content
        .filter((p) => typeof p === "object" && p !== null && "type" in p && (p as any).type === "text")
        .map((p) => (typeof p === "object" && p !== null && "text" in p ? (p as any).text : ""));
      return textParts.join("");
    },
    [messageRuntime]
  );

  return (
    <MessagePrimitive.Root
      className="group flex w-full min-w-0 max-w-full flex-col gap-0 self-start overflow-hidden"
      data-role="assistant"
      data-streaming={isRunning ? "true" : undefined}
    >
      <div
        className="wrap-anywhere min-w-0 max-w-full overflow-hidden text-pretty text-sm leading-relaxed text-foreground"
        data-slot="aui_assistant-message-content"
      >
        <MessagePrimitive.Parts
          components={{
            Text: () => <StreamingTextPart />,
          }}
        />
        {isLastMessage && (isPlaceholder ? (
          <div className="mt-2 flex items-center gap-1.5">
            <div className="w-2 h-2 rounded-full bg-accent animate-pulse" />
            <span className="text-xs text-text-muted">AI is thinking...</span>
          </div>
        ) : isRunning ? (
          <div className="mt-2 flex items-center gap-1.5">
            <div className="flex gap-1">
              <div className="w-1.5 h-1.5 rounded-full bg-accent animate-bounce" style={{ animationDelay: "0ms" }} />
              <div className="w-1.5 h-1.5 rounded-full bg-accent animate-bounce" style={{ animationDelay: "150ms" }} />
              <div className="w-1.5 h-1.5 rounded-full bg-accent animate-bounce" style={{ animationDelay: "300ms" }} />
            </div>
            <span className="text-xs text-text-muted">typing...</span>
          </div>
        ) : null)}
      </div>

      {/* Footer — copy button — only visible after completion */}
      {!isRunning && (
        <div className="flex items-center gap-2 mt-2 px-4">
          <button
            onClick={() => {
              navigator.clipboard?.writeText(getMessageText());
            }}
            className="text-xs text-text-muted hover:text-text-primary transition-colors"
          >
            Copy
          </button>
        </div>
      )}
    </MessagePrimitive.Root>
  );
});

const UserMessage = memo(() => {
  return (
    <MessagePrimitive.Root
      className="group flex w-full min-w-0 max-w-full flex-col gap-0 self-end overflow-hidden"
      data-role="user"
    >
      <div className="max-w-[80%] rounded-2xl bg-accent/10 border-accent/20 border px-4 py-3">
        <MessagePrimitive.Parts
          components={{
            Text: () => <StreamingTextPart />,
          }}
        />
      </div>
    </MessagePrimitive.Root>
  );
});

// ---------------------------------------------------------------------------
// Thread component — uses ThreadPrimitive for the container
// ---------------------------------------------------------------------------

export const ThreadView = memo(function ThreadView() {
  const isStreaming = useAuiState((s) => s.thread.isRunning);
  const messages = useAuiState((s) => s.thread.messages);
  const hasMessages = messages.length > 0;

  if (!hasMessages) {
    return (
      <div className="flex-1 flex items-center justify-center">
        <div className="text-center max-w-lg px-6">
          <p className="text-sm text-text-muted">
            No messages yet. Send a message to start the conversation.
          </p>
        </div>
      </div>
    );
  }

  return (
    <ThreadPrimitive.Root className="flex-1 relative">
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
          <span className="text-xs text-text-muted">AI is thinking</span>
        </div>
      )}
    </ThreadPrimitive.Root>
  );
});
