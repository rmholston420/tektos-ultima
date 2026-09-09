"use client";

import { useStore } from "@nanostores/react";
import { $connectionState } from "@/lib/stores/connection";
import { $sessionModel, $messages, $toolCalls, $artifactOrder } from "@/lib/stores/session";
import { $persistedSessions } from "@/lib/stores/persisted-sessions";

/**
 * Dashboard destination. Phase 6 ships a KPI card grid; Phase 8 ports
 * the ~50 dynamic panels from the legacy dashboard into the panel
 * registry that plugs in here.
 */
export default function DashboardPage() {
  const connState = useStore($connectionState);
  const model = useStore($sessionModel);
  const messages = useStore($messages);
  const tools = useStore($toolCalls);
  const artifacts = useStore($artifactOrder);
  const sessions = useStore($persistedSessions);

  const kpis = [
    { label: "Connection", value: connState },
    { label: "Active model", value: model ?? "\u2014" },
    { label: "Messages (session)", value: Object.keys(messages).length },
    { label: "Tool calls (session)", value: Object.keys(tools).length },
    { label: "Artifacts (session)", value: artifacts.length },
    { label: "Persisted sessions", value: sessions.length },
  ];

  return (
    <div className="flex h-full min-h-0 flex-col overflow-auto scrollbar-thin bg-surface-1">
      <div className="hairline px-4 py-3">
        <h1 className="text-14 font-medium text-text-base">Dashboard</h1>
        <div className="mt-1 text-11 text-text-muted">
          Phase 6 preview. Full panel grid ports in Phase 8.
        </div>
      </div>
      <div className="grid grid-cols-2 gap-3 p-4 sm:grid-cols-3 xl:grid-cols-4">
        {kpis.map((k) => (
          <div key={k.label} className="hairline rounded-md bg-surface-2 p-3">
            <div className="text-11 uppercase tracking-wide text-text-muted">
              {k.label}
            </div>
            <div className="mt-1 truncate font-mono text-16 text-text-base">
              {String(k.value)}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
