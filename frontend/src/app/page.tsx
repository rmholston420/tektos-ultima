/**
 * Tektos-Ultima v1 — Main Layout Shell
 *
 * Full app layout: Sidebar + Transcript + Composer with header bar.
 * Manages global state: session, theme, streaming, WebSocket connection.
 *
 * Exemplar pattern: Single page app with WebSocket-driven real-time updates.
 */

"use client";

import React, { useState, useEffect, useCallback, useRef } from "react";
import { ProtocolClient, EventType, type WSEnvelopeClient } from "@/lib/protocol";
import { SessionStore, type SessionSnapshot, type SessionEvent } from "@/lib/session-store";
import { Sidebar } from "@/components/sidebar/Sidebar";
import { Transcript, type TranscriptEvent } from "@/components/transcript/Transcript";
import { Composer } from "@/components/composer/Composer";

// ---------------------------------------------------------------------------
// Main App component
// ---------------------------------------------------------------------------

export default function App() {
  // State
  const [protocolClient] = useState(() => new ProtocolClient());
  const [sessionStore] = useState(() => new SessionStore(protocolClient));
  const [activeSession, setActiveSession] = useState<SessionSnapshot | null>(null);
  const [transcriptEvents, setTranscriptEvents] = useState<TranscriptEvent[]>([]);
  const [streamingContent, setStreamingContent] = useState("");
  const [isStreaming, setIsStreaming] = useState(false);
  const [theme, setTheme] = useState<"dark" | "tibet">("dark");
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
  const [connectionState, setConnectionState] = useState<
    "disconnected" | "connecting" | "connected" | "reconnecting"
  >("disconnected");

  // Refs for cleanup
  const streamBuffer = useRef("");

  // -------------------------------------------------------------------
  // Connection management
  // -------------------------------------------------------------------

  useEffect(() => {
    // Connect to backend WebSocket
    protocolClient.onStateChange((state) => {
      setConnectionState(state.state);
    });

    protocolClient.connect();

    // Cleanup on unmount
    return () => {
      protocolClient.disconnect();
    };
  }, [protocolClient]);

  // -------------------------------------------------------------------
  // Event handling from backend
  // -------------------------------------------------------------------

  useEffect(() => {
    protocolClient.on("*", (envelope: WSEnvelopeClient) => {
      const event: TranscriptEvent = {
        type: mapEventType(envelope.event_type),
        session_id: envelope.session_id,
        seq: envelope.seq ?? 0,
        payload: envelope.payload,
        timestamp: envelope.timestamp ?? new Date().toISOString(),
      };

      switch (envelope.event_type) {
        case EventType.ASSISTANT_DELTA:
          // Streaming content
          const text = envelope.payload.text as string;
          if (text) {
            streamBuffer.current += text;
            setStreamingContent(streamBuffer.current);
            setIsStreaming(true);
          }
          break;

        case EventType.ASSISTANT_COMPLETED:
          // Finalize streaming message
          if (streamBuffer.current) {
            setTranscriptEvents((prev) => [...prev, event]);
            streamBuffer.current = "";
            setStreamingContent("");
          }
          setIsStreaming(false);
          break;

        default:
          // Non-streaming events go directly into transcript
          setTranscriptEvents((prev) => [...prev, event]);
      }
    });
  }, [protocolClient]);

  // -------------------------------------------------------------------
  // Session management
  // -------------------------------------------------------------------

  useEffect(() => {
    sessionStore.on("created", (event: SessionEvent) => {
      if (event.type === "created") {
        setActiveSession(event.session);
        protocolClient.setSessionId(event.session.id);
      }
    });

    sessionStore.on("updated", (event: SessionEvent) => {
      if (event.type === "updated") {
        setActiveSession((prev) => {
          if (prev?.id === event.session.id) {
            return { ...prev, ...event.session };
          }
          return prev;
        });
      }
    });

    sessionStore.on("deleted", (event: SessionEvent) => {
      if (event.type === "deleted" && activeSession?.id === event.session_id) {
        setActiveSession(null);
        setTranscriptEvents([]);
        protocolClient.setSessionId("");
      }
    });
  }, [sessionStore, protocolClient, activeSession]);

  // -------------------------------------------------------------------
  // Handlers
  // -------------------------------------------------------------------

  const handleSendMessage = useCallback(
    (message: string) => {
      if (!activeSession) return;

      // Add user message to transcript
      const userEvent: TranscriptEvent = {
        type: "message",
        session_id: activeSession.id,
        seq: 0,
        payload: { text: message },
        timestamp: new Date().toISOString(),
      };
      setTranscriptEvents((prev) => [...prev, userEvent]);

      // Send to backend
      protocolClient.sendPrompt(message, {
        model: activeSession.model,
        cwd: activeSession.cwd,
      });
    },
    [activeSession, protocolClient]
  );

  const handleInterrupt = useCallback(() => {
    protocolClient.sendInterrupt();
    if (streamBuffer.current) {
      setTranscriptEvents((prev) => [...prev, {
        type: "message",
        session_id: activeSession?.id ?? "",
        seq: 0,
        payload: { text: streamBuffer.current },
        timestamp: new Date().toISOString(),
      }]);
      streamBuffer.current = "";
      setStreamingContent("");
    }
    setIsStreaming(false);
  }, [protocolClient, activeSession]);

  const handleSelectSession = useCallback(
    (sessionId: string) => {
      sessionStore.getSession(sessionId).then((session) => {
        if (session) {
          setActiveSession(session);
          protocolClient.setSessionId(sessionId);

          // Load transcript for this session
          fetch(`/api/sessions/${sessionId}/events`)
            .then((res) => res.json())
            .then((data) => {
              const events: TranscriptEvent[] = (data.events || []).map(
                (e: any) => ({
                  type: mapEventType(e.type),
                  session_id: e.session_id,
                  seq: e.seq ?? 0,
                  payload: e.payload ?? {},
                  timestamp: e.timestamp ?? new Date().toISOString(),
                })
              );
              setTranscriptEvents(events);
              setStreamingContent("");
              setIsStreaming(false);
            })
            .catch(() => {
              setTranscriptEvents([]);
            });
        }
      });
    },
    [sessionStore, protocolClient]
  );

  const handleCreateSession = useCallback(() => {
    sessionStore.createSession().then((session) => {
      setActiveSession(session);
      protocolClient.setSessionId(session.id);
    });
  }, [sessionStore, protocolClient]);

  const handleAttachFile = useCallback(
    (files: File[]) => {
      // TODO: Implement file upload to backend
      console.log("File attachment:", files);
    },
    []
  );

  // -------------------------------------------------------------------
  // Theme toggle
  // -------------------------------------------------------------------

  const handleToggleTheme = useCallback(() => {
    setTheme((prev) => {
      const next = prev === "dark" ? "tibet" : "dark";
      document.documentElement.setAttribute("data-theme", next);
      return next;
    });
  }, []);

  // -------------------------------------------------------------------
  // Render
  // -------------------------------------------------------------------

  return (
    <div className="shell">
      {/* Sidebar */}
      <Sidebar
        sessionStore={sessionStore}
        activeSessionId={activeSession?.id ?? null}
        onSelectSession={handleSelectSession}
        onCreateSession={handleCreateSession}
        theme={theme}
        onToggleTheme={handleToggleTheme}
        collapsed={sidebarCollapsed}
        onToggleCollapsed={() => setSidebarCollapsed(!sidebarCollapsed)}
      />

      {/* Main content */}
      <div className="shell-main">
        {/* Header */}
        <header className="shell-header">
          <div className="flex items-center gap-3">
            <h1 className="text-sm font-semibold text-text-primary">
              {activeSession?.title ?? "Tektos-Ultima"}
            </h1>
            {activeSession && (
              <span className="text-xs text-text-muted">
                {activeSession.model}
              </span>
            )}
          </div>

          <div className="flex items-center gap-3">
            {/* Connection status */}
            <div className="flex items-center gap-1.5">
              <div
                className={`w-2 h-2 rounded-full ${
                  connectionState === "connected"
                    ? "bg-status-success"
                    : connectionState === "connecting" || connectionState === "reconnecting"
                    ? "bg-status-warning animate-pulse"
                    : "bg-status-error"
                }`}
              />
              <span className="text-xs text-text-muted capitalize">
                {connectionState === "reconnecting" ? "reconnecting" : connectionState}
              </span>
            </div>
          </div>
        </header>

        {/* Transcript */}
        <Transcript
          activeSession={activeSession}
          events={transcriptEvents}
          streamingContent={streamingContent}
          isStreaming={isStreaming}
          onSendMessage={handleSendMessage}
          onInterrupt={handleInterrupt}
        />

        {/* Composer */}
        <Composer
          isActive={!!activeSession}
          isStreaming={isStreaming}
          sessionId={activeSession?.id}
          model={activeSession?.model}
          onSendMessage={handleSendMessage}
          onInterrupt={handleInterrupt}
          onAttach={handleAttachFile}
        />
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function mapEventType(backendType: string): "message" | "tool" | "system" {
  if (
    backendType.startsWith("session.") ||
    backendType.startsWith("system.")
  ) {
    return "system";
  }
  if (backendType.startsWith("tool.")) {
    return "tool";
  }
  if (backendType.startsWith("assistant.")) {
    return "message";
  }
  return "message";
}
