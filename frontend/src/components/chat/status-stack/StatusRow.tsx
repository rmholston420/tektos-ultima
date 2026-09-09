"use client";

import { type ReactNode } from "react";
import { cn } from "@/lib/cn";

type Tone = "info" | "success" | "warn" | "error" | "agent";

const toneClass: Record<Tone, string> = {
  info: "text-text-muted",
  success: "text-success",
  warn: "text-warning",
  error: "text-error",
  agent: "text-agent",
};

interface Props {
  icon: ReactNode;
  tone?: Tone;
  children: ReactNode;
  actions?: ReactNode;
  "data-testid"?: string;
}

/**
 * One compact row in the status stack. 22px tall, monospaced label, one
 * message, optional action buttons on the right.
 */
export function StatusRow({ icon, tone = "info", children, actions, ...rest }: Props) {
  return (
    <div
      className={cn(
        "flex h-[22px] items-center gap-2 px-2 text-11",
        toneClass[tone],
      )}
      role="status"
      {...rest}
    >
      <span className={cn("shrink-0", toneClass[tone])}>{icon}</span>
      <span className="min-w-0 flex-1 truncate">{children}</span>
      {actions && <span className="flex shrink-0 items-center gap-1">{actions}</span>}
    </div>
  );
}
