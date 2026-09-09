"use client";

import { useStore } from "@nanostores/react";
import { Activity, X } from "lucide-react";
import { $resourceWarnings } from "@/lib/stores/session";
import { StatusRow } from "./StatusRow";

export function ResourceRow() {
  const warnings = useStore($resourceWarnings);
  if (warnings.length === 0) return null;
  const latest = warnings[warnings.length - 1];
  const dismiss = () => {
    $resourceWarnings.set(warnings.slice(0, -1));
  };
  return (
    <StatusRow
      icon={<Activity className="h-3 w-3" />}
      tone="warn"
      data-testid="status-resource"
      actions={
        <button
          className="rounded p-0.5 text-text-faint hover:bg-surface-4"
          onClick={dismiss}
          title="Dismiss"
        >
          <X className="h-3 w-3" />
        </button>
      }
    >
      <span className="font-mono text-text-base">{latest.kind}</span>{" "}
      <span>{latest.message}</span>
    </StatusRow>
  );
}
