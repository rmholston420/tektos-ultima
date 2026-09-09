"use client";

import { useEffect } from "react";
import { useParams } from "next/navigation";
import { ChatRegion } from "@/components/chat/ChatRegion";
import { $sessionId } from "@/lib/stores/session";

/**
 * Dynamic session route. The current architecture keeps a single active
 * session per WebSocket; loading /s/[id] resets \$sessionId so the store
 * treats a new session.created for this ID as the active session.
 */
export default function SessionPage() {
  const params = useParams();
  const id = String(params?.id ?? "");
  useEffect(() => {
    if (!id) return;
    $sessionId.set(id);
  }, [id]);
  return <ChatRegion />;
}
