"use client";

import { useStore } from "@nanostores/react";
import { cn } from "@/lib/cn";
import { $connectionError, $connectionState } from "@/lib/stores/connection";
import { $sessionId, $sessionModel } from "@/lib/stores/session";
import { useProtocol } from "@/lib/hooks/useProtocol";
import { ChatRegion } from "@/components/chat/ChatRegion";
import { RightRail } from "@/components/panes/RightRail";
import { registerBuiltinVisualizers } from "@/components/assistant-ui/tool-visualizers";

registerBuiltinVisualizers();

/**
 * AppShell: three-region layout scaffold.
 *
 *   +----------------+---------------------------+------------------+
 *   | LeftRail       | ChatRegion                | RightRailHost    |
 *   | (nav + session)| (transcript + composer)   | (contextual pane)|
 *   +----------------+---------------------------+------------------+
 *
 * Populated across Phases 2-8. Wires the protocol client at Phase 1.
 */
export function AppShell() {
  useProtocol();
  const state = useStore($connectionState);
  const error = useStore($connectionError);
  const sessionId = useStore($sessionId);
  const model = useStore($sessionModel);
  void sessionId; void model;

  const dotClass =
    state === "connected"
      ? "bg-success"
      : state === "connecting" || state === "reconnecting"
        ? "bg-agent animate-tektos-pulse"
        : "bg-error";
  return (
    <div
      className={cn(
        "grid h-dvh w-dvw",
        "grid-cols-[var(--left-rail-width)_1fr_var(--right-rail-width)]",
        "bg-surface-1 text-text-base",
      )}
    >
      <aside
        aria-label="Navigation"
        className="hairline min-h-0 bg-surface-2"
      >
        <div className="flex h-full flex-col p-3 gap-4">
          <div className="text-11 tracking-wide text-text-muted uppercase">
            Tektos
          </div>
          <div className="flex items-center gap-2 text-11" data-testid="connection-indicator">
            <span className={cn("h-2 w-2 rounded-full", dotClass)} />
            <span className="text-text-muted">{state}</span>
          </div>
          {error && (
            <div className="text-11 text-error" role="status">
              {error}
            </div>
          )}
        </div>
      </aside>

      <main aria-label="Chat" className="min-h-0">
        <ChatRegion />
      </main>

      <aside aria-label="Contextual pane" className="hairline min-h-0">
        <RightRail />
      </aside>
    </div>
  );
}
