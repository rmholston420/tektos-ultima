"use client";

import { useState } from "react";
import { useStore } from "@nanostores/react";
import { RotateCcw, Check, X } from "lucide-react";
import {
  $keybindCatalog,
  $keybindOverrides,
  resetBinding,
  setBinding,
} from "@/lib/keybinds/registry";
import { chordFromEvent, formatChord } from "@/lib/keybinds/chord";

export default function SettingsPage() {
  const catalog = useStore($keybindCatalog);
  const overrides = useStore($keybindOverrides);
  const [editing, setEditing] = useState<string | null>(null);
  const [pending, setPending] = useState<string | null>(null);

  const capture = (e: React.KeyboardEvent, id: string) => {
    e.preventDefault();
    if (e.key === "Escape") {
      setEditing(null);
      setPending(null);
      return;
    }
    if (["Meta", "Control", "Alt", "Shift"].includes(e.key)) return;
    const chord = chordFromEvent(e.nativeEvent);
    setPending(chord);
  };

  const save = (id: string) => {
    if (!pending) return;
    setBinding(id, pending);
    setEditing(null);
    setPending(null);
  };

  return (
    <div className="flex h-full min-h-0 flex-col overflow-auto scrollbar-thin bg-surface-1">
      <div className="hairline px-4 py-3">
        <h1 className="text-14 font-medium text-text-base">Settings</h1>
        <div className="mt-1 text-11 text-text-muted">
          Keybinds are saved locally per browser. Press a chord to rebind, Esc
          to cancel.
        </div>
      </div>
      <div className="p-4">
        <h2 className="text-12 font-medium text-text-base">Keybinds</h2>
        <ul className="mt-2 divide-y divide-[var(--stroke)]">
          {catalog.map((a) => {
            const active = editing === a.id;
            const current = overrides[a.id] ?? a.defaultBinding;
            const overridden = !!overrides[a.id];
            return (
              <li key={a.id} className="flex items-center gap-3 py-2 text-12">
                <div className="min-w-0 flex-1">
                  <div className="text-text-base">{a.label}</div>
                  <div className="text-11 text-text-faint">
                    {a.section} · {a.id}
                  </div>
                </div>
                {active ? (
                  <div className="flex items-center gap-2">
                    <input
                      autoFocus
                      readOnly
                      value={pending ? formatChord(pending) : "press chord\u2026"}
                      onKeyDown={(e) => capture(e, a.id)}
                      className="w-40 rounded border border-[var(--stroke)] bg-surface-3 px-2 py-1 text-11 font-mono text-text-base focus:outline-none"
                    />
                    <button
                      className="rounded p-1 text-success hover:bg-surface-4"
                      onClick={() => save(a.id)}
                      title="Save"
                    >
                      <Check className="h-3.5 w-3.5" />
                    </button>
                    <button
                      className="rounded p-1 text-text-muted hover:bg-surface-4"
                      onClick={() => {
                        setEditing(null);
                        setPending(null);
                      }}
                      title="Cancel"
                    >
                      <X className="h-3.5 w-3.5" />
                    </button>
                  </div>
                ) : (
                  <div className="flex items-center gap-2">
                    <button
                      className="rounded bg-surface-3 px-2 py-1 font-mono text-11 text-text-base hover:bg-surface-4"
                      onClick={() => {
                        setEditing(a.id);
                        setPending(null);
                      }}
                      title="Rebind"
                    >
                      {formatChord(current)}
                    </button>
                    {overridden && (
                      <button
                        className="rounded p-1 text-text-muted hover:bg-surface-4"
                        onClick={() => resetBinding(a.id)}
                        title="Reset to default"
                      >
                        <RotateCcw className="h-3.5 w-3.5" />
                      </button>
                    )}
                  </div>
                )}
              </li>
            );
          })}
        </ul>
      </div>
    </div>
  );
}
