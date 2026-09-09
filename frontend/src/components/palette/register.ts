"use client";

import { registerAction } from "@/lib/keybinds/registry";
import { openPalette, closePalette, $paletteOpen } from "./CommandPalette";
import { $activePane } from "@/lib/stores/panes";
import type { PaneId } from "@/components/panes/registry";
import { api } from "@/lib/api";
import { $sessionId } from "@/lib/stores/session";
import { $permissionQueue } from "@/lib/stores/session";
import { $planProposals } from "@/lib/stores/session";

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

  // Session actions (write) — these mutate backend state, so keep them
  // discoverable in the palette but off the default keybind grid.
  registerAction({
    id: "session.new",
    label: "New session",
    defaultBinding: "mod+shift+n",
    section: "Session",
    run: async () => {
      try {
        const s = await api.createSession();
        $sessionId.set(s.id);
        navigate("/");
      } catch (err) {
        console.error("session.new failed", err);
      } finally {
        closePalette();
      }
    },
  });

  registerAction({
    id: "session.fork",
    label: "Fork current session",
    defaultBinding: "",
    section: "Session",
    run: async () => {
      const id = $sessionId.get();
      if (!id) return;
      try {
        const s = await api.forkSession(id);
        $sessionId.set(s.id);
      } catch (err) {
        console.error("session.fork failed", err);
      } finally {
        closePalette();
      }
    },
  });

  registerAction({
    id: "session.interrupt",
    label: "Interrupt current session",
    defaultBinding: "mod+.",
    section: "Session",
    run: async () => {
      const id = $sessionId.get();
      if (!id) return;
      try {
        await api.interruptSession(id);
      } catch (err) {
        console.error("session.interrupt failed", err);
      } finally {
        closePalette();
      }
    },
  });

  registerAction({
    id: "session.change_model",
    label: "Change model for current session…",
    defaultBinding: "",
    section: "Session",
    run: async () => {
      const id = $sessionId.get();
      if (!id) return;
      const model = window.prompt("Model name (e.g. Qwen3.6-35B-A3B-Q4_K_M):");
      if (!model) return;
      try {
        await api.changeSessionModel(id, model);
      } catch (err) {
        console.error("session.change_model failed", err);
      } finally {
        closePalette();
      }
    },
  });

  registerAction({
    id: "plan.approve_pending",
    label: "Approve next pending plan",
    defaultBinding: "",
    section: "Plans",
    run: () => {
      const proposals = Object.values($planProposals.get());
      const pending = proposals.find((p) => !p.approved);
      if (!pending) return;
      $planProposals.setKey(pending.plan_id, { ...pending, approved: true });
      closePalette();
    },
  });

  registerAction({
    id: "permission.approve_next",
    label: "Approve next permission prompt",
    defaultBinding: "",
    section: "Permissions",
    run: () => {
      const queue = $permissionQueue.get();
      if (queue.length === 0) return;
      // Fire a DOM event the PermissionModal picks up; keeps the
      // approval logic in one place instead of duplicating the WS reply.
      window.dispatchEvent(new CustomEvent("tektos:permission:approve", { detail: queue[0] }));
      closePalette();
    },
  });
}
