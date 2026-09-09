"use client";

import { atom } from "nanostores";

export interface PersistedSession {
  id: string;
  title: string;
  pinned: boolean;
  created_at: string;
  updated_at: string;
  message_count: number;
}

const STORAGE_KEY = "tektos.sessions.v1";

function readStorage(): PersistedSession[] {
  if (typeof window === "undefined") return [];
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    if (!raw) return [];
    const parsed = JSON.parse(raw) as unknown;
    if (!Array.isArray(parsed)) return [];
    return parsed as PersistedSession[];
  } catch {
    return [];
  }
}

function writeStorage(list: PersistedSession[]): void {
  if (typeof window === "undefined") return;
  try {
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify(list));
  } catch {
    /* quota / private mode — silently accept in-memory only */
  }
}

export const $persistedSessions = atom<PersistedSession[]>([]);

export function hydratePersistedSessions(): void {
  $persistedSessions.set(readStorage());
}

export function upsertPersistedSession(entry: PersistedSession): void {
  const cur = $persistedSessions.get();
  const idx = cur.findIndex((s) => s.id === entry.id);
  const next = idx >= 0 ? cur.map((s) => (s.id === entry.id ? entry : s)) : [entry, ...cur];
  $persistedSessions.set(next);
  writeStorage(next);
}

export function removePersistedSession(id: string): void {
  const next = $persistedSessions.get().filter((s) => s.id !== id);
  $persistedSessions.set(next);
  writeStorage(next);
}

export function togglePinnedPersisted(id: string): void {
  const cur = $persistedSessions.get();
  const next = cur.map((s) => (s.id === id ? { ...s, pinned: !s.pinned } : s));
  $persistedSessions.set(next);
  writeStorage(next);
}
