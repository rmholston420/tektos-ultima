"use client";

import { Search } from "lucide-react";
import type { VisualizerProps } from "./registry";
import { ToolShell } from "./primitives/ToolShell";

interface Args {
  query?: string;
  pattern?: string;
  path?: string;
}
interface Match {
  file?: string;
  path?: string;
  line?: number;
  text?: string;
}
interface Result {
  matches?: Match[];
  count?: number;
}

export function SearchVisualizer({ tool }: VisualizerProps) {
  const args = (tool.arguments ?? {}) as Args;
  const query = args.query ?? args.pattern ?? "";
  const result = (tool.result ?? {}) as Result;
  const matches = result.matches ?? [];

  return (
    <ToolShell
      tool={tool}
      title={
        <span className="inline-flex items-center gap-1 font-mono text-11">
          <Search className="h-3 w-3" />
          {query}
        </span>
      }
      subtitle={
        result.count !== undefined
          ? `${result.count} matches`
          : `${matches.length} matches${args.path ? ` in ${args.path}` : ""}`
      }
      defaultOpen={matches.length > 0 && matches.length <= 20}
    >
      {matches.length > 0 && (
        <ul className="max-h-80 overflow-auto scrollbar-thin font-mono text-10">
          {matches.slice(0, 100).map((m, i) => (
            <li key={i} className="py-0.5">
              <span className="text-primary">{m.file ?? m.path}</span>
              {m.line !== undefined && (
                <span className="text-text-faint">:{m.line}</span>
              )}
              {m.text && (
                <span className="ml-2 text-text-base">{m.text.trim()}</span>
              )}
            </li>
          ))}
          {matches.length > 100 && (
            <li className="mt-1 text-text-faint">\u2026 {matches.length - 100} more</li>
          )}
        </ul>
      )}
    </ToolShell>
  );
}
