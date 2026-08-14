/**
 * Tektos-Ultima v1 — Transcript View
 *
 * Displays the conversation transcript with real-time streaming updates
 * from the WebSocket connection. Supports code blocks, markdown rendering,
 * and streaming text with cursor animation.
 *
 * Exemplar pattern: Incremental rendering with streaming text buffers.
 */

"use client";

import React, { useRef, useEffect, useMemo, useState } from "react";
import type { WSEnvelopeClient } from "@/lib/protocol";
import type { SessionSnapshot } from "@/lib/session-store";

// ---------------------------------------------------------------------------
// Event types mapping
// ---------------------------------------------------------------------------

interface TranscriptMessage {
  id: string;
  type: "user" | "assistant" | "system";
  content: string;
  timestamp: string;
  metadata?: Record<string, unknown>;
  isStreaming?: boolean;
}

interface TranscriptEvent {
  type: "message" | "tool" | "system";
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
  onSendMessage,
  onInterrupt,
}: TranscriptProps) {
  const messages = useMemo(() => buildMessages(events, streamingContent, isStreaming), [events, streamingContent, isStreaming]);
  const bottomRef = useRef<HTMLDivElement>(null);
  const [showScrollButton, setShowScrollButton] = useState(false);

  // Auto-scroll to bottom
  useEffect(() => {
    if (bottomRef.current) {
      bottomRef.current.scrollIntoView({ behavior: "smooth" });
    }
  }, [messages.length, streamingContent]);

  // Scroll listener
  const handleScroll = (e: React.UIEvent<HTMLDivElement>) => {
    const { scrollTop, scrollHeight, clientHeight } = e.currentTarget;
    setShowScrollButton(scrollHeight - scrollTop - clientHeight > 100);
  };

  const scrollToBottom = () => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  // -----------------------------------------------------------------------
  // Render
  // -----------------------------------------------------------------------

  if (!activeSession) {
    return (
      <div className="flex-1 flex items-center justify-center">
        <div className="text-center">
          <div className="w-16 h-16 mx-auto mb-4 rounded-2xl bg-surface border border-border flex items-center justify-center">
            <svg xmlns="http://www.w3.org/2000/svg" className="w-8 h-8 text-text-muted" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M8.625 12a.375.375 0 11-.75 0 .375.375 0 01.75 0zm0 0H8.25m4.125 0a.375.375 0 11-.75 0 .375.375 0 01.75 0zm0 0H12m4.125 0a.375.375 0 11-.75 0 .375.375 0 01.75 0zm0 0h-.375M21 12c0 4.556-4.03 8.25-9 8.25a9.764 9.764 0 01-2.555-.337A5.972 5.972 0 015.41 20.97a5.969 5.969 0 01-.474-.065 4.48 4.48 0 00.978-2.025c.09-.457-.133-.901-.467-1.226C3.93 16.178 3 14.189 3 12c0-4.556 4.03-8.25 9-8.25s9 3.694 9 8.25z" />
            </svg>
          </div>
          <h3 className="text-lg font-medium text-text-primary mb-2">Welcome to Tektos</h3>
          <p className="text-sm text-text-muted max-w-md">
            Create a new session to start an AI-powered coding workflow. The system uses a local LLM to assist with code generation, debugging, and architectural decisions.
          </p>
          <div className="mt-6 flex items-center justify-center gap-4 text-xs text-text-muted">
            <span className="flex items-center gap-1">
              <svg xmlns="http://www.w3.org/2000/svg" className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M13 10V3L4 14h7v7l9-11h-7z" />
              </svg>
              Local LLM
            </span>
            <span className="flex items-center gap-1">
              <svg xmlns="http://www.w3.org/2000/svg" className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z" />
              </svg>
              100% Local
            </span>
            <span className="flex items-center gap-1">
              <svg xmlns="http://www.w3.org/2000/svg" className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z" />
              </svg>
              Self-Improving
            </span>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="transcript relative" onScroll={handleScroll}>
      {/* Messages */}
      <div className="max-w-4xl mx-auto">
        {messages.map((msg) => (
          <div
            key={msg.id}
            className={`transcript-message ${
              msg.type === "user"
                ? "transcript-message-user"
                : msg.type === "system"
                ? "flex justify-center"
                : "transcript-message-assistant"
            }`}
          >
            <div
              className={`message-bubble ${
                msg.type === "user"
                  ? "message-bubble-user"
                  : "message-bubble-assistant"
              } ${msg.isStreaming ? "animate-pulse-glow" : ""}`}
            >
              {msg.type === "system" ? (
                <div className="flex items-center gap-2 text-xs text-text-muted">
                  <svg xmlns="http://www.w3.org/2000/svg" className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                    <path strokeLinecap="round" strokeLinejoin="round" d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                  </svg>
                  <span>{msg.content}</span>
                </div>
              ) : (
                <div className="leading-relaxed">
                  {msg.type === "assistant" && msg.isStreaming && (
                    <span className="inline-block w-2 h-4 bg-accent animate-pulse ml-0.5" />
                  )}
                  <MarkdownContent content={msg.content} />
                </div>
              )}
            </div>
          </div>
        ))}
      </div>

      {/* Auto-scroll button */}
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
    }
  }

  // Push any remaining streaming message
  if (currentMessage) {
    messages.push(currentMessage);
  }

  return messages;
}

// ---------------------------------------------------------------------------
// Markdown content renderer
// ---------------------------------------------------------------------------

function MarkdownContent({ content }: { content: string }) {
  // Simple markdown parsing — for production, use react-markdown
  const renderContent = (text: string) => {
    const lines = text.split("\n");
    return lines.map((line, i) => {
      // Code blocks
      if (line.startsWith("```")) {
        return null; // Skip — handled separately
      }

      // Headers
      if (line.startsWith("### ")) {
        return (
          <h3 key={i} className="text-sm font-semibold text-text-primary mt-3 mb-1">
            {line.slice(4)}
          </h3>
        );
      }
      if (line.startsWith("## ")) {
        return (
          <h2 key={i} className="text-base font-semibold text-text-primary mt-4 mb-2">
            {line.slice(3)}
          </h2>
        );
      }
      if (line.startsWith("# ")) {
        return (
          <h1 key={i} className="text-lg font-semibold text-text-primary mt-4 mb-2">
            {line.slice(2)}
          </h1>
        );
      }

      // Lists
      if (line.startsWith("- ")) {
        return (
          <li key={i} className="ml-4 list-disc text-sm">
            {parseInline(line.slice(2))}
          </li>
        );
      }
      if (/^\d+\.\s/.test(line)) {
        return (
          <li key={i} className="ml-4 list-decimal text-sm">
            {parseInline(line.replace(/^\d+\.\s/, ""))}
          </li>
        );
      }

      // Empty lines
      if (line.trim() === "") {
        return <div key={i} className="h-2" />;
      }

      // Regular paragraph
      return (
        <p key={i} className="text-sm mb-1">
          {parseInline(line)}
        </p>
      );
    });
  };

  const parseInline = (text: string) => {
    // Bold
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

    // Code spans
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
