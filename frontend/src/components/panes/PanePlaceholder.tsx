"use client";

import type { ReactNode } from "react";

export function PanePlaceholder({ title, hint }: { title: string; hint?: ReactNode }) {
  return (
    <div className="flex h-full flex-col items-start p-3 text-11 text-text-muted">
      <div className="text-text-base">{title}</div>
      {hint && <div className="mt-1 text-text-faint">{hint}</div>}
    </div>
  );
}
