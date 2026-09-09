"use client";

import { FilePlus, FileEdit } from "lucide-react";
import type { VisualizerProps } from "./registry";
import { ToolShell } from "./primitives/ToolShell";

interface Args {
  path?: string;
  file_path?: string;
  content?: string;
  mode?: string;
}
interface Result {
  bytes_written?: number;
  created?: boolean;
}

export function FileWriteVisualizer({ tool }: VisualizerProps) {
  const args = (tool.arguments ?? {}) as Args;
  const path = args.path ?? args.file_path ?? "";
  const result = (tool.result ?? {}) as Result;
  const Icon = result.created ? FilePlus : FileEdit;
  const preview = args.content ?? "";

  return (
    <ToolShell
      tool={tool}
      title={
        <span className="inline-flex items-center gap-1 font-mono text-11">
          <Icon className="h-3 w-3" />
          {path}
        </span>
      }
      subtitle={
        result.bytes_written !== undefined
          ? `${result.bytes_written.toLocaleString()} bytes`
          : preview
            ? `${preview.length.toLocaleString()} chars`
            : undefined
      }
      defaultOpen={false}
    >
      {preview && (
        <pre className="max-h-80 overflow-auto scrollbar-thin whitespace-pre-wrap rounded bg-surface-0 p-2 font-mono text-10 text-text-muted">
          {preview.slice(0, 4000)}
          {preview.length > 4000 && "\n\u2026"}
        </pre>
      )}
    </ToolShell>
  );
}
