"use client";

import { useState, type ReactNode } from "react";
import { ChevronDown, ChevronRight } from "lucide-react";
import { cn } from "@/lib/cn";
import type { ToolCallRecord } from "@/lib/stores/session";
import { StatusIndicator } from "./StatusIndicator";

interface Props {
  tool: ToolCallRecord;
  title?: ReactNode;
  subtitle?: ReactNode;
  defaultOpen?: boolean;
  children?: ReactNode;
}

/**
 * Standard collapsible card used by every specialized visualizer. Keeps
 * header/status/duration consistent across tools; body is opt-in.
 */
export function ToolShell({ tool, title, subtitle, defaultOpen = true, children }: Props) {
  const [open, setOpen] = useState(defaultOpen);
  const Chevron = open ? ChevronDown : ChevronRight;
  const hasBody = Boolean(children);

  return (
    <div
      className={cn(
        "hairline rounded bg-surface-2",
        tool.status === "errored" && "bg-surface-3",
      )}
      data-testid="tool-card"
      data-tool={tool.name}
      data-status={tool.status}
    >
      <button
        type="button"
        onClick={() => hasBody && setOpen((v) => !v)}
        className={cn(
          "flex w-full items-center gap-2 rounded px-2.5 py-2 text-left",
          hasBody && "hover:bg-surface-3",
        )}
      >
        {hasBody ? (
          <Chevron className="h-3 w-3 text-text-faint" />
        ) : (
          <span className="w-3" />
        )}
        <StatusIndicator status={tool.status} />
        <div className="min-w-0 flex-1">
          <div className="truncate text-11 text-text-base">
            <span className="font-mono">{tool.name}</span>
            {title && <span className="ml-2 text-text-muted">{title}</span>}
          </div>
          {subtitle && (
            <div className="mt-0.5 truncate text-10 text-text-faint">{subtitle}</div>
          )}
        </div>
        {tool.duration_ms !== undefined && (
          <span className="tabular text-10 text-text-faint">{tool.duration_ms}ms</span>
        )}
      </button>
      {hasBody && open && (
        <div className="border-t border-[var(--stroke)] p-2.5 pt-2">
          {children}
        </div>
      )}
    </div>
  );
}
