"use client";

import { useEffect, useRef, useState } from "react";
import { ProtocolClient } from "@/lib/protocol-client";
import { applyEnvelope } from "@/lib/stores/session";
import { $connectionError, $connectionState } from "@/lib/stores/connection";

let singleton: ProtocolClient | null = null;

function makeClient(): ProtocolClient {
  const c = new ProtocolClient();
  c.onStateChange((change) => {
    $connectionState.set(change.state);
    $connectionError.set(change.error ?? null);
  });
  c.on("*", (env) => applyEnvelope(env));
  c.connect();
  return c;
}

/**
 * Lazy-init singleton client. Safe to call from anywhere.
 *
 * On the server it returns a client instance that never touches the
 * WebSocket API (guarded internally by `ProtocolClient.connect`), so
 * callers can hold the reference; the SSR instance is thrown away
 * when the singleton is created on the client.
 *
 * IMPORTANT: this should NOT be called from render code — that would
 * flip `$connectionState` during hydration and produce a mismatch.
 * The AppShell mount gate makes all client-side callers safe by
 * definition (they only fire in event handlers after mount).
 */
export function getProtocolClient(): ProtocolClient {
  if (typeof window === "undefined") {
    // Server: return a stub-shaped instance without connecting. `connect()`
    // is only invoked on the client from `makeClient` above.
    return new ProtocolClient();
  }
  if (!singleton) singleton = makeClient();
  return singleton;
}

/** Mount-only hook: creates the singleton after first client render. */
export function useProtocol(): ProtocolClient | null {
  const ref = useRef<ProtocolClient | null>(null);
  const [, force] = useState(0);
  useEffect(() => {
    if (ref.current) return;
    ref.current = getProtocolClient();
    force((n) => n + 1);
  }, []);
  return ref.current;
}
