/**
 * SidebarFooter — version + Nous Research link.
 *
 * Mirrors the Hermes Agent desktop GUI sidebar footer.
 */

import { useCallback, useEffect, useState } from "react";

interface StatusResponse {
  version?: string;
}

interface SidebarFooterProps {
  className?: string;
}

export function SidebarFooter({ className }: SidebarFooterProps) {
  const [status, setStatus] = useState<StatusResponse | null>(null);

  useEffect(() => {
    fetch("/api/status")
      .then((r) => r.json())
      .then((data) => setStatus(data))
      .catch(() => {});
  }, []);

  return (
    <div
      className={`flex shrink-0 items-center justify-between gap-2 px-5 py-2.5 border-t border-border/50 ${className || ""}`}
    >
      <span className="font-mono-ui text-xs tabular-nums tracking-[0.08em] text-text-muted lowercase">
        {status?.version != null ? `v${status.version}` : "—"}
      </span>
      <a
        href="https://nousresearch.com"
        target="_blank"
        rel="noopener noreferrer"
        className="font-sans text-xs tracking-[0.12em] text-midground transition-opacity hover:opacity-90"
      >
        Nous Research
      </a>
    </div>
  );
}
