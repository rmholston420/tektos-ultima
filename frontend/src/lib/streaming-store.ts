/**
 * Streaming message store for Tektos
 *
 * Mirrors Hermes Agent's @assistant-ui/react MessageParts architecture:
 * - Each assistant message has independent parts (Text, Tool, Reasoning)
 * - Delta events append to the current Text part
 * - isRunning flag drives streaming state machine
 * - Completed events transition to "complete" status
 *
 * This is the single source of truth for streaming state. The
 * Transcript component reads from this store via React hooks.
 */

import { useState, useCallback, useRef } from "react";

// ---------------------------------------------------------------------------
// Part types (mirrors @assistant-ui/react contract)
// ---------------------------------------------------------------------------

export type PartStatus = "running" | "complete";

export interface TextPart {
  type: "text";
  id: string;
  text: string;
  status: PartStatus;
  metadata?: Record<string, unknown>;
}

export interface ToolPart {
  type: "tool";
  id: string;
  toolName: string;
  args?: Record<string, unknown>;
  result?: unknown;
  status: PartStatus;
}

export type MessagePart = TextPart | ToolPart;

// ---------------------------------------------------------------------------
// Message types
// ---------------------------------------------------------------------------

export interface AssistantMessage {
  id: string;
  role: "assistant";
  parts: MessagePart[];
  status: PartStatus;
  timestamp: string;
}

export interface UserMessage {
  id: string;
  role: "user";
  content: string;
  timestamp: string;
}

export type ChatMessage = AssistantMessage | UserMessage;

// ---------------------------------------------------------------------------
// Streaming store hook
// ---------------------------------------------------------------------------

interface UseStreamingMessages {
  messages: ChatMessage[];
  isStreaming: boolean;
  sendMessage: (content: string) => void;
  addDelta: (text: string) => void;
  completeMessage: () => void;
  interrupt: () => void;
}

/**
 * Hook that manages the streaming message state.
 *
 * Mirrors Hermes Agent's pattern:
 * - User messages are immediate (UserMessage)
 * - Assistant messages start with a single TextPart with status="running"
 * - Each delta event appends to that TextPart's text
 * - Completion event transitions status to "complete"
 * - isStreaming is true when any message has status="running"
 */
export function useStreamingMessages(): UseStreamingMessages {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const activeAssistantId = useRef<string | null>(null);
  const [isStreaming, setIsStreaming] = useState(false);

  const sendMessage = useCallback((content: string) => {
    // Add user message
    const userMsg: UserMessage = {
      id: `user-${Date.now()}`,
      role: "user",
      content,
      timestamp: new Date().toISOString(),
    };

    // Create empty assistant message that will be filled via deltas
    const assistantMsg: AssistantMessage = {
      id: `assistant-${Date.now()}`,
      role: "assistant",
      parts: [
        {
          type: "text",
          id: "text-0",
          text: "",
          status: "running",
        },
      ],
      status: "running",
      timestamp: new Date().toISOString(),
    };

    activeAssistantId.current = assistantMsg.id;
    setIsStreaming(true);

    setMessages((prev) => [...prev, userMsg, assistantMsg]);
  }, []);

  const addDelta = useCallback((text: string) => {
    if (!activeAssistantId.current) return;

    setMessages((prev) =>
      prev.map((msg) => {
        if (msg.role !== "assistant" || msg.id !== activeAssistantId.current) {
          return msg;
        }
        if (msg.status !== "running") return msg;

        // Append text to the first text part (mirrors Hermes Agent's
        // TextMessagePartProvider which mints a fresh part on each text
        // change but keeps the same identity for streaming)
        const updatedParts = msg.parts.map((part) => {
          if (part.type === "text") {
            return { ...part, text: part.text + text };
          }
          return part;
        });

        return { ...msg, parts: updatedParts };
      })
    );
  }, []);

  const completeMessage = useCallback(() => {
    if (!activeAssistantId.current) return;

    setMessages((prev) =>
      prev.map((msg) => {
        if (msg.role !== "assistant" || msg.id !== activeAssistantId.current) {
          return msg;
        }
        // Transition from "running" to "complete"
        const updatedParts = msg.parts.map((part) => {
          if (part.type === "text") {
            return { ...part, status: "complete" as const };
          }
          return part;
        });

        return { ...msg, parts: updatedParts, status: "complete" as const };
      })
    );

    activeAssistantId.current = null;
    setIsStreaming(false);
  }, []);

  const interrupt = useCallback(() => {
    // Same as complete — just don't wait for natural completion
    if (activeAssistantId.current) {
      completeMessage();
    }
  }, [completeMessage]);

  return {
    messages,
    isStreaming,
    sendMessage,
    addDelta,
    completeMessage,
    interrupt,
  };
}
