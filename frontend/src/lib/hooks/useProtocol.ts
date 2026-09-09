"use client";

import { useEffect, useRef } from "react";
import { ProtocolClient } from "@/lib/protocol-client";
import { applyEnvelope } from "@/lib/stores/session";
import { $connectionError, $connectionState } from "@/lib/stores/connection";

let singleton: ProtocolClient | null = null;

/**
 * Lazy-init singleton client. Returned from `useProtocol()` so components
 * can send prompts and interrupts without reaching into module state.
 */
export function getProtocolClient(): ProtocolClient {
  if (typeof window === "undefined") {
    // SSR safety: return a stub-shaped instance; real client is created on the client.
    return new ProtocolClient();
  }
  if (!singleton) {
    singleton = new ProtocolClient();
    singleton.onStateChange((change) => {
      $connectionState.set(change.state);
      $connectionError.set(change.error ?? null);
    });
    singleton.on("*", (env) => applyEnvelope(env));
    singleton.connect();
  }
  return singleton;
}

/** Mount-only hook: ensures the singleton exists on the client. */
export function useProtocol(): ProtocolClient {
  const ref = useRef<ProtocolClient | null>(null);
  if (ref.current === null && typeof window !== "undefined") {
    ref.current = getProtocolClient();
  }
  useEffect(() => {
    if (typeof window === "undefined") return;
    if (!ref.current) ref.current = getProtocolClient();
  }, []);
  // Always return a valid client (stub on the server) for hook stability.
  return ref.current ?? getProtocolClient();
}
