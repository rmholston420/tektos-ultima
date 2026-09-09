"use client";

import { useStore } from "@nanostores/react";
import { $systemNotices } from "@/lib/stores/session";
import { PanePlaceholder } from "./PanePlaceholder";
import { cn } from "@/lib/cn";

const toneClass: Record<"info" | "warn" | "error", string> = {
  info: "text-text-muted",
  warn: "text-warning",
  error: "text-error",
};

/**
 * Logs pane: system.message + session.interrupted/failed rendered as a
 * scrollable timeline.
 */
export default function LogsPane() {
  const notices = useStore($systemNotices);
  if (notices.length === 0) {
    return <PanePlaceholder title="Logs" hint="system.message events accumulate here." />;
  }
  return (
    <div className="flex h-full flex-col text-11">
      <div className="hairline px-3 py-1.5 text-text-muted">{notices.length} entries</div>
      <ul className="flex-1 overflow-auto scrollbar-thin font-mono">
        {notices.map((n, i) => (
          <li
            key={i}
            className={cn(
              "border-b border-[var(--stroke)] px-3 py-1.5",
              toneClass[n.level],
            )}
          >
            <span className="text-text-faint">
              {new Date(n.at).toISOString().slice(11, 19)}{" "}
            </span>
            <span className="uppercase text-text-faint">{n.level}</span>{" "}
            <span>{n.message}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}
