"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { CommandPalette } from "./CommandPalette";
import { registerDefaultActions } from "./register";
import { useKeybinds } from "@/lib/keybinds/useKeybinds";
import { hydrateKeybindOverrides } from "@/lib/keybinds/registry";

/**
 * Client-only mount for the palette + global keybinds. Rendered once
 * in AppShell so it's alive on every route.
 */
export function PaletteMount() {
  const router = useRouter();
  useEffect(() => {
    hydrateKeybindOverrides();
    registerDefaultActions((href) => router.push(href));
  }, [router]);
  useKeybinds();
  return <CommandPalette />;
}
