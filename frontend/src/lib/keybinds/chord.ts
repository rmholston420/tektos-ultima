"use client";

/**
 * Normalize a keyboard chord to a canonical string.
 *
 *   modifier order: mod (\u2318/ctrl), alt, shift
 *   key: lowercased for letters, unchanged otherwise
 *
 * Examples: "mod+k", "mod+shift+p", "esc", "?"
 */
export function chordFromEvent(e: KeyboardEvent): string {
  const isMac = typeof navigator !== "undefined" && /Mac|iPhone|iPad/.test(navigator.platform);
  const parts: string[] = [];
  const mod = isMac ? e.metaKey : e.ctrlKey;
  if (mod) parts.push("mod");
  if (e.altKey) parts.push("alt");
  if (e.shiftKey) parts.push("shift");
  const key = normalizeKey(e.key);
  if (!["control", "meta", "alt", "shift"].includes(key)) parts.push(key);
  return parts.join("+");
}

function normalizeKey(k: string): string {
  const map: Record<string, string> = {
    Escape: "esc",
    " ": "space",
    ArrowLeft: "left",
    ArrowRight: "right",
    ArrowUp: "up",
    ArrowDown: "down",
    Enter: "enter",
    Backspace: "backspace",
    Delete: "delete",
    Tab: "tab",
  };
  if (map[k]) return map[k];
  return k.length === 1 ? k.toLowerCase() : k.toLowerCase();
}

export function formatChord(chord: string): string {
  const isMac = typeof navigator !== "undefined" && /Mac|iPhone|iPad/.test(navigator.platform);
  return chord
    .split("+")
    .map((p) => {
      if (p === "mod") return isMac ? "\u2318" : "Ctrl";
      if (p === "alt") return isMac ? "\u2325" : "Alt";
      if (p === "shift") return isMac ? "\u21e7" : "Shift";
      if (p === "esc") return "Esc";
      if (p === "enter") return "\u21b5";
      if (p.length === 1) return p.toUpperCase();
      return p.charAt(0).toUpperCase() + p.slice(1);
    })
    .join(isMac ? " " : "+");
}
