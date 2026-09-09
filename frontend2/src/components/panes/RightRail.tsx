"use client";

import { Suspense, useEffect, useState, type ComponentType } from "react";
import { useStore } from "@nanostores/react";
import { $activePane } from "@/lib/stores/panes";
import { cn } from "@/lib/cn";
import { PANES, type PaneMeta } from "./registry";

/**
 * Right rail: 40px icon tab strip + full-height pane surface. Panes are
 * dynamically imported the first time they're activated, then cached.
 */
export function RightRail() {
  const active = useStore($activePane);
  const [loaded, setLoaded] = useState<Record<string, ComponentType<Record<string, unknown>>>>({});

  useEffect(() => {
    const meta = PANES.find((p) => p.id === active);
    if (!meta || loaded[active]) return;
    meta.loader().then((mod) => {
      setLoaded((prev) => ({ ...prev, [active]: mod.default }));
    });
  }, [active, loaded]);

  const ActiveComponent = loaded[active];

  return (
    <div className="flex h-full min-h-0 bg-surface-2">
      <TabStrip active={active} onSelect={(id) => $activePane.set(id)} />
      <div className="min-h-0 min-w-0 flex-1 bg-surface-1">
        <Suspense fallback={<div className="p-3 text-11 text-text-faint">loading\u2026</div>}>
          {ActiveComponent ? (
            <ActiveComponent />
          ) : (
            <div className="p-3 text-11 text-text-faint">loading\u2026</div>
          )}
        </Suspense>
      </div>
    </div>
  );
}

function TabStrip({
  active,
  onSelect,
}: {
  active: PaneMeta["id"];
  onSelect: (id: PaneMeta["id"]) => void;
}) {
  return (
    <nav
      aria-label="Panes"
      className="hairline flex w-10 shrink-0 flex-col items-center gap-1 bg-surface-2 py-2"
    >
      {PANES.map(({ id, label, icon: Icon }) => {
        const isActive = id === active;
        return (
          <button
            key={id}
            type="button"
            onClick={() => onSelect(id)}
            title={label}
            aria-label={label}
            data-testid={`pane-tab-${id}`}
            className={cn(
              "flex h-8 w-8 items-center justify-center rounded",
              "transition-colors duration-fast ease",
              isActive
                ? "bg-surface-4 text-primary"
                : "text-text-muted hover:bg-surface-3 hover:text-text-base",
            )}
          >
            <Icon className="h-4 w-4" />
          </button>
        );
      })}
    </nav>
  );
}
