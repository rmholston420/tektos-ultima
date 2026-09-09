"use client";

import { useEffect, useRef, useState } from "react";
import { useStore } from "@nanostores/react";
import { $toolCalls } from "@/lib/stores/session";
import { PanePlaceholder } from "./PanePlaceholder";

type XTerm = {
  dispose: () => void;
  write: (s: string) => void;
  clear: () => void;
  onData: (cb: (s: string) => void) => { dispose: () => void };
  onResize: (cb: (e: { cols: number; rows: number }) => void) => { dispose: () => void };
  cols: number;
  rows: number;
};

/**
 * Terminal pane with two modes:
 *   1. Interactive PTY (default) — bidirectional shell over /ws/pty.
 *   2. bash-tool replay — last bash tool call output, useful for reviewing
 *      what the agent ran without opening a live shell.
 */
export default function TerminalPane() {
  const tools = useStore($toolCalls);
  const [mode, setMode] = useState<"pty" | "replay">("pty");
  const containerRef = useRef<HTMLDivElement>(null);
  const termRef = useRef<XTerm | null>(null);
  const wsRef = useRef<WebSocket | null>(null);
  const [connected, setConnected] = useState(false);

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
      if (disposed || !containerRef.current) return;
      const term = new Terminal({
        fontFamily: "var(--font-mono)",
        fontSize: 12,
        theme: { background: "#101010", foreground: "#CDCCCA" },
        convertEol: true,
        disableStdin: mode === "replay",
        scrollback: 5000,
        cursorBlink: mode === "pty",
      });
      const fit = new FitAddon();
      term.loadAddon(fit);
      term.open(containerRef.current);
      fit.fit();
      termRef.current = term as unknown as XTerm;

      if (mode === "pty") {
        const wsProto = window.location.protocol === "https:" ? "wss:" : "ws:";
        const backendHost =
          process.env.NEXT_PUBLIC_TEKTOS_WS_HOST || `${window.location.hostname}:8020`;
        const ws = new WebSocket(`${wsProto}//${backendHost}/ws/pty`);
        wsRef.current = ws;
        ws.onopen = () => {
          setConnected(true);
          ws.send(JSON.stringify({ type: "resize", cols: term.cols, rows: term.rows }));
        };
        ws.onclose = () => setConnected(false);
        ws.onmessage = (ev) => {
          try {
            const msg = JSON.parse(ev.data);
            if (msg.type === "output" && typeof msg.data === "string") {
              term.write(msg.data);
            } else if (msg.type === "exit") {
              term.write(`\r\n\x1b[33m[shell exited: ${msg.code}]\x1b[0m\r\n`);
            }
          } catch {}
        };
        term.onData((data) => {
          if (ws.readyState === WebSocket.OPEN) {
            ws.send(JSON.stringify({ type: "input", data }));
          }
        });
        term.onResize(({ cols, rows }) => {
          if (ws.readyState === WebSocket.OPEN) {
            ws.send(JSON.stringify({ type: "resize", cols, rows }));
          }
        });
      }
    }
    void mount();
    return () => {
      disposed = true;
      wsRef.current?.close();
      wsRef.current = null;
      termRef.current?.dispose();
      termRef.current = null;
      setConnected(false);
    };
  }, [mode]);

  // Replay-mode: repaint on new bash tool output.
  useEffect(() => {
    if (mode !== "replay") return;
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
  }, [mode, bash?.id, bash?.status, bash?.delta_chunks.length]); // eslint-disable-line react-hooks/exhaustive-deps

  if (mode === "replay" && !bash) {
    return (
      <div className="flex h-full flex-col">
        <TerminalHeader mode={mode} connected={connected} onModeChange={setMode} label="no bash yet" />
        <PanePlaceholder title="Terminal" hint="bash tool output renders here." />
      </div>
    );
  }

  return (
    <div className="flex h-full flex-col">
      <TerminalHeader
        mode={mode}
        connected={connected}
        onModeChange={setMode}
        label={mode === "pty" ? "interactive shell" : bash?.name || "bash"}
      />
      <div ref={containerRef} className="min-h-0 flex-1 bg-[#101010] p-1" />
    </div>
  );
}

function TerminalHeader({
  mode,
  connected,
  onModeChange,
  label,
}: {
  mode: "pty" | "replay";
  connected: boolean;
  onModeChange: (m: "pty" | "replay") => void;
  label: string;
}) {
  return (
    <div className="hairline flex items-center gap-3 px-3 py-1.5 text-11 text-text-muted">
      <span className="font-mono text-text-base">{label}</span>
      {mode === "pty" && (
        <span className={connected ? "text-green-400" : "text-red-400"}>
          {connected ? "\u2022 connected" : "\u2022 disconnected"}
        </span>
      )}
      <div className="ml-auto flex items-center gap-1">
        <button
          onClick={() => onModeChange("pty")}
          className={`rounded px-2 py-0.5 ${mode === "pty" ? "bg-primary text-surface-0" : "hover:bg-surface-6"}`}
        >
          PTY
        </button>
        <button
          onClick={() => onModeChange("replay")}
          className={`rounded px-2 py-0.5 ${mode === "replay" ? "bg-primary text-surface-0" : "hover:bg-surface-6"}`}
        >
          Replay
        </button>
      </div>
    </div>
  );
}
