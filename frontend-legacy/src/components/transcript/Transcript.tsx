/**
 * Tektos-Ultima v1 — Transcript View (Streaming Architecture)
 *
 * Replaced TranscriptEvent[] with @assistant-ui/react MessageParts:
 * - Messages are now ChatMessage[] (AssistantMessage | UserMessage)
 * - Assistant messages have parts (TextPart, ToolPart) with streaming status
 * - Uses StreamingMarkdown for incremental markdown rendering
 * - Streaming cursor, thinking indicators, completion flush
 * - Auto-scroll to keep up with streaming
 * - Clean, minimal chrome — content is the focus
 */

"use client";

import React, { useRef, useEffect, useMemo, useState, useCallback } from "react";
import type { ChatMessage } from "@/lib/streaming-store";
import { StreamingMarkdown } from "@/components/streaming/StreamingMarkdown";

// ---------------------------------------------------------------------------
// Transcript component
// ---------------------------------------------------------------------------

interface TranscriptProps {
  messages: ChatMessage[];
  isStreaming: boolean;
  onSendMessage: (message: string) => void;
  onInterrupt: () => void;
}

export function Transcript({ messages, isStreaming }: TranscriptProps) {
  const bottomRef = useRef<HTMLDivElement>(null);
  const scrollRef = useRef<HTMLDivElement>(null);
  const [autoScroll, setAutoScroll] = useState(true);

  // Auto-scroll during streaming
  useEffect(() => {
    if (autoScroll) {
      bottomRef.current?.scrollIntoView({ behavior: "smooth" });
    }
  }, [messages.length, autoScroll, isStreaming]);

  // Scroll listener to disable auto-scroll when user scrolls up
  const handleScroll = useCallback(
    (e: React.UIEvent<HTMLDivElement>) => {
      const { scrollTop, scrollHeight, clientHeight } = e.currentTarget;
      setAutoScroll(scrollHeight - scrollTop - clientHeight < 50);
    },
    []
  );

  // ---------------------------------------------------------------------------
  // Render
  // ---------------------------------------------------------------------------

  return (
    <div ref={scrollRef} className="transcript relative overflow-y-auto" onScroll={handleScroll}>
      <div className="max-w-4xl mx-auto py-6 px-4">
        {messages.map((msg) => (
          <div
            key={msg.id}
            className={`mb-6 ${
              msg.role === "user" ? "flex justify-end" : "flex justify-start"
            }`}
          >
            {msg.role === "user" ? (
              /* User message — simple text bubble */
              <div className="max-w-[80%] rounded-2xl bg-accent/10 border-accent/20 border px-4 py-3">
                <div className="text-sm leading-relaxed text-text-primary whitespace-pre-wrap">
                  {msg.content}
                </div>
              </div>
            ) : msg.role === "assistant" ? (
              /* Assistant message — streaming markdown */
              <div className="relative max-w-[80%] bg-surface border-border rounded-2xl border">
                {/* Message header */}
                <div className="flex items-center gap-2 px-4 pt-3 pb-2 border-b border-border/50">
                  <div className="w-6 h-6 rounded-full bg-gradient-to-br from-accent to-accent/60 flex items-center justify-center">
                    <svg xmlns="http://www.w3.org/2000/svg" className="w-3 h-3 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                      <path strokeLinecap="round" strokeLinejoin="round" d="M9.813 15.904L9 18.75l-.813-2.846a4.5 4.5 0 00-3.09-3.09L2.25 12l2.846-.813a4.5 4.5 0 003.09-3.09L9 5.25l.813 2.846a4.5 4.5 0 003.09 3.09L15.75 12l-2.846.813a4.5 4.5 0 003.09 3.09L15.75 12l-2.846.813a4.5 4.5 0 003.09 3.09zM18.259 8.715L18 9.75l-.259-1.035a3.375 3.375 0 00-2.455-2.456L14.25 6l1.036-.259a3.375 3.375 0 002.455-2.456L18 2.25l.259 1.035a3.375 3.375 0 002.456 2.456L21.75 6l-1.035.259a3.375 3.375 0 00-2.456 2.456zM16.894 20.567L16.5 21.75l-.394-1.183a2.25 2.25 0 00-1.423-1.423L13.5 18.75l1.183-.394a2.25 2.25 0 001.423-1.423l.394-1.183.394 1.183a2.25 2.25 0 001.423 1.423l1.183.394-1.183.394a2.25 2.25 0 00-1.423 1.423z" />
                    </svg>
                  </div>
                  <span className="text-xs font-medium text-text-secondary">AI Agent</span>
                  {msg.status === "running" && (
                    <div className="flex items-center gap-1.5 ml-auto">
                      <div className="w-1.5 h-1.5 rounded-full bg-accent animate-pulse" />
                      <span className="text-xs text-text-muted">
                        {getStreamingText(msg.parts)}
                      </span>
                    </div>
                  )}
                </div>

                {/* Content — streaming markdown */}
                <div className="px-4 pb-3 pt-2 text-sm leading-relaxed max-h-[60vh] overflow-y-auto">
                  {renderAssistantContent(msg)}
                </div>
              </div>
            ) : null}
          </div>
        ))}

        {/* Streaming indicator at bottom */}
        {isStreaming && (
          <div className="sticky bottom-0 left-0 right-0 flex items-center gap-2 px-4 py-2 bg-surface/80 backdrop-blur-sm border-t border-border/50">
            <div className="flex-1 h-1 bg-border rounded-full overflow-hidden">
              <div className="h-full bg-accent/60 animate-pulse rounded-full" />
            </div>
            <span className="text-xs text-text-muted">AI is thinking</span>
          </div>
        )}

        {/* Scroll anchor */}
        <div ref={bottomRef} />
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Helper: determine streaming status text
// ---------------------------------------------------------------------------

function getStreamingText(parts: Array<{ type: string; text?: string }>): string {
  const hasText = parts.some((p) => p.type === "text" && p.text && p.text.length > 0);
  return hasText ? "typing..." : "thinking...";
}

// ---------------------------------------------------------------------------
// Helper: render assistant message content with streaming markdown
// ---------------------------------------------------------------------------

function renderAssistantContent(msg: Extract<ChatMessage, { role: "assistant" }>): React.ReactNode {
  // Find the first text part
  const textPart = msg.parts.find((p) => p.type === "text");
  if (!textPart || !textPart.text) {
    // Empty assistant message — show nothing (will be filled by deltas)
    return null;
  }

  // Render with StreamingMarkdown which uses:
  // - TextMessagePartProvider for streaming state
  // - StreamdownTextPrimitive with mode="streaming"
  // - isRunning flag drives cursor/thinking/flush
  return (
    <StreamingMarkdown
      containerClassName="aui-md prose w-full max-w-none text-sm leading-relaxed text-foreground"
      isRunning={msg.status === "running"}
      text={textPart.text}
    />
  );
}

// ---------------------------------------------------------------------------
// TypeScript type narrowing for assistant messages
// ---------------------------------------------------------------------------

// Helper to make TypeScript happy with the role-based narrowing
function isAssistantMessage(msg: ChatMessage): msg is Extract<ChatMessage, { role: "assistant" }> {
  return msg.role === "assistant";
}
