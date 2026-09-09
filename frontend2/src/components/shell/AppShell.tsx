"use client";

import { useStore } from "@nanostores/react";
import { cn } from "@/lib/cn";
import { $connectionError, $connectionState } from "@/lib/stores/connection";
import { $sessionId, $sessionModel } from "@/lib/stores/session";
import { useProtocol } from "@/lib/hooks/useProtocol";

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

      <main
        aria-label="Chat"
        className="min-h-0 grid grid-rows-[1fr_auto] bg-surface-1"
      >
        <section className="min-h-0 overflow-auto scrollbar-thin p-6">
          <div className="mx-auto max-w-[720px] text-text-muted text-13 space-y-3">
            <div>Frontend2 online. Transcript renders in Phase 2.</div>
            {sessionId && (
              <div className="tabular text-11 text-text-faint">
                session {sessionId.slice(0, 8)}
                {model && <> · model {model}</>}
              </div>
            )}
          </div>
        </section>
        <section className="hairline bg-surface-2 p-3">
          <div className="mx-auto max-w-[720px] text-11 text-text-faint">
            Composer + status stack land in Phases 2-4.
          </div>
        </section>
      </main>

      <aside
        aria-label="Contextual pane"
        className="hairline min-h-0 bg-surface-2"
      >
        <div className="p-3 text-11 text-text-faint">
          Right-rail panes land in Phase 5.
        </div>
      </aside>
    </div>
  );
}
