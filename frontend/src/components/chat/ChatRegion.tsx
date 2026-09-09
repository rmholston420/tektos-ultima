"use client";

import { useEffect } from "react";
import { Transcript } from "./Transcript";
import { Composer } from "./Composer";
import { PermissionModal } from "./PermissionModal";
import { StatusStack } from "./status-stack/StatusStack";
import { getProtocolClient } from "@/lib/hooks/useProtocol";

/**
 * Chat region: transcript above, composer below.
 * Wires Esc as a global interrupt keybind and mounts the permission
 * modal for tool.permission.required prompts.
 */
export function ChatRegion() {
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        getProtocolClient().sendInterrupt();
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  return (
    <div className="grid h-full grid-rows-[1fr_auto] bg-surface-1">
      <Transcript />
      <div className="hairline bg-surface-2 px-4 pb-3 pt-2">
        <div className="mx-auto max-w-[760px] space-y-1.5">
          <StatusStack />
          <Composer />
        </div>
      </div>
      <PermissionModal />
    </div>
  );
}
