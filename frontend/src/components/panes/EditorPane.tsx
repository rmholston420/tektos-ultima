"use client";

import { useEffect, useMemo, useRef, useState, type ReactElement } from "react";
import { useStore } from "@nanostores/react";
import { $toolCalls } from "@/lib/stores/session";
import { PanePlaceholder } from "./PanePlaceholder";
import { cn } from "@/lib/cn";

/**
 * Editor pane: read-only Monaco view of the last file_read / file_write
 * from the transcript, or an empty state when nothing to show.
 *
 * Monaco is dynamically imported so it doesn't ship in the initial bundle.
 */
export default function EditorPane() {
  const tools = useStore($toolCalls);
  const [Editor, setEditor] = useState<null | ((props: EditorProps) => ReactElement)>(null);
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    let mounted = true;
    import("@monaco-editor/react").then((mod) => {
      if (mounted) {
        const M = mod.default as unknown as (props: EditorProps) => ReactElement;
        setEditor(() => M);
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
      if (["file_read", "read_file", "file_write", "write_file"].includes(t.name)) {
        const args = (t.arguments ?? {}) as { path?: string; file_path?: string; content?: string };
        const path = args.path ?? args.file_path;
        const content =
          args.content ??
          (t.result && typeof t.result === "object"
            ? ((t.result as { content?: string }).content ?? "")
            : "") ??
          t.delta_chunks.join("");
        if (path) return { path, content: content ?? "" };
      }
    }
    return null;
  }, [tools]);

  if (!latest) {
    return (
      <PanePlaceholder
        title="Editor"
        hint="Reads and writes from file_read / file_write render here."
      />
    );
  }

  const lang = detectLanguage(latest.path);

  return (
    <div className="flex h-full flex-col text-11">
      <div className="hairline flex items-center gap-2 px-3 py-1.5 text-text-muted">
        <span className="truncate font-mono text-text-base">{latest.path}</span>
        <span className="ml-auto shrink-0 text-text-faint">{lang}</span>
      </div>
      <div ref={containerRef} className={cn("min-h-0 flex-1 bg-surface-0")}>
        {Editor ? (
          <Editor
            key={latest.path}
            language={lang}
            value={latest.content}
            theme="vs-dark"
            options={{
              readOnly: true,
              minimap: { enabled: false },
              fontSize: 12,
              fontFamily: "var(--font-mono)",
              wordWrap: "on",
              scrollBeyondLastLine: false,
            }}
          />
        ) : (
          <div className="p-3 text-text-faint">loading editor\u2026</div>
        )}
      </div>
    </div>
  );
}

interface EditorProps {
  language: string;
  value: string;
  theme: string;
  options?: Record<string, unknown>;
}

function detectLanguage(path: string): string {
  const ext = path.split(".").pop() ?? "";
  const map: Record<string, string> = {
    ts: "typescript",
    tsx: "typescript",
    js: "javascript",
    jsx: "javascript",
    py: "python",
    json: "json",
    md: "markdown",
    css: "css",
    html: "html",
    yml: "yaml",
    yaml: "yaml",
    sh: "shell",
    bash: "shell",
    rs: "rust",
    go: "go",
    toml: "ini",
  };
  return map[ext] ?? "plaintext";
}
