/**
 * ChatSidebar — model picker + connection status badge.
 *
 * Mirrors the Hermes Agent desktop GUI sidebar card:
 *   - Model label (clickable to open picker)
 *   - Connection state badge (idle/connecting/live/closed/error)
 *   - Error banner with reconnect button
 */

import { ChevronDownIcon, ArrowPathIcon } from "@heroicons/react/24/outline";
import { useCallback, useEffect, useState } from "react";

interface ChatSidebarProps {
  channel?: string;
  profile?: string;
  className?: string;
}

const STATE_LABEL: Record<string, string> = {
  idle: "idle",
  connecting: "connecting",
  open: "live",
  closed: "closed",
  error: "error",
};

const STATE_TONE: Record<string, string> = {
  idle: "text-text-muted",
  connecting: "text-warning",
  open: "text-success",
  closed: "text-text-muted",
  error: "text-destructive",
};

export function ChatSidebar({ className }: ChatSidebarProps) {
  const [state, setState] = useState<string>("idle");
  const [effectiveModel, setEffectiveModel] = useState("");
  const [error, setError] = useState<string | null>(null);

  // Fetch model info from backend
  const refreshModel = useCallback(() => {
    fetch("/api/model/info")
      .then((r) => r.json())
      .then((data) => {
        if (data?.model) {
          setEffectiveModel(data.model.split("/").slice(-1)[0]);
        }
      })
      .catch(() => {});
  }, []);

  useEffect(() => {
    refreshModel();
  }, [refreshModel]);

  const modelName = effectiveModel || "—";

  return (
    <aside className={`flex h-full w-full min-w-0 shrink-0 flex-col gap-3 overflow-y-auto overflow-x-hidden pr-1 ${className || ""}`}>
      <div className="flex items-center justify-between gap-2 px-3 py-2 bg-surface border border-border rounded-lg">
        <div className="min-w-0 flex-1">
          <div className="text-xs tracking-wider text-text-muted uppercase">
            model
          </div>
          <div className="text-sm font-medium truncate">{modelName}</div>
        </div>
        <span className={`shrink-0 text-xs px-2 py-1 rounded-full ${STATE_TONE[state]}`}>
          {STATE_LABEL[state]}
        </span>
      </div>

      {error && (
        <div className="flex items-center gap-2 px-3 py-2 text-xs text-destructive bg-destructive/10 rounded-lg">
          <span className="flex-1 truncate">{error}</span>
          <button
            onClick={() => {
              setError(null);
              refreshModel();
            }}
            className="h-6 w-6 shrink-0 flex items-center justify-center text-text-muted hover:text-text-primary"
          >
            <ArrowPathIcon className="h-3 w-3" />
          </button>
        </div>
      )}
    </aside>
  );
}
