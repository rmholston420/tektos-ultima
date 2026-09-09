/**
 * SidebarStatusStrip — gateway status + active sessions count.
 *
 * Mirrors the Hermes Agent desktop GUI sidebar status block.
 */

import { useCallback, useEffect, useState } from "react";

interface StatusResponse {
  gateway_state?: string;
  gateway_running?: boolean;
  active_sessions?: number;
  version?: string;
}

interface SidebarStatusStripProps {
  className?: string;
}

export function SidebarStatusStrip({ className }: SidebarStatusStripProps) {
  const [status, setStatus] = useState<StatusResponse | null>(null);
  const [loading, setLoading] = useState(true);

  const load = useCallback(() => {
    fetch("/api/status")
      .then((r) => r.json())
      .then((data) => {
        setStatus(data);
        setLoading(false);
      })
      .catch(() => {
        setLoading(false);
      });
  }, []);

  useEffect(() => {
    load();
    const interval = setInterval(load, 10000);
    return () => clearInterval(interval);
  }, [load]);

  if (loading) {
    return (
      <div className={`px-5 py-1.5 ${className || ""}`} aria-hidden>
        <div className="h-2 w-[80%] max-w-full animate-pulse rounded-sm bg-border/50" />
      </div>
    );
  }

  if (!status) return null;

  const gwLabel = status.gateway_running
    ? status.gateway_state === "running"
      ? "Running"
      : "Running"
    : "Stopped";
  const gwTone = status.gateway_running ? "text-success" : "text-text-muted";

  return (
    <div className={`block text-left px-5 pb-2 pt-0.5 text-text-secondary transition-colors hover:text-midground ${className || ""}`}>
      <div className="flex flex-col gap-1 font-sans text-xs leading-snug tracking-[0.08em]">
        <p className="break-words">
          <span className="text-text-muted">Gateway</span>{" "}
          <span className={`font-medium ${gwTone}`}>{gwLabel}</span>
        </p>
        <p className="break-words">
          <span className="text-text-muted">Sessions</span>{" "}
          <span className="tabular-nums text-text-secondary">
            {status.active_sessions ?? 0}
          </span>
        </p>
      </div>
    </div>
  );
}
