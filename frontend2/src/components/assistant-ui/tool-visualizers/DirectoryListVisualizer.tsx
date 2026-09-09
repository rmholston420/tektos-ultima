"use client";

import { Folder, FolderOpen, File as FileIcon } from "lucide-react";
import type { VisualizerProps } from "./registry";
import { ToolShell } from "./primitives/ToolShell";

interface Args {
  path?: string;
  directory?: string;
}
interface Entry {
  name: string;
  kind?: "file" | "directory";
  size?: number;
}
interface Result {
  entries?: Entry[];
  path?: string;
}

export function DirectoryListVisualizer({ tool }: VisualizerProps) {
  const args = (tool.arguments ?? {}) as Args;
  const path = args.path ?? args.directory ?? "";
  const result = (tool.result ?? {}) as Result;
  const entries = result.entries ?? [];

  return (
    <ToolShell
      tool={tool}
      title={
        <span className="inline-flex items-center gap-1 font-mono text-11">
          <FolderOpen className="h-3 w-3" />
          {path}
        </span>
      }
      subtitle={`${entries.length} entries`}
      defaultOpen={false}
    >
      {entries.length > 0 && (
        <ul className="max-h-80 overflow-auto scrollbar-thin font-mono text-10">
          {entries.slice(0, 200).map((e) => (
            <li key={e.name} className="flex items-center gap-1.5 py-0.5">
              {e.kind === "directory" ? (
                <Folder className="h-3 w-3 text-primary" />
              ) : (
                <FileIcon className="h-3 w-3 text-text-faint" />
              )}
              <span className="truncate text-text-base">{e.name}</span>
              {e.size !== undefined && e.kind !== "directory" && (
                <span className="ml-auto tabular text-text-faint">
                  {e.size.toLocaleString()}
                </span>
              )}
            </li>
          ))}
          {entries.length > 200 && (
            <li className="mt-1 text-text-faint">\u2026 {entries.length - 200} more</li>
          )}
        </ul>
      )}
    </ToolShell>
  );
}
