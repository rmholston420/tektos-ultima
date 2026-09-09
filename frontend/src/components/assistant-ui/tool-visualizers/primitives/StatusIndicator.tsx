"use client";

import { CheckCircle2, CircleDashed, XCircle, type LucideProps } from "lucide-react";
import { cn } from "@/lib/cn";
import type { ToolCallRecord } from "@/lib/stores/session";

export function StatusIndicator({
  status,
  className,
  ...rest
}: { status: ToolCallRecord["status"]; className?: string } & Omit<LucideProps, "ref">) {
  const Icon =
    status === "running" ? CircleDashed : status === "errored" ? XCircle : CheckCircle2;
  const tone =
    status === "running"
      ? "text-agent animate-tektos-pulse"
      : status === "errored"
        ? "text-error"
        : "text-success";
  return <Icon className={cn("h-3 w-3", tone, className)} {...rest} />;
}
