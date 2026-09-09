"use client";

import { registerAction } from "@/lib/keybinds/registry";
import { openPalette, closePalette, $paletteOpen } from "./CommandPalette";
import { $activePane } from "@/lib/stores/panes";
import type { PaneId } from "@/components/panes/registry";

let registered = false;

/**
 * Register the default action catalog for the palette + keybinds. Safe
 * to call multiple times; idempotent per module load.
 */
export function registerDefaultActions(navigate: (href: string) => void): void {
  if (registered) return;
  registered = true;

  registerAction({
    id: "palette.toggle",
    label: "Open command palette",
    defaultBinding: "mod+k",
    section: "Palette",
    run: () => {
      $paletteOpen.set(!$paletteOpen.get());
    },
  });
  registerAction({
    id: "palette.close",
    label: "Close command palette",
    defaultBinding: "esc",
    section: "Palette",
    run: () => closePalette(),
  });

  // Navigation
  for (const [href, label, chord] of [
    ["/", "Go to Chat", "mod+1"],
    ["/artifacts", "Go to Artifacts", "mod+2"],
    ["/runs", "Go to Runs", "mod+3"],
    ["/dashboard", "Go to Dashboard", "mod+4"],
    ["/settings", "Go to Settings", "mod+,"],
  ] as const) {
    registerAction({
      id: `nav.${href}`,
      label,
      defaultBinding: chord,
      section: "Navigation",
      run: () => {
        navigate(href);
        closePalette();
      },
    });
  }

  // Panes
  for (const [id, label, chord] of [
    ["files", "Show Files pane", "mod+shift+f"],
    ["editor", "Show Editor pane", "mod+shift+e"],
    ["diff", "Show Diff pane", "mod+shift+d"],
    ["terminal", "Show Terminal pane", "mod+shift+t"],
    ["preview", "Show Preview pane", "mod+shift+p"],
    ["graph", "Show Graph pane", "mod+shift+g"],
    ["logs", "Show Logs pane", "mod+shift+l"],
  ] as const) {
    registerAction({
      id: `pane.${id}`,
      label,
      defaultBinding: chord,
      section: "Panes",
      run: () => {
        $activePane.set(id as PaneId);
        openPalette; // reference to keep import active for future palette-close side-effects
        closePalette();
      },
    });
  }
}
