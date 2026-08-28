/**
 * ChatPage — Tektos chat interface mirroring Hermes desktop GUI.
 *
 * Layout:
 *   ┌─────────────────────────────────────────────────────────────┐
 *   │ Thread (scrollable messages)                                │
 *   │                                                             │
 *   │   [User bubble]                                             │
 *   │   [Assistant message with markdown/code]                    │
 *   │   [User bubble]                                             │
 *   │   [Assistant message with markdown/code]                    │
 *   │                                                             │
 *   │   ┌───────────────────────────────────────────────────────┐ │
 *   │   │ ChatBar (composer with attachments, slash commands)   │ │
 *   │   └───────────────────────────────────────────────────────┘ │
 *   └─────────────────────────────────────────────────────────────┘
 *
 * Uses @heroicons/react for icons, shared ProtocolClient for WebSocket.
 * Receives protocolClient and sessionStore from parent to share the
 * same WebSocket connection — no independent connections.
 */

"use client";

import React, {
  useRef,
  useEffect,
  useState,
  useCallback,
  useMemo,
} from "react";
import {
  PaperAirplaneIcon,
  StopIcon,
  ChevronDownIcon,
  ChevronUpIcon,
} from "@heroicons/react/24/outline";
import {
  SparklesIcon,
  ChatBubbleLeftIcon,
} from "@heroicons/react/24/solid";
import type {
  WSEnvelopeClient,
  ConnectionState,
} from "@/lib/protocol";
import { ProtocolClient, EventType } from "@/lib/protocol";
import type { SessionSnapshot, SessionEvent } from "@/lib/session-store";
import { SessionStore } from "@/lib/session-store";

// ---------------------------------------------------------------------------
// Props
// ---------------------------------------------------------------------------

interface ChatPageProps {
  activeSessionId: string;
  onSelectSession: (sessionId: string) => void;
  onCreateSession: () => void;
  connectionState: ConnectionState;
  activeModel: string;
  onModelChange: (modelId: string) => void;
  isActive: boolean;
  // Shared WebSocket connection from parent
  protocolClient: ProtocolClient;
  sessionStore: SessionStore;
}

// ---------------------------------------------------------------------------
// ChatMessage type — mirrors Hermes desktop's ChatMessage
// ---------------------------------------------------------------------------

interface ChatMessagePart {
  type: string;
  text?: string;
  [key: string]: unknown;
}

interface ChatMessage {
  id: string;
  role: "user" | "assistant" | "system";
  parts: ChatMessagePart[];
  timestamp?: number;
  completedAt?: number;
  pending?: boolean;
  error?: string;
  interim?: boolean;
  durationS?: number;
  attachmentRefs?: string[];
  rowId?: number;
  reactions?: Array<{ author: string; emoji: string }>;
}

// ---------------------------------------------------------------------------
// Thread — the message list (mirrors Hermes desktop's Thread component)
// ---------------------------------------------------------------------------

function Thread({
  messages,
  loading,
  onBranchInNewChat,
  onCancel,
  onDismissError,
  onRestoreToMessage,
}: {
  messages: ChatMessage[];
  loading?: "response" | "session";
  onBranchInNewChat?: (messageId: string) => void;
  onCancel?: () => Promise<void> | void;
  onDismissError?: (messageId: string) => void;
  onRestoreToMessage?: (messageId: string, target?: { text?: string; userOrdinal?: number | null }) => Promise<void>;
}) {
  const scrollRef = useRef<HTMLDivElement>(null);

  // Auto-scroll to bottom on new messages
  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [messages.length]);

  if (messages.length === 0) {
    return (
      <div className="flex min-h-0 w-full flex-col items-center justify-center">
        <div className="text-center space-y-4">
          <h2 className="text-2xl font-semibold text-foreground">Welcome to Tektos</h2>
          <p className="text-sm text-muted-foreground">Create a session to start chatting</p>
        </div>
      </div>
    );
  }

  return (
    <div ref={scrollRef} className="flex-1 overflow-y-auto overflow-x-hidden px-4 py-4">
      <div className="flex flex-col gap-4 max-w-4xl mx-auto">
        {messages.map((msg, idx) => {
          if (msg.role === "user") {
            return (
              <UserMessage key={msg.id} message={msg} idx={idx} />
            );
          }
          if (msg.role === "assistant") {
            return (
              <AssistantMessage
                key={msg.id}
                message={msg}
                idx={idx}
                onBranchInNewChat={onBranchInNewChat}
                onDismissError={onDismissError}
              />
            );
          }
          if (msg.role === "system") {
            return (
              <SystemMessage key={msg.id} message={msg} />
            );
          }
          return null;
        })}
      </div>
      {loading === "session" && (
        <div className="flex items-center justify-center py-8">
          <div className="animate-spin rounded-full h-6 w-6 border-b-2 border-foreground" />
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// UserMessage — renders a user message bubble
// ---------------------------------------------------------------------------

function UserMessage({
  message,
  idx,
}: {
  message: ChatMessage;
  idx: number;
}) {
  const text = message.parts
    .filter((c) => c.type === "text")
    .map((c) => (c as { text?: string }).text ?? "")
    .join("");

  return (
    <div className="flex w-full min-w-0 max-w-full flex-col gap-1 self-end">
      <div className="group/user-message sticky z-40 -mx-4 flex w-[calc(100%+2rem)] min-w-0 max-w-none flex-col items-stretch gap-1.5 overflow-y-auto rounded-xl border bg-[var(--dt-user-bubble)] px-3 py-2 text-left text-[length:var(--conversation-text-font-size)] leading-[var(--dt-line-height)] text-foreground/95 transition-colors border-[var(--ui-stroke-tertiary)] hover:border-[var(--ui-stroke-secondary)]">
        <div className="wrap-anywhere">{text}</div>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// AssistantMessage — renders an assistant message with markdown/code
// ---------------------------------------------------------------------------

function AssistantMessage({
  message,
  idx,
  onBranchInNewChat,
  onDismissError,
}: {
  message: ChatMessage;
  idx: number;
  onBranchInNewChat?: (messageId: string) => void;
  onDismissError?: (messageId: string) => void;
}) {
  const isRunning = message.pending && !message.error;
  const hasError = !!message.error;
  const text = message.parts
    .filter((c) => c.type === "text")
    .map((c) => (c as { text?: string }).text ?? "")
    .join("");

  return (
    <div
      className="group flex w-full min-w-0 max-w-full flex-col gap-0 self-start overflow-hidden"
      data-role="assistant"
      data-slot="aui_assistant-message-root"
    >
      <div
        className="wrap-anywhere min-w-0 max-w-full overflow-hidden text-pretty text-[length:var(--conversation-text-font-size)] leading-[var(--dt-line-height)] text-foreground"
        data-slot="aui_assistant-message-content"
      >
        {text && <div className="prose prose-sm max-w-none">{text}</div>}
        {isRunning && (
          <div className="mt-1 flex items-center gap-2 text-xs text-muted-foreground">
            <div className="animate-spin rounded-full h-3 w-3 border-b-2 border-foreground" />
            <span>Thinking...</span>
          </div>
        )}
        {hasError && (
          <div className="mt-1.5 flex flex-col gap-1.5 rounded-lg border border-[color-mix(in_srgb,var(--dt-destructive)_35%,transparent)] bg-[color-mix(in_srgb,var(--dt-destructive)_7%,transparent)] px-3 py-2 text-[0.78rem] leading-5 text-[color-mix(in_srgb,var(--dt-destructive)_78%,var(--ui-text-secondary))]">
            <div className="flex items-start gap-1.5">
              <div className="min-w-0 flex-1">
                <div className="font-medium">Error</div>
                <div>{String(message.error || "Unknown error")}</div>
              </div>
              {onDismissError && (
                <button
                  className="-my-0.5 shrink-0 text-current opacity-70 hover:opacity-100"
                  onClick={() => onDismissError(message.id)}
                >
                  ✕
                </button>
              )}
            </div>
          </div>
        )}
      </div>
      {isRunning && (
        <span
          aria-hidden="true"
          className="hidden"
          data-message-streaming="true"
          data-slot="aui_message-streaming-marker"
        />
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// SystemMessage — renders a system message
// ---------------------------------------------------------------------------

function SystemMessage({ message }: { message: ChatMessage }) {
  const text = message.parts
    .filter((c) => c.type === "text")
    .map((c) => (c as { text?: string }).text ?? "")
    .join("");

  return (
    <div className="flex w-full min-w-0 flex-col items-stretch">
      <div className="flex max-w-[min(86%,44rem)] flex-col gap-0.5 self-center px-2 py-0.5 text-[0.6875rem] leading-5 text-muted-foreground/60">
        <span className="wrap-anywhere">{text}</span>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// ChatBar — the composer input bar (mirrors Hermes desktop's ChatBar)
// ---------------------------------------------------------------------------

function ChatBar({
  busy,
  disabled,
  onCancel,
  onSubmit,
}: {
  busy: boolean;
  disabled: boolean;
  onCancel?: () => Promise<void> | void;
  onSubmit: (text: string) => void;
}) {
  const [inputValue, setInputValue] = useState("");
  const [showModelPicker, setShowModelPicker] = useState(false);
  const [models, setModels] = useState<string[]>([]);
  const [modelError, setModelError] = useState<string | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  // Fetch available models
  useEffect(() => {
    fetch("/api/models")
      .then((r) => r.json())
      .then((data: any[]) => {
        const names = data.map((m: any) => m.name || m.model_name || "");
        setModels(names.filter(Boolean));
      })
      .catch(() => setModelError("Failed to load models"));
  }, []);

  const handleSend = useCallback(() => {
    const text = inputValue.trim();
    if (!text || busy) return;
    onSubmit(text);
    setInputValue("");
  }, [inputValue, busy, onSubmit]);

  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent<HTMLInputElement>) => {
      if (e.key === "Enter" && !e.shiftKey) {
        e.preventDefault();
        handleSend();
      }
    },
    [handleSend]
  );

  return (
    <div className="flex-shrink-0 border-t border-border/50 bg-surface px-3 py-2">
      <div className="flex items-center gap-2 max-w-4xl mx-auto">
        {/* Model picker */}
        <div className="relative">
          <button
            onClick={() => setShowModelPicker(!showModelPicker)}
            className="flex items-center gap-1 px-2 py-1.5 text-xs text-text-muted hover:text-text-primary rounded-md hover:bg-surface-hover transition-colors"
            title="Switch model"
          >
            <SparklesIcon className="h-3.5 w-3.5" />
            <span className="max-w-[8rem] truncate">
              —
            </span>
            {showModelPicker ? (
              <ChevronUpIcon className="h-3 w-3" />
            ) : (
              <ChevronDownIcon className="h-3 w-3" />
            )}
          </button>

          {showModelPicker && (
            <div className="absolute bottom-full left-0 mb-1 w-64 bg-surface border border-border rounded-lg shadow-lg z-20 max-h-48 overflow-y-auto">
              {models.map((model) => (
                <button
                  key={model}
                  onClick={() => setShowModelPicker(false)}
                  className="w-full text-left px-3 py-1.5 text-xs hover:bg-surface-hover transition-colors truncate text-text-muted"
                >
                  {model.split("/").slice(-1)[0]}
                </button>
              ))}
              {modelError && (
                <div className="px-3 py-1.5 text-xs text-destructive">
                  {modelError}
                </div>
              )}
            </div>
          )}
        </div>

        {/* Input field */}
        <div className="flex-1 relative">
          <input
            ref={inputRef}
            type="text"
            value={inputValue}
            onChange={(e) => setInputValue(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Type a message..."
            className="w-full bg-bg-3 border border-border rounded-lg px-3 py-2 text-sm placeholder-text-muted focus:border-accent focus:ring-1 focus:ring-accent/20 transition-all"
            disabled={disabled}
          />
        </div>

        {/* Send / Interrupt buttons */}
        {busy ? (
          <button
            onClick={onCancel}
            className="h-9 w-9 flex items-center justify-center rounded-lg bg-destructive/20 text-destructive hover:bg-destructive/30 transition-all"
            title="Interrupt"
          >
            <StopIcon className="h-4 w-4" />
          </button>
        ) : (
          <button
            onClick={handleSend}
            disabled={!inputValue.trim()}
            className="h-9 w-9 flex items-center justify-center rounded-lg bg-accent text-white hover:bg-accent-hover transition-all disabled:opacity-30 disabled:cursor-not-allowed"
            title="Send"
          >
            <PaperAirplaneIcon className="h-4 w-4 rotate-90" />
          </button>
        )}

        {/* Event log toggle */}
        <button
          className="h-9 w-9 flex items-center justify-center rounded-lg text-text-muted hover:text-text-primary hover:bg-surface-hover transition-all"
          title="Event log"
        >
          <ChatBubbleLeftIcon className="h-4 w-4" />
        </button>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// ChatPage — main component
// ---------------------------------------------------------------------------

export default function ChatPage({
  activeSessionId,
  connectionState,
  activeModel,
  onModelChange,
  isActive,
  protocolClient,
  sessionStore,
}: ChatPageProps) {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [busy, setBusy] = useState(false);
  const [sessionTitle, setSessionTitle] = useState("New Session");
  const [eventLog, setEventLog] = useState<WSEnvelopeClient[]>([]);
  const [showEventLog, setShowEventLog] = useState(false);

  // -----------------------------------------------------------------------
  // Listen to shared ProtocolClient events (from parent's WebSocket)
  // -----------------------------------------------------------------------

  useEffect(() => {
    if (!isActive) return;

    const handleEvent = (envelope: WSEnvelopeClient) => {
      // Update event log
      setEventLog((prev) => {
        const next = [...prev, envelope];
        return next.slice(-200); // Keep last 200 events
      });

      const { event_type, payload, session_id } = envelope;

      // Update session title from created/updated events
      if (event_type === "session.created" || event_type === "session.updated") {
        const title = payload.title as string | undefined;
        if (title) setSessionTitle(title);
      }

      // Handle assistant delta (streaming text)
      if (event_type === "assistant.delta") {
        const delta = payload.text as string | undefined;
        if (delta) {
          setMessages((prev) => {
            const last = prev[prev.length - 1];
            if (last && last.role === "assistant" && !last.error) {
              // Append to last assistant message
              const updated = [...prev];
              updated[updated.length - 1] = {
                ...last,
                parts: [
                  ...last.parts,
                  { type: "text", text: delta },
                ],
                pending: true,
              };
              return updated;
            }
            // Create new assistant message
            return [
              ...prev,
              {
                id: `assistant-${Date.now()}-${Math.random().toString(36).slice(2, 9)}`,
                role: "assistant",
                parts: [{ type: "text", text: delta }],
                pending: true,
              },
            ];
          });
        }
      }

      // Handle assistant completed
      if (event_type === "assistant.completed") {
        setMessages((prev) => {
          const last = prev[prev.length - 1];
          if (last && last.role === "assistant") {
            const updated = [...prev];
            updated[updated.length - 1] = {
              ...last,
              pending: false,
              completedAt: Date.now() / 1000,
            };
            return updated;
          }
          return prev;
        });
        setBusy(false);
      }

      // Handle tool started
      if (event_type === "tool.started") {
        const toolName = payload.tool_name as string | undefined;
        if (toolName) {
          setMessages((prev) => [
            ...prev,
            {
              id: `tool-${Date.now()}-${Math.random().toString(36).slice(2, 9)}`,
              role: "assistant",
              parts: [{ type: "text", text: `Running ${toolName}...` }],
              pending: true,
            },
          ]);
        }
      }

      // Handle tool completed
      if (event_type === "tool.completed") {
        const toolName = payload.tool_name as string | undefined;
        if (toolName) {
          setMessages((prev) => {
            const last = prev[prev.length - 1];
            if (last && last.role === "assistant" && last.parts.some((p) => p.text?.includes(toolName))) {
              const updated = [...prev];
              updated[updated.length - 1] = {
                ...last,
                pending: false,
              };
              return updated;
            }
            return [
              ...prev,
              {
                id: `tool-done-${Date.now()}-${Math.random().toString(36).slice(2, 9)}`,
                role: "assistant",
                parts: [{ type: "text", text: `${toolName} done` }],
                pending: false,
              },
            ];
          });
        }
      }

      // Handle system messages
      if (event_type === "system.message") {
        const message = payload.message as string | undefined;
        if (message) {
          setMessages((prev) => [
            ...prev,
            {
              id: `system-${Date.now()}-${Math.random().toString(36).slice(2, 9)}`,
              role: "system",
              parts: [{ type: "text", text: message }],
            },
          ]);
        }
      }

      // Handle session ready
      if (event_type === "session.ready") {
        setMessages((prev) => [
          ...prev,
          {
            id: `ready-${Date.now()}`,
            role: "system",
            parts: [{ type: "text", text: "Session ready" }],
          },
        ]);
      }

      // Handle session interrupted
      if (event_type === "session.interrupted") {
        setMessages((prev) => {
          const last = prev[prev.length - 1];
          if (last && last.role === "assistant") {
            const updated = [...prev];
            updated[updated.length - 1] = {
              ...last,
              pending: false,
            };
            return updated;
          }
          return prev;
        });
        setBusy(false);
      }

      // Handle session failed
      if (event_type === "session.failed") {
        const reason = payload.reason as string | undefined;
        setMessages((prev) => {
          const last = prev[prev.length - 1];
          if (last && last.role === "assistant") {
            const updated = [...prev];
            updated[updated.length - 1] = {
              ...last,
              pending: false,
              error: reason || "Unknown error",
            };
            return updated;
          }
          return prev;
        });
        setBusy(false);
      }

      // Handle model switched
      if (event_type === "model_switched") {
        const model = payload.model as string | undefined;
        setMessages((prev) => [
          ...prev,
          {
            id: `model-${Date.now()}`,
            role: "system",
            parts: [{ type: "text", text: `Model switched to: ${model || "unknown"}` }],
          },
        ]);
      }

      // Handle self_improvement.tick
      if (event_type === "self_improvement.tick") {
        const tickInfo = payload.info as string | undefined;
        setMessages((prev) => [
          ...prev,
          {
            id: `improve-${Date.now()}`,
            role: "system",
            parts: [{ type: "text", text: `[improvement] ${tickInfo || "tick"}` }],
          },
        ]);
      }

      // Handle resource.warning
      if (event_type === "resource.warning") {
        const warning = payload.message as string | undefined;
        setMessages((prev) => [
          ...prev,
          {
            id: `warn-${Date.now()}`,
            role: "system",
            parts: [{ type: "text", text: `[warning] ${warning || "resource warning"}` }],
          },
        ]);
      }

      // Handle tool.permission.required
      if (event_type === "tool.permission.required") {
        const toolName = payload.tool_name as string | undefined;
        setMessages((prev) => [
          ...prev,
          {
            id: `perm-${Date.now()}`,
            role: "system",
            parts: [{ type: "text", text: `[perm] ${toolName || "tool"} requires permission` }],
          },
        ]);
      }
    };

    // Subscribe to all events from the shared ProtocolClient
    protocolClient.on("*", handleEvent);

    return () => {
      protocolClient.off("*", handleEvent);
    };
  }, [isActive, protocolClient]);

  // -----------------------------------------------------------------------
  // Send prompt via shared ProtocolClient
  // -----------------------------------------------------------------------

  const sendPrompt = useCallback(
    (text: string) => {
      if (!text.trim()) return;

      // Add user message
      const userMsg: ChatMessage = {
        id: `user-${Date.now()}-${Math.random().toString(36).slice(2, 9)}`,
        role: "user",
        parts: [{ type: "text", text }],
        timestamp: Date.now() / 1000,
      };
      setMessages((prev) => [...prev, userMsg]);
      setBusy(true);

      // Send via shared ProtocolClient
      protocolClient.sendPrompt(text);
    },
    [protocolClient]
  );

  // -----------------------------------------------------------------------
  // Interrupt via shared ProtocolClient
  // -----------------------------------------------------------------------

  const interrupt = useCallback(() => {
    protocolClient.sendInterrupt();
  }, [protocolClient]);

  // -----------------------------------------------------------------------
  // Render
  // -----------------------------------------------------------------------

  const connectionColor = useMemo(() => {
    switch (connectionState) {
      case "connected":
        return "bg-status-success";
      case "connecting":
      case "reconnecting":
        return "bg-status-warning animate-pulse";
      default:
        return "bg-status-error";
    }
  }, [connectionState]);

  const connectionLabel = useMemo(() => {
    switch (connectionState) {
      case "connected":
        return "Connected";
      case "connecting":
        return "Connecting...";
      case "reconnecting":
        return "Reconnecting...";
      default:
        return "Disconnected";
    }
  }, [connectionState]);

  return (
    <div className="flex h-full w-full flex-col bg-[#0a0a0f]">
      {/* Thread area */}
      <div className="flex-1 min-h-0 relative">
        <Thread
          messages={messages}
          loading={busy ? "response" : undefined}
          onCancel={interrupt}
        />

        {/* Connection status overlay */}
        <div className="absolute top-2 right-2 flex items-center gap-1.5 z-10">
          <div className={`w-2 h-2 rounded-full ${connectionColor}`} />
          <span className="text-[0.625rem] text-text-muted uppercase tracking-wider">
            {connectionLabel}
          </span>
        </div>

        {/* Session title overlay */}
        <div className="absolute top-2 left-2 z-10">
          <span className="text-xs text-text-muted font-medium">
            {sessionTitle}
          </span>
        </div>
      </div>

      {/* ChatBar (composer) */}
      <ChatBar
        busy={busy}
        disabled={connectionState !== "connected"}
        onCancel={interrupt}
        onSubmit={sendPrompt}
      />

      {/* Event log panel */}
      {showEventLog && (
        <div className="flex-shrink-0 border-t border-border/50 bg-surface h-48 overflow-y-auto">
          <div className="px-3 py-2">
            <div className="flex items-center justify-between mb-2">
              <span className="text-xs font-medium text-text-muted uppercase tracking-wider">
                Event Log ({eventLog.length})
              </span>
              <button
                onClick={() => setEventLog([])}
                className="text-xs text-text-muted hover:text-text-primary transition-colors"
              >
                Clear
              </button>
            </div>
            <div className="space-y-0.5">
              {eventLog.map((evt, i) => {
                const eventType = evt.event_type;
                let label = eventType;
                let color = "text-text-muted";
                switch (eventType) {
                  case "session.created":
                    label = "SESSION";
                    color = "text-bright-cyan";
                    break;
                  case "session.ready":
                    label = "READY";
                    color = "text-green";
                    break;
                  case "assistant.delta":
                    label = "assistant";
                    color = "text-bright-magenta";
                    break;
                  case "assistant.completed":
                    label = "DONE";
                    color = "text-green";
                    break;
                  case "tool.started":
                    label = "tool";
                    color = "text-yellow";
                    break;
                  case "tool.completed":
                    label = "tool";
                    color = "text-bright-green";
                    break;
                  case "system.message":
                    label = "system";
                    color = "text-gray";
                    break;
                  case "session.interrupted":
                    label = "INTERRUPT";
                    color = "text-red";
                    break;
                  case "session.failed":
                    label = "FAILED";
                    color = "text-red";
                    break;
                  case "model_switched":
                    label = "MODEL";
                    color = "text-bright-cyan";
                    break;
                  default:
                    label = eventType;
                    color = "text-text-muted";
                }
                return (
                  <div
                    key={`${evt.seq}-${i}`}
                    className="flex items-start gap-2 text-xs font-mono"
                  >
                    <span className="text-text-muted shrink-0 tabular-nums w-16">
                      {evt.seq ?? "—"}
                    </span>
                    <span className={`shrink-0 ${color}`}>{label}</span>
                    <span className="text-text-muted truncate">
                      {evt.session_id.slice(0, 8)}
                    </span>
                    <span className="text-text-muted ml-auto tabular-nums">
                      {evt.timestamp
                        ? new Date(evt.timestamp).toLocaleTimeString()
                        : "—"}
                    </span>
                  </div>
                );
              })}
              {eventLog.length === 0 && (
                <div className="text-xs text-text-muted py-2 text-center">
                  No events yet
                </div>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
