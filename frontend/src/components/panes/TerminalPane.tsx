"use client";

import { useEffect, useRef } from "react";
import { useStore } from "@nanostores/react";
import { $toolCalls } from "@/lib/stores/session";
import { PanePlaceholder } from "./PanePlaceholder";

/**
 * Terminal pane: xterm-rendered output of the most recent bash call.
 * Read-only in Phase 5 (interactive PTY lands with the backend
 * bidirectional terminal channel).
 */
export default function TerminalPane() {
  const tools = useStore($toolCalls);
  const containerRef = useRef<HTMLDivElement>(null);
  const termRef = useRef<{ dispose: () => void; write: (s: string) => void; clear: () => void } | null>(null);

  const bash = (() => {
    const list = Object.values(tools);
    for (let i = list.length - 1; i >= 0; i--) {
      const t = list[i];
      if (t.name === "bash" || t.name === "shell") return t;
    }
    return null;
  })();

  useEffect(() => {
    let disposed = false;
    async function mount() {
      if (!containerRef.current) return;
      const { Terminal } = await import("@xterm/xterm");
      const { FitAddon } = await import("@xterm/addon-fit");
      // xterm.css injected via globals.css @import
      if (disposed || !containerRef.current) return;
      const term = new Terminal({
        fontFamily: "var(--font-mono)",
        fontSize: 12,
        theme: { background: "#101010", foreground: "#CDCCCA" },
        convertEol: true,
        disableStdin: true,
        scrollback: 5000,
      });
      const fit = new FitAddon();
      term.loadAddon(fit);
      term.open(containerRef.current);
      fit.fit();
      termRef.current = term;
    }
    void mount();
    return () => {
      disposed = true;
      termRef.current?.dispose();
      termRef.current = null;
    };
  }, []);

  useEffect(() => {
    const term = termRef.current;
    if (!term || !bash) return;
    term.clear();
    const args = (bash.arguments ?? {}) as { cmd?: string; command?: string };
    const cmd = args.cmd ?? args.command ?? "";
    if (cmd) term.write(`\x1b[36m$\x1b[0m ${cmd}\r\n`);
    const merged = bash.delta_chunks.join("");
    const result = (bash.result ?? {}) as { stdout?: string; stderr?: string };
    if (merged) term.write(merged);
    else if (result.stdout) term.write(result.stdout);
    if (result.stderr) term.write(`\x1b[31m${result.stderr}\x1b[0m`);
  }, [bash?.id, bash?.status, bash?.delta_chunks.length]); // eslint-disable-line react-hooks/exhaustive-deps

  if (!bash) {
    return <PanePlaceholder title="Terminal" hint="bash tool output renders here." />;
  }

  return (
    <div className="flex h-full flex-col">
      <div className="hairline px-3 py-1.5 text-11 text-text-muted">
        <span className="font-mono text-text-base">{bash.name}</span>
        {bash.status === "running" && <span className="ml-2 text-agent">\u2022 running</span>}
      </div>
      <div ref={containerRef} className="min-h-0 flex-1 bg-[#101010] p-1" />
    </div>
  );
}
