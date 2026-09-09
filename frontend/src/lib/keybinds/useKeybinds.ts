"use client";

import { useEffect } from "react";
import { useStore } from "@nanostores/react";
import {
  $keybindCatalog,
  $keybindOverrides,
  resolveBinding,
} from "./registry";
import { chordFromEvent } from "./chord";

/**
 * Attach a document-level listener that fires the correct action for
 * the pressed chord. Ignores key events while the user is typing in
 * an input / textarea / contentEditable, except for chords that
 * include the mod key (⌘/Ctrl).
 */
export function useKeybinds(): void {
  const catalog = useStore($keybindCatalog);
  const overrides = useStore($keybindOverrides);
  void overrides; // subscribe so the effect re-attaches when overrides change

  useEffect(() => {
    function onKeyDown(e: KeyboardEvent) {
      const chord = chordFromEvent(e);
      // Allow mod-chords everywhere; skip plain keys inside editable fields.
      const target = e.target as HTMLElement | null;
      const inEditable =
        !!target &&
        (target.tagName === "INPUT" ||
          target.tagName === "TEXTAREA" ||
          target.isContentEditable);
      const usesMod = chord.startsWith("mod+");
      if (inEditable && !usesMod && chord !== "esc") return;

      for (const action of catalog) {
        if (resolveBinding(action) === chord) {
          e.preventDefault();
          action.run();
          return;
        }
      }
    }
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [catalog, overrides]);
}
