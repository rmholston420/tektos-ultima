"use client";

import { useStore } from "@nanostores/react";
import * as Dialog from "@radix-ui/react-dialog";
import { $permissionQueue, resolvePermission } from "@/lib/stores/session";
import { getProtocolClient } from "@/lib/hooks/useProtocol";
import { cn } from "@/lib/cn";

/**
 * When the backend emits tool.permission.required, the front of the queue
 * is shown as a blocking modal. Approve/deny fire tool.permission.reply.
 */
export function PermissionModal() {
  const queue = useStore($permissionQueue);
  const current = queue[0] ?? null;

  const decide = (granted: boolean) => {
    if (!current) return;
    getProtocolClient().sendPermission(current.request_id, granted);
    resolvePermission(current.request_id);
  };

  return (
    <Dialog.Root open={current !== null} onOpenChange={(o) => !o && decide(false)}>
      <Dialog.Portal>
        <Dialog.Overlay className="fixed inset-0 z-modal bg-black/60 backdrop-blur-sm" />
        <Dialog.Content
          className={cn(
            "fixed left-1/2 top-1/2 z-modal -translate-x-1/2 -translate-y-1/2",
            "w-[min(480px,90vw)] rounded bg-surface-3 shadow-card hairline",
            "p-4 focus:outline-none",
          )}
        >
          <Dialog.Title className="text-13 font-medium text-text-base">
            Approve tool call
          </Dialog.Title>
          {current && (
            <>
              <div className="mt-2 font-mono text-11 text-text-muted">
                {current.tool_name}
              </div>
              {current.reason && (
                <Dialog.Description className="mt-2 text-12 text-text-muted">
                  {current.reason}
                </Dialog.Description>
              )}
              {current.arguments && (
                <pre className="mt-3 max-h-48 overflow-auto scrollbar-thin rounded bg-surface-1 p-2 font-mono text-10 text-text-muted">
                  {JSON.stringify(current.arguments, null, 2)}
                </pre>
              )}
              <div className="mt-4 flex justify-end gap-2">
                <button
                  onClick={() => decide(false)}
                  className="rounded bg-surface-6 px-3 py-1.5 text-11 text-text-base hover:bg-surface-7"
                >
                  deny
                </button>
                <button
                  onClick={() => decide(true)}
                  className="rounded bg-primary px-3 py-1.5 text-11 font-medium text-surface-0 hover:bg-primary-hover"
                >
                  approve
                </button>
              </div>
            </>
          )}
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}
