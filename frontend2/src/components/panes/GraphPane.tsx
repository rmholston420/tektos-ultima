"use client";

import { useMemo } from "react";
import { useStore } from "@nanostores/react";
import { $messages, $toolCalls } from "@/lib/stores/session";
import { PanePlaceholder } from "./PanePlaceholder";

/**
 * Graph pane: minimal SVG dependency graph — assistant messages linked
 * to their correlated tool calls. Full d3-force layout arrives when
 * a dedicated graph service ships; for now this is a linear timeline.
 */
export default function GraphPane() {
  const byId = useStore($messages);
  const tools = useStore($toolCalls);

  const nodes = useMemo(() => {
    const list: Array<{ id: string; label: string; kind: "msg" | "tool"; status?: string }> = [];
    for (const id of Object.keys(byId)) {
      const m = byId[id];
      list.push({ id, label: `${m.role}${m.completed ? "" : "\u2026"}`, kind: "msg" });
      for (const tid of m.tool_call_ids) {
        const t = tools[tid];
        if (t) list.push({ id: tid, label: t.name, kind: "tool", status: t.status });
      }
    }
    return list;
  }, [byId, tools]);

  if (nodes.length === 0) {
    return <PanePlaceholder title="Graph" hint="Turn / tool dependency graph." />;
  }

  return (
    <div className="flex h-full flex-col text-11">
      <div className="hairline px-3 py-1.5 text-text-muted">
        {nodes.length} nodes
      </div>
      <ul className="flex-1 overflow-auto scrollbar-thin p-3 font-mono">
        {nodes.map((n, i) => (
          <li
            key={n.id}
            className={
              n.kind === "tool"
                ? "ml-4 text-text-muted"
                : "mt-2 text-text-base"
            }
          >
            <span className="text-text-faint">{i.toString().padStart(2, "0")} </span>
            {n.kind === "tool" ? "\u2937 " : ""}
            {n.label}
            {n.status && n.status !== "completed" && (
              <span className="ml-2 text-text-faint">[{n.status}]</span>
            )}
          </li>
        ))}
      </ul>
    </div>
  );
}
