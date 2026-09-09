"use client";

import { FileText } from "lucide-react";
import type { VisualizerProps } from "./registry";
import { ToolShell } from "./primitives/ToolShell";

interface Args {
  path?: string;
  file_path?: string;
  offset?: number;
  limit?: number;
}
interface Result {
  content?: string;
  lines?: number;
  start_line?: number;
}

export function FileReadVisualizer({ tool }: VisualizerProps) {
  const args = (tool.arguments ?? {}) as Args;
  const path = args.path ?? args.file_path ?? "";
  const result = (tool.result ?? {}) as Result;
  const content = result.content ?? tool.delta_chunks.join("");

  return (
    <ToolShell
      tool={tool}
      title={
        <span className="inline-flex items-center gap-1 font-mono text-11">
          <FileText className="h-3 w-3" />
          {path}
        </span>
      }
      subtitle={
        result.lines
          ? `${result.lines} lines${result.start_line ? ` from ${result.start_line}` : ""}`
          : args.limit
            ? `range ${args.offset ?? 0}\u2013${(args.offset ?? 0) + args.limit}`
            : undefined
      }
      defaultOpen={false}
    >
      {content && (
        <pre className="max-h-80 overflow-auto scrollbar-thin whitespace-pre-wrap rounded bg-surface-0 p-2 font-mono text-10 text-text-base">
          {content}
        </pre>
      )}
    </ToolShell>
  );
}
