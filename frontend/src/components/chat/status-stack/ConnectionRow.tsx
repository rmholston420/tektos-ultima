"use client";

import { useStore } from "@nanostores/react";
import { Wifi, WifiOff, RefreshCw } from "lucide-react";
import { $connectionError, $connectionState } from "@/lib/stores/connection";
import { getProtocolClient } from "@/lib/hooks/useProtocol";
import { StatusRow } from "./StatusRow";

export function ConnectionRow() {
  const state = useStore($connectionState);
  const error = useStore($connectionError);
  if (state === "connected") return null;

  const tone = state === "disconnected" ? "error" : "agent";
  const Icon = state === "disconnected" ? WifiOff : Wifi;
  return (
    <StatusRow
      icon={<Icon className="h-3 w-3" />}
      tone={tone}
      data-testid="status-connection"
      actions={
        state === "disconnected" && (
          <button
            className="inline-flex items-center gap-1 rounded px-1.5 py-0.5 text-11 text-text-muted hover:bg-surface-4"
            onClick={() => getProtocolClient().reconnect()}
            title="Reconnect"
          >
            <RefreshCw className="h-3 w-3" />
            reconnect
          </button>
        )
      }
    >
      gateway {state}
      {error && <> · {error}</>}
    </StatusRow>
  );
}
