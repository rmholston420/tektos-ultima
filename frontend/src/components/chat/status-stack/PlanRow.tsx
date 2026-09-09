"use client";

import { useStore } from "@nanostores/react";
import { ListChecks, Check, X } from "lucide-react";
import { $planProposals } from "@/lib/stores/session";
import { getProtocolClient } from "@/lib/hooks/useProtocol";
import { StatusRow } from "./StatusRow";

export function PlanRow() {
  const proposals = useStore($planProposals);
  const pending = Object.values(proposals).find((p) => !p.approved);
  if (!pending) return null;

  const decide = (approved: boolean) => {
    getProtocolClient().sendPlanDecision(pending.plan_id, approved);
  };

  return (
    <StatusRow
      icon={<ListChecks className="h-3 w-3" />}
      tone="agent"
      data-testid="status-plan"
      actions={
        <>
          <button
            className="inline-flex items-center gap-1 rounded px-1.5 py-0.5 text-11 text-text-muted hover:bg-surface-4"
            onClick={() => decide(false)}
          >
            <X className="h-3 w-3" /> reject
          </button>
          <button
            className="inline-flex items-center gap-1 rounded bg-agent px-1.5 py-0.5 text-11 font-medium text-surface-0 hover:bg-agent-hover"
            onClick={() => decide(true)}
          >
            <Check className="h-3 w-3" /> approve
          </button>
        </>
      }
    >
      plan proposed — {pending.steps.length} step{pending.steps.length === 1 ? "" : "s"}
    </StatusRow>
  );
}
