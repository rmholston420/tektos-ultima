"use client";

import { useEffect, useMemo, useState, type ReactElement } from "react";
import { useStore } from "@nanostores/react";
import { $toolCalls } from "@/lib/stores/session";
import { PanePlaceholder } from "./PanePlaceholder";

/**
 * Diff pane: Monaco Diff editor for the latest file_write that includes
 * both `previous` and `content` in its result, or a placeholder otherwise.
 */
export default function DiffPane() {
  const tools = useStore($toolCalls);
  const [Diff, setDiff] = useState<null | ((props: DiffProps) => ReactElement)>(null);

  useEffect(() => {
    let mounted = true;
    import("@monaco-editor/react").then((mod) => {
      if (mounted) {
        const D = mod.DiffEditor as unknown as (props: DiffProps) => ReactElement;
        setDiff(() => D);
      }
    });
    return () => {
      mounted = false;
    };
  }, []);

  const latest = useMemo(() => {
    const list = Object.values(tools);
    for (let i = list.length - 1; i >= 0; i--) {
      const t = list[i];
      if (t.name !== "file_write" && t.name !== "write_file") continue;
      const args = (t.arguments ?? {}) as { path?: string; file_path?: string; content?: string };
      const result = (t.result ?? {}) as { previous?: string; content?: string };
      if (result.previous !== undefined && (result.content ?? args.content) !== undefined) {
        return {
          path: args.path ?? args.file_path ?? "unknown",
          before: result.previous,
          after: result.content ?? args.content ?? "",
        };
      }
    }
    return null;
  }, [tools]);

  if (!latest) {
    return (
      <PanePlaceholder
        title="Diff"
        hint="file_write results with { previous, content } render here."
      />
    );
  }

  return (
    <div className="flex h-full flex-col text-11">
      <div className="hairline px-3 py-1.5 font-mono text-text-base">{latest.path}</div>
      <div className="min-h-0 flex-1 bg-surface-0">
        {Diff ? (
          <Diff
            original={latest.before}
            modified={latest.after}
            theme="vs-dark"
            options={{
              readOnly: true,
              renderSideBySide: true,
              minimap: { enabled: false },
              fontSize: 12,
            }}
          />
        ) : (
          <div className="p-3 text-text-faint">loading diff\u2026</div>
        )}
      </div>
    </div>
  );
}

interface DiffProps {
  original: string;
  modified: string;
  theme: string;
  options?: Record<string, unknown>;
}
