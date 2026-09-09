"use client";

import type { ReactNode } from "react";
import { cn } from "@/lib/cn";
import { useProtocol } from "@/lib/hooks/useProtocol";
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
 */
export function AppShell({ children }: { children: ReactNode }) {
  useProtocol();

  return (
    <div
      className={cn(
        "grid h-dvh w-dvw",
        "grid-cols-[var(--left-rail-width)_1fr_var(--right-rail-width)]",
        "bg-surface-1 text-text-base",
      )}
    >
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
