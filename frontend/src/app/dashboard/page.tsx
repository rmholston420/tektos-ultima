"use client";

import { useMemo, useState } from "react";
import { PANELS, getPanel } from "@/components/panels/registry";
import { cn } from "@/lib/cn";

/**
 * Dashboard: sidebar-groups-by-section + main panel surface. Panels are
 * dynamic-imported through the registry so only the active panel enters
 * the bundle.
 */
export default function DashboardPage() {
  const [activeId, setActiveId] = useState<string>(PANELS[0]?.id ?? "overview");
  const active = getPanel(activeId);

  const grouped = useMemo(() => {
    const map = new Map<string, typeof PANELS>();
    for (const p of PANELS) {
      const list = map.get(p.section) ?? [];
      list.push(p);
      map.set(p.section, list);
    }
    return Array.from(map.entries());
  }, []);

  const Panel = active?.Component;

  return (
    <div className="grid h-full min-h-0 grid-cols-[220px_1fr] bg-surface-1">
      <nav
        aria-label="Dashboard sections"
        className="hairline min-h-0 overflow-auto scrollbar-thin bg-surface-2"
      >
        <div className="px-3 py-3">
          <h1 className="text-11 uppercase tracking-wide text-text-muted">
            Dashboard
          </h1>
        </div>
        <div className="flex flex-col gap-2 pb-4">
          {grouped.map(([section, items]) => (
            <div key={section}>
              <div className="px-3 py-1 text-11 uppercase tracking-wide text-text-faint">
                {section}
              </div>
              <ul>
                {items.map((p) => (
                  <li key={p.id}>
                    <button
                      type="button"
                      onClick={() => setActiveId(p.id)}
                      className={cn(
                        "flex w-full items-center gap-2 px-3 py-1.5 text-11",
                        "transition-colors duration-fast ease",
                        p.id === activeId
                          ? "bg-surface-4 text-text-base"
                          : "text-text-muted hover:bg-surface-3 hover:text-text-base",
                      )}
                      data-testid={`panel-tab-${p.id}`}
                    >
                      {p.label}
                    </button>
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </div>
      </nav>
      <div className="min-h-0 min-w-0 overflow-auto scrollbar-thin bg-surface-1">
        {Panel ? (
          <Panel />
        ) : (
          <div className="p-6 text-11 text-text-faint">panel not found</div>
        )}
      </div>
    </div>
  );
}
