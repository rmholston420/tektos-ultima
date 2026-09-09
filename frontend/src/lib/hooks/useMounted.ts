"use client";

import { useEffect, useState } from "react";

/**
 * Returns `false` during SSR and the first client render, `true` after
 * mount. Use to gate rendering of values that change between the server
 * snapshot and the first client tick (WebSocket state, live timers,
 * `localStorage`-backed prefs, etc.) — return a stable placeholder while
 * `false`, then render the live value once `true`.
 *
 * Cheap: a single `useState` + `useEffect` per component; the effect
 * runs once on mount.
 */
export function useMounted(): boolean {
  const [mounted, setMounted] = useState(false);
  useEffect(() => setMounted(true), []);
  return mounted;
}
