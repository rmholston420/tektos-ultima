"use client";

import { ConnectionRow } from "./ConnectionRow";
import { ModelRow } from "./ModelRow";
import { ResourceRow } from "./ResourceRow";
import { PlanRow } from "./PlanRow";
import { PermissionRow } from "./PermissionRow";
import { GeneratingRow } from "./GeneratingRow";

/**
 * The status stack that sits above the composer.
 *
 *   1. Connection   — only when not connected
 *   2. Model        — always when connected
 *   3. Generating   — only while an assistant turn is open (live spinner)
 *   4. Resources    — only when a resource.warning is active
 *   5. Plan         — only when a plan.proposed awaits approval
 *   6. Permission   — only when a tool.permission.required awaits reply
 *
 * Rows self-hide when empty so the stack collapses to zero height when
 * nothing is happening.
 */
export function StatusStack() {
  return (
    <div className="flex flex-col" data-testid="status-stack">
      <ConnectionRow />
      <ModelRow />
      <GeneratingRow />
      <ResourceRow />
      <PlanRow />
      <PermissionRow />
    </div>
  );
}
