/**
 * Tektos-Ultima v1 — Transcript View (Redesigned)
 *
 * Workflow-centered message display with:
 * - Clear visual hierarchy: user → assistant → system
 * - Code blocks with syntax-aware formatting
 * - File change indicators for agent actions
 * - Streaming cursor animation
 * - Smooth scroll and auto-scroll
 */

"use client";

import React, { useRef, useEffect, useMemo, useState } from "react";
import type { WSEnvelopeClient } from "@/lib/protocol";
import type { SessionSnapshot } from "@/lib/session-store";

// ---------------------------------------------------------------------------
// Event types
// ---------------------------------------------------------------------------

interface TranscriptMessage {
  id: string;
  type: "user" | "assistant" | "system";
  content: string;
  timestamp: string;
  metadata?: Record<string, unknown>;
  isStreaming?: boolean;
}

export interface TranscriptEvent {
  type: "message" | "tool" | "system" | "assistant.delta" | "assistant.completed" | "session.updated" | "session.created" | "system.message";
  session_id: string;
  seq: number;
  payload: Record<string, unknown>;
  timestamp: string;
}

// ---------------------------------------------------------------------------
// Transcript component
// ---------------------------------------------------------------------------

interface TranscriptProps {
  activeSession: SessionSnapshot | null;
  events: TranscriptEvent[];
  streamingContent: string;
  isStreaming: boolean;
  onSendMessage: (message: string) => void;
  onInterrupt: () => void;
}

export function Transcript({
  activeSession,
  events,
  streamingContent,
  isStreaming,
}: TranscriptProps) {
  const messages = useMemo(
    () => buildMessages(events, streamingContent, isStreaming),
    [events, streamingContent, isStreaming]
  );
  const bottomRef = useRef<HTMLDivElement>(null);
  const [showScrollButton, setShowScrollButton] = useState(false);

  // Auto-scroll
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages.length, streamingContent]);

  // Scroll listener
  const handleScroll = (e: React.UIEvent<HTMLDivElement>) => {
    const { scrollTop, scrollHeight, clientHeight } = e.currentTarget;
    setShowScrollButton(scrollHeight - scrollTop - clientHeight > 100);
  };

  const scrollToBottom = () => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  // ── Render ──────────────────────────────────────────────────

  return (
    <div className="transcript relative" onScroll={handleScroll}>
      <div className="max-w-4xl mx-auto">
        {messages.map((msg) => (
          <div
            key={msg.id}
            className="message-card mb-4"
          >
            {msg.type === "system" ? (
              /* System message — subtle */
              <div className="message-card-system flex items-center gap-2 text-xs text-text-muted px-4">
                <svg xmlns="http://www.w3.org/2000/svg" className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                </svg>
                <span>{msg.content}</span>
              </div>
            ) : msg.type === "user" ? (
              /* User message */
              <div className="message-card-user mx-4 md:mx-0 md:ml-auto md:max-w-[75%]">
                <div className="p-4 text-sm leading-relaxed">
                  {msg.content}
                </div>
              </div>
            ) : (
              /* Assistant message — rich content */
              <div className="message-card-assistant mx-4 md:mx-0 md:max-w-[85%]">
                {/* Header */}
                <div className="flex items-center gap-2 px-4 py-2 border-b border-border">
                  <div className="w-6 h-6 rounded-full bg-accent/20 flex items-center justify-center">
                    <svg xmlns="http://www.w3.org/2000/svg" className="w-3.5 h-3.5 text-accent" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                      <path strokeLinecap="round" strokeLinejoin="round" d="M9.813 15.904L9 18.75l-.813-2.846a4.5 4.5 0 00-3.09-3.09L2.25 12l2.846-.813a4.5 4.5 0 003.09-3.09L9 5.25l.813 2.846a4.5 4.5 0 003.09 3.09L15.75 12l-2.846.813a4.5 4.5 0 00-3.09 3.09z" />
                    </svg>
                  </div>
                  <span className="text-xs font-medium text-text-secondary">AI Agent</span>
                  {msg.isStreaming && (
                    <div className="flex items-center gap-1.5 ml-auto">
                      <div className="w-1.5 h-1.5 rounded-full bg-accent animate-pulse" />
                      <span className="text-xs text-text-muted">thinking...</span>
                    </div>
                  )}
                </div>

                {/* Content */}
                <div className="p-4 text-sm leading-relaxed">
                  <MarkdownContent content={msg.content} />
                  {msg.isStreaming && (
                    <span className="inline-block w-2 h-4 bg-accent animate-pulse ml-0.5" />
                  )}
                </div>
              </div>
            )}
          </div>
        ))}

        {/* Scroll to bottom button */}
        {showScrollButton && messages.length > 0 && (
          <button
            onClick={scrollToBottom}
            className="absolute bottom-4 left-1/2 -translate-x-1/2 w-10 h-10 rounded-full
                       bg-surface border border-border text-text-secondary hover:text-text-primary
                       shadow-lg flex items-center justify-center transition-all
                       hover:shadow-glow"
            title="Scroll to bottom"
          >
            <svg xmlns="http://www.w3.org/2000/svg" className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M19 14l-7 7m0 0l-7-7m7 7V3" />
            </svg>
          </button>
        )}

        {/* Streaming indicator */}
        {isStreaming && (
          <div className="absolute bottom-0 left-0 right-0 h-1 bg-accent/20">
            <div className="h-full bg-accent animate-pulse" />
          </div>
        )}

        {/* Scroll anchor */}
        <div ref={bottomRef} />
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Message builder
// ---------------------------------------------------------------------------

function buildMessages(
  events: TranscriptEvent[],
  streamingContent: string,
  isStreaming: boolean
): TranscriptMessage[] {
  const messages: TranscriptMessage[] = [];
  let currentMessage: TranscriptMessage | null = null;

  for (const event of events) {
    const eventType = event.type;

    if (eventType === "assistant.delta") {
      const content = (event.payload.text as string) ?? "";
      if (!currentMessage || currentMessage.type !== "assistant") {
        if (currentMessage) messages.push(currentMessage);
        currentMessage = {
          id: `msg-${event.seq}`,
          type: "assistant",
          content: content,
          timestamp: event.timestamp,
          isStreaming: true,
        };
      } else {
        currentMessage.content += content;
      }
    } else if (eventType === "assistant.completed") {
      if (currentMessage && currentMessage.type === "assistant") {
        currentMessage.isStreaming = false;
        messages.push(currentMessage);
        currentMessage = null;
      }
    } else if (eventType === "session.updated" || eventType === "session.created") {
      const title = event.payload.title as string;
      if (title) {
        messages.push({
          id: `sys-${event.seq}`,
          type: "system",
          content: title,
          timestamp: event.timestamp,
        });
      }
    } else if (eventType === "system.message") {
      const msg = event.payload.message as string;
      if (msg) {
        messages.push({
          id: `sys-${event.seq}`,
          type: "system",
          content: msg,
          timestamp: event.timestamp,
        });
      }
    } else if (eventType === "message") {
      // Generic message event (e.g., vision responses)
      const text = event.payload.text as string;
      if (text) {
        messages.push({
          id: `msg-${event.seq}`,
          type: "assistant",
          content: text,
          timestamp: event.timestamp,
        });
      }
    }
  }

  if (currentMessage) {
    messages.push(currentMessage);
  }

  return messages;
}

// ---------------------------------------------------------------------------
// Markdown content renderer
// ---------------------------------------------------------------------------

function MarkdownContent({ content }: { content: string }) {
  const renderContent = (text: string) => {
    const lines = text.split("\n");
    const rendered: React.ReactNode[] = [];
    let inCodeBlock = false;
    let codeContent: string[] = [];
    let codeLang = "";

    lines.forEach((line, i) => {
      // Code blocks
      if (line.startsWith("```")) {
        if (inCodeBlock) {
          rendered.push(
            <div key={`code-${i}`} className="code-block">
              <div className="code-block-header">
                <span>{codeLang || "code"}</span>
                <span className="text-[10px] opacity-50">{codeContent.length} lines</span>
              </div>
              <div className="code-block-content">
                <pre className="m-0 overflow-x-auto">
                  <code>{codeContent.join("\n")}</code>
                </pre>
              </div>
            </div>
          );
          codeContent = [];
          codeLang = "";
          inCodeBlock = false;
        } else {
          inCodeBlock = true;
          codeLang = line.slice(3).trim();
        }
        return;
      }

      if (inCodeBlock) {
        codeContent.push(line);
        return;
      }

      // Headers
      if (line.startsWith("### ")) {
        rendered.push(<h3 key={i} className="text-sm font-semibold text-text-primary mt-3 mb-1">{parseInline(line.slice(4))}</h3>);
      } else if (line.startsWith("## ")) {
        rendered.push(<h2 key={i} className="text-base font-semibold text-text-primary mt-4 mb-2">{parseInline(line.slice(3))}</h2>);
      } else if (line.startsWith("# ")) {
        rendered.push(<h1 key={i} className="text-lg font-semibold text-text-primary mt-4 mb-2">{parseInline(line.slice(2))}</h1>);
      }
      // Lists
      else if (line.startsWith("- ")) {
        rendered.push(<li key={i} className="ml-4 list-disc text-sm">{parseInline(line.slice(2))}</li>);
      } else if (/^\d+\. \s/.test(line)) {
        rendered.push(<li key={i} className="ml-4 list-decimal text-sm">{parseInline(line.replace(/^\d+\. \s/, ""))}</li>);
      }
      // Empty lines
      else if (line.trim() === "") {
        rendered.push(<div key={i} className="h-2" />);
      }
      // Regular paragraph
      else {
        rendered.push(
          <p key={i} className="text-sm mb-1">
            {parseInline(line)}
          </p>
        );
      }
    });

    return rendered;
  };

  const parseInline = (text: string) => {
    const parts: React.ReactNode[] = [];
    let remaining = text;
    let key = 0;

    const boldRegex = /\*\*(.+?)\*\*/g;
    let match;
    let lastIndex = 0;

    while ((match = boldRegex.exec(remaining)) !== null) {
      if (match.index > lastIndex) {
        parts.push(remaining.slice(lastIndex, match.index));
      }
      parts.push(
        <strong key={key++} className="font-semibold text-text-primary">
          {match[1]}
        </strong>
      );
      lastIndex = match.index + match[0].length;
    }

    if (lastIndex < remaining.length) {
      parts.push(remaining.slice(lastIndex));
    }

    const codeRegex = /`([^`]+)`/g;
    const codeParts: React.ReactNode[] = [];
    remaining = parts.join("");
    lastIndex = 0;
    key = 0;

    while ((match = codeRegex.exec(remaining)) !== null) {
      if (match.index > lastIndex) {
        codeParts.push(remaining.slice(lastIndex, match.index));
      }
      codeParts.push(
        <code key={key++} className="bg-bg-3 px-1.5 py-0.5 rounded text-sm text-accent">
          {match[1]}
        </code>
      );
      lastIndex = match.index + match[0].length;
    }

    if (lastIndex < remaining.length) {
      codeParts.push(remaining.slice(lastIndex));
    }

    return codeParts.length > 0 ? <>{codeParts}</> : <>{parts}</>;
  };

  return <>{renderContent(content)}</>;
}
