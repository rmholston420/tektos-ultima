"use client";

import { useStore } from "@nanostores/react";
import { CheckCircle2, Clock } from "lucide-react";
import { $messages, $messageOrder, $sessionId } from "@/lib/stores/session";

/**
 * Runs destination: one row per assistant message in the current session.
 * Shows completion status and message excerpt. Backend run persistence
 * (planned) will replace the in-memory source with a query over the run
 * store.
 */
export default function RunsPage() {
  const byId = useStore($messages);
  const order = useStore($messageOrder);
  const sessionId = useStore($sessionId);

  const runs = order
    .map((id) => byId[id])
    .filter((m): m is NonNullable<typeof m> => Boolean(m && m.role === "assistant"));

  return (
    <div className="flex h-full min-h-0 flex-col overflow-auto scrollbar-thin bg-surface-1">
      <div className="hairline flex items-center justify-between px-4 py-3">
        <h1 className="text-14 font-medium text-text-base">Runs</h1>
        <span className="text-11 text-text-muted">
          {runs.length} in session {sessionId ? `· ${sessionId.slice(0, 8)}` : ""}
        </span>
      </div>
      {runs.length === 0 ? (
        <div className="flex flex-1 items-center justify-center text-11 text-text-muted">
          No runs yet in this session.
        </div>
      ) : (
        <ul className="divide-y divide-[var(--stroke)]">
          {runs.map((m) => {
            const Icon = m.completed ? CheckCircle2 : Clock;
            const tone = m.completed ? "text-success" : "text-agent";
            const usage = m.usage;
            return (
              <li key={m.id} className="flex items-start gap-3 px-4 py-2.5">
                <Icon className={`mt-0.5 h-3.5 w-3.5 shrink-0 ${tone}`} />
                <div className="min-w-0 flex-1">
                  <div className="truncate text-12 text-text-base">
                    {m.text.slice(0, 200) || <em className="text-text-faint">(no text yet)</em>}
                  </div>
                  <div className="mt-0.5 flex items-center gap-2 text-11 text-text-faint">
                    <span className="font-mono">{m.id.slice(0, 8)}</span>
                    {m.tool_call_ids.length > 0 && (
                      <span>· {m.tool_call_ids.length} tool{m.tool_call_ids.length === 1 ? "" : "s"}</span>
                    )}
                    {usage?.total !== undefined && <span>· {usage.total} tok</span>}
                  </div>
                </div>
              </li>
            );
          })}
        </ul>
      )}
    </div>
  );
}
