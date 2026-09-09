"use client";

import { Terminal } from "lucide-react";
import type { VisualizerProps } from "./registry";
import { ToolShell } from "./primitives/ToolShell";

interface BashArgs {
  cmd?: string;
  command?: string;
  cwd?: string;
}
interface BashResult {
  stdout?: string;
  stderr?: string;
  exit_code?: number;
}

export function BashVisualizer({ tool }: VisualizerProps) {
  const args = (tool.arguments ?? {}) as BashArgs;
  const cmd = args.cmd ?? args.command ?? "";
  const result = (tool.result ?? {}) as BashResult;
  const merged = tool.delta_chunks.join("");
  const output = merged || result.stdout || "";
  const err = result.stderr;

  return (
    <ToolShell
      tool={tool}
      title={
        <span className="inline-flex items-center gap-1 font-mono text-11">
          <Terminal className="h-3 w-3" />
          {cmd.slice(0, 80)}
          {cmd.length > 80 && "\u2026"}
        </span>
      }
      subtitle={args.cwd ? `cwd ${args.cwd}` : undefined}
    >
      {output && (
        <pre className="max-h-80 overflow-auto scrollbar-thin whitespace-pre-wrap rounded bg-surface-0 p-2 font-mono text-10 text-text-base">
          {output}
        </pre>
      )}
      {err && (
        <pre className="mt-1 max-h-40 overflow-auto scrollbar-thin whitespace-pre-wrap rounded bg-surface-0 p-2 font-mono text-10 text-error">
          {err}
        </pre>
      )}
      {result.exit_code !== undefined && result.exit_code !== 0 && (
        <div className="mt-1 text-10 text-error">exit {result.exit_code}</div>
      )}
      {tool.error && <div className="mt-1 text-11 text-error">{tool.error}</div>}
    </ToolShell>
  );
}
