"use client";

import { useStore } from "@nanostores/react";
import { ShieldAlert, Check, X } from "lucide-react";
import { $permissionQueue, resolvePermission } from "@/lib/stores/session";
import { getProtocolClient } from "@/lib/hooks/useProtocol";
import { StatusRow } from "./StatusRow";

/**
 * Peripheral permission row. The blocking modal renders in parallel;
 * this row exists so long-running approvals don't hide the composer.
 */
export function PermissionRow() {
  const queue = useStore($permissionQueue);
  if (queue.length === 0) return null;
  const current = queue[0];
  const decide = (granted: boolean) => {
    getProtocolClient().sendPermission(current.request_id, granted);
    resolvePermission(current.request_id);
  };
  return (
    <StatusRow
      icon={<ShieldAlert className="h-3 w-3" />}
      tone="warn"
      data-testid="status-permission"
      actions={
        <>
          <button
            className="inline-flex items-center gap-1 rounded px-1.5 py-0.5 text-11 text-text-muted hover:bg-surface-4"
            onClick={() => decide(false)}
          >
            <X className="h-3 w-3" /> deny
          </button>
          <button
            className="inline-flex items-center gap-1 rounded bg-primary px-1.5 py-0.5 text-11 font-medium text-surface-0 hover:bg-primary-hover"
            onClick={() => decide(true)}
          >
            <Check className="h-3 w-3" /> approve
          </button>
        </>
      }
    >
      permission needed \u2014 <span className="font-mono">{current.tool_name}</span>
      {queue.length > 1 && <span className="ml-1 text-text-faint">(+{queue.length - 1})</span>}
    </StatusRow>
  );
}
