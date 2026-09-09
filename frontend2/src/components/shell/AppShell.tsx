"use client";

import { cn } from "@/lib/cn";

/**
 * Phase-0 AppShell: three-region layout scaffold.
 *
 *   +----------------+---------------------------+------------------+
 *   | LeftRail       | ChatRegion                | RightRailHost    |
 *   | (nav + session)| (transcript + composer)   | (contextual pane)|
 *   +----------------+---------------------------+------------------+
 *
 * Populated across Phases 1-8.
 */
export function AppShell() {
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
        <div className="flex h-full flex-col p-3">
          <div className="text-11 tracking-wide text-text-muted uppercase">
            Tektos
          </div>
        </div>
      </aside>

      <main
        aria-label="Chat"
        className="min-h-0 grid grid-rows-[1fr_auto] bg-surface-1"
      >
        <section className="min-h-0 overflow-auto scrollbar-thin p-6">
          <div className="mx-auto max-w-[720px] text-text-muted text-13">
            Frontend2 scaffold online. Transcript renders in Phase 2.
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
