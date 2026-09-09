"use client";

import { atom } from "nanostores";

export interface KeybindAction {
  id: string;
  label: string;
  hint?: string;
  /** Default binding as chord string, e.g. "mod+k" or "esc". */
  defaultBinding: string;
  /** Section label for grouping in the palette / settings. */
  section: string;
  /** Handler invoked when the binding fires. */
  run: () => void;
}

const registry = new Map<string, KeybindAction>();
/** Reactive so the palette can list actions when it opens. */
export const $keybindCatalog = atom<KeybindAction[]>([]);

export function registerAction(action: KeybindAction): void {
  registry.set(action.id, action);
  $keybindCatalog.set(Array.from(registry.values()));
}

export function getAction(id: string): KeybindAction | undefined {
  return registry.get(id);
}

export function listActions(): KeybindAction[] {
  return Array.from(registry.values());
}

// ---- User overrides (persisted in localStorage) -----------------------

const STORAGE_KEY = "tektos.keybinds.v1";

function readOverrides(): Record<string, string> {
  if (typeof window === "undefined") return {};
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    if (!raw) return {};
    const parsed = JSON.parse(raw) as unknown;
    if (parsed && typeof parsed === "object") return parsed as Record<string, string>;
    return {};
  } catch {
    return {};
  }
}

function writeOverrides(map: Record<string, string>): void {
  if (typeof window === "undefined") return;
  try {
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify(map));
  } catch {
    /* ignore */
  }
}

export const $keybindOverrides = atom<Record<string, string>>({});

export function hydrateKeybindOverrides(): void {
  $keybindOverrides.set(readOverrides());
}

export function setBinding(actionId: string, chord: string): void {
  const cur = { ...$keybindOverrides.get(), [actionId]: chord };
  $keybindOverrides.set(cur);
  writeOverrides(cur);
}

export function resetBinding(actionId: string): void {
  const cur = { ...$keybindOverrides.get() };
  delete cur[actionId];
  $keybindOverrides.set(cur);
  writeOverrides(cur);
}

export function resolveBinding(action: KeybindAction): string {
  return $keybindOverrides.get()[action.id] ?? action.defaultBinding;
}
