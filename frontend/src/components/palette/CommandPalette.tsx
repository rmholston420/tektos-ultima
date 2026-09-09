"use client";

import { useEffect } from "react";
import { atom } from "nanostores";
import { useStore } from "@nanostores/react";
import { Command } from "cmdk";
import { $keybindCatalog, resolveBinding } from "@/lib/keybinds/registry";
import { formatChord } from "@/lib/keybinds/chord";

export const $paletteOpen = atom<boolean>(false);

export function openPalette(): void {
  $paletteOpen.set(true);
}
export function closePalette(): void {
  $paletteOpen.set(false);
}

/**
 * cmdk command palette. Lists every registered keybind action. Chord
 * hint on the right; Enter fires action; Esc closes.
 */
export function CommandPalette() {
  const open = useStore($paletteOpen);
  const catalog = useStore($keybindCatalog);

  useEffect(() => {
    // Body-scroll lock while open.
    if (typeof document === "undefined") return;
    if (open) document.body.style.overflow = "hidden";
    else document.body.style.overflow = "";
  }, [open]);

  if (!open) return null;

  return (
    <div
      className="fixed inset-0 z-50 flex items-start justify-center bg-black/40 pt-[15vh]"
      onClick={closePalette}
      data-testid="command-palette-overlay"
    >
      <div
        className="hairline w-full max-w-[560px] rounded-lg bg-surface-2 shadow-strong"
        onClick={(e) => e.stopPropagation()}
      >
        <Command
          label="Command palette"
          className="flex flex-col"
          shouldFilter
          loop
        >
          <Command.Input
            autoFocus
            placeholder="Type a command\u2026"
            className="w-full border-0 bg-transparent px-4 py-3 text-13 text-text-base placeholder:text-text-faint focus:outline-none"
          />
          <div className="hairline-top max-h-[50vh] overflow-auto scrollbar-thin p-1">
            <Command.List>
              <Command.Empty className="px-4 py-6 text-11 text-text-faint">
                No commands match.
              </Command.Empty>
              {groupBySection(catalog).map(([section, items]) => (
                <Command.Group
                  key={section}
                  heading={section}
                  className="text-11"
                >
                  {items.map((a) => (
                    <Command.Item
                      key={a.id}
                      value={`${a.section} ${a.label} ${a.hint ?? ""}`}
                      onSelect={() => {
                        a.run();
                        closePalette();
                      }}
                      className="flex cursor-pointer items-center gap-3 rounded px-3 py-2 text-12 text-text-base aria-selected:bg-surface-4"
                    >
                      <span className="min-w-0 flex-1 truncate">{a.label}</span>
                      <span className="text-11 text-text-faint">
                        {formatChord(resolveBinding(a))}
                      </span>
                    </Command.Item>
                  ))}
                </Command.Group>
              ))}
            </Command.List>
          </div>
        </Command>
      </div>
    </div>
  );
}

function groupBySection<T extends { section: string }>(
  items: T[],
): Array<[string, T[]]> {
  const map = new Map<string, T[]>();
  for (const it of items) {
    const list = map.get(it.section) ?? [];
    list.push(it);
    map.set(it.section, list);
  }
  return Array.from(map.entries());
}
