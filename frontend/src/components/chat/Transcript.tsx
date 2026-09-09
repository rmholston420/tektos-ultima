"use client";

import { useEffect, useRef } from "react";
import { useStore } from "@nanostores/react";
import { $orderedMessages } from "@/lib/stores/session";
import { MessageBubble } from "./MessageBubble";

/**
 * Chronological transcript with auto-scroll-to-bottom when the user is
 * already pinned to the bottom. Preserves scroll position otherwise.
 */
export function Transcript() {
  const messages = useStore($orderedMessages);
  const scrollRef = useRef<HTMLDivElement>(null);
  const pinnedToBottom = useRef(true);

  useEffect(() => {
    const el = scrollRef.current;
    if (!el) return;
    if (pinnedToBottom.current) {
      el.scrollTop = el.scrollHeight;
    }
  }, [messages]);

  return (
    <div
      ref={scrollRef}
      onScroll={(e) => {
        const el = e.currentTarget;
        const distance = el.scrollHeight - el.scrollTop - el.clientHeight;
        pinnedToBottom.current = distance < 40;
      }}
      className="min-h-0 overflow-auto scrollbar-thin"
      data-testid="transcript"
    >
      <div className="mx-auto max-w-[760px] px-6">
        {messages.length === 0 ? (
          <EmptyState />
        ) : (
          messages.map((m) => <MessageBubble key={m.id} message={m} />)
        )}
      </div>
    </div>
  );
}

function EmptyState() {
  return (
    <div className="flex h-full min-h-[240px] items-center justify-center py-24">
      <div className="text-13 text-text-muted">
        Start a conversation. Prompts stream over WebSocket to the local Tektos gateway.
      </div>
    </div>
  );
}
