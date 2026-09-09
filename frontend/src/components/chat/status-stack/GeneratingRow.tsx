"use client";

import { useEffect, useState } from "react";
import { useStore } from "@nanostores/react";
import { Loader2 } from "lucide-react";
import { $isGenerating, $messages, $messageOrder } from "@/lib/stores/session";
import { StatusRow } from "./StatusRow";

/**
 * Shows a live "assistant is generating…" indicator whenever the newest
 * assistant message is still open. Self-hides otherwise. Also surfaces the
 * elapsed seconds since the current turn started so an obviously-stuck turn
 * becomes visible instead of the user staring at a silent transcript.
 */
export function GeneratingRow() {
  const generating = useStore($isGenerating);
  const messages = useStore($messages);
  const order = useStore($messageOrder);
  const [nowMs, setNowMs] = useState(() => Date.now());

  useEffect(() => {
    if (!generating) return;
    const id = window.setInterval(() => setNowMs(Date.now()), 1000);
    return () => window.clearInterval(id);
  }, [generating]);

  if (!generating) return null;

  // Find the currently-open assistant message to time it.
  let startedAt: string | undefined;
  for (let i = order.length - 1; i >= 0; i--) {
    const m = messages[order[i]];
    if (!m) continue;
    if (m.role === "assistant" && !m.completed) {
      startedAt = m.created_at;
      break;
    }
  }
  const elapsedSec = startedAt
    ? Math.max(0, Math.floor((nowMs - new Date(startedAt).getTime()) / 1000))
    : 0;

  return (
    <StatusRow
      icon={<Loader2 className="h-3 w-3 animate-spin" />}
      tone="agent"
      data-testid="status-generating"
    >
      <span className="text-text-muted">assistant</span>{" "}
      <span className="text-text-base">generating…</span>
      {elapsedSec > 0 && (
        <span className="ml-2 font-mono text-text-muted">{elapsedSec}s</span>
      )}
    </StatusRow>
  );
}
