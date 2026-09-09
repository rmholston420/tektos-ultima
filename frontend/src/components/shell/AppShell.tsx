"use client";

import type { ReactNode } from "react";
import { cn } from "@/lib/cn";
import { useProtocol } from "@/lib/hooks/useProtocol";
import { useMounted } from "@/lib/hooks/useMounted";
import { LeftRail } from "@/components/shell/LeftRail";
import { RightRail } from "@/components/panes/RightRail";
import { PaletteMount } from "@/components/palette/PaletteMount";
import { registerBuiltinVisualizers } from "@/components/assistant-ui/tool-visualizers";

registerBuiltinVisualizers();

/**
 * AppShell: three-region layout scaffold used by every route.
 *
 *   +----------------+---------------------------+------------------+
 *   | LeftRail       | {children}                | RightRail        |
 *   | (nav + status) | (route content)           | (contextual pane)|
 *   +----------------+---------------------------+------------------+
 *
 * Client-only render. The AppShell reads from live stores (connection
 * state, session, panes, palette) that transition immediately after
 * mount. Serving an SSR snapshot of that state guarantees a hydration
 * mismatch, so we render an inert grid-shaped placeholder on the server
 * + first client render and swap in the full shell after mount. This
 * eliminates ~15 individual `useMounted` gates and matches how OpenHands
 * and Hermes handle the same class of components.
 */
export function AppShell({ children }: { children: ReactNode }) {
  const mounted = useMounted();
  useProtocol();

  const gridClass = cn(
    "grid h-dvh w-dvw",
    "grid-cols-[var(--left-rail-width)_1fr_var(--right-rail-width)]",
    "bg-surface-1 text-text-base",
  );

  if (!mounted) {
    // Structurally identical placeholder — same grid, same regions, no
    // store reads. Hydration matches this exactly.
    return (
      <div className={gridClass} suppressHydrationWarning>
        <aside aria-label="Navigation" className="hairline bg-surface-2" />
        <main aria-label="Main" className="min-h-0" />
        <aside aria-label="Contextual pane" className="hairline min-h-0" />
      </div>
    );
  }

  return (
    <div className={gridClass}>
      <LeftRail />

      <main aria-label="Main" className="min-h-0">
        {children}
      </main>

      <aside aria-label="Contextual pane" className="hairline min-h-0">
        <RightRail />
      </aside>

      <PaletteMount />
    </div>
  );
}
