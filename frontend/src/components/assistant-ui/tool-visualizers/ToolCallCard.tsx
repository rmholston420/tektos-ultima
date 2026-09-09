"use client";

import { CheckCircle2, CircleDashed, XCircle } from "lucide-react";
import { cn } from "@/lib/cn";
import type { ToolCallRecord } from "@/lib/stores/session";
import { getVisualizer } from "./registry";

/**
 * Phase-2 fallback renderer. The registry (Phase 3) will look up a
 * per-tool component; anything unknown falls back to this generic view.
 */
export function ToolCallCard({ tool }: { tool: ToolCallRecord }) {
  const Visualizer = getVisualizer(tool.name);
  if (Visualizer) return <Visualizer tool={tool} />;

  const StatusIcon =
    tool.status === "running"
      ? CircleDashed
      : tool.status === "errored"
        ? XCircle
        : CheckCircle2;
  const statusClass =
    tool.status === "running"
      ? "text-agent animate-tektos-pulse"
      : tool.status === "errored"
        ? "text-error"
        : "text-success";

  const merged = tool.delta_chunks.join("");

  return (
    <div
      className={cn(
        "hairline rounded bg-surface-2 p-2.5",
        "text-11 text-text-muted",
      )}
      data-testid="tool-card"
      data-tool={tool.name}
      data-status={tool.status}
    >
      <div className="flex items-center gap-2">
        <StatusIcon className={cn("h-3 w-3", statusClass)} />
        <span className="font-mono text-text-base">{tool.name}</span>
        {tool.duration_ms !== undefined && (
          <span className="tabular text-text-faint">{tool.duration_ms}ms</span>
        )}
      </div>
      {tool.arguments && Object.keys(tool.arguments).length > 0 && (
        <pre className="mt-2 max-h-40 overflow-auto scrollbar-thin whitespace-pre-wrap font-mono text-10 text-text-faint">
          {JSON.stringify(tool.arguments, null, 2)}
        </pre>
      )}
      {merged && (
        <pre className="mt-2 max-h-60 overflow-auto scrollbar-thin whitespace-pre-wrap font-mono text-10 text-text-muted">
          {merged}
        </pre>
      )}
      {tool.error && (
        <div className="mt-2 text-11 text-error">{tool.error}</div>
      )}
    </div>
  );
}
