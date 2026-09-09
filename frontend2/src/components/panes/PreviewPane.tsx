"use client";

import { useStore } from "@nanostores/react";
import { $artifacts, $artifactOrder } from "@/lib/stores/session";
import { PanePlaceholder } from "./PanePlaceholder";
import { ExternalLink } from "lucide-react";

/**
 * Preview pane: iframe-embed the latest artifact if it has a URL, or
 * show its metadata. No sandbox escape: iframe is sandboxed with
 * allow-scripts + allow-same-origin OFF; we allow allow-scripts only
 * for artifacts explicitly typed as text/html on the same-origin dev
 * server or on the backend origin.
 */
export default function PreviewPane() {
  const byId = useStore($artifacts);
  const order = useStore($artifactOrder);
  const latest = order.length ? byId[order[order.length - 1]] : null;

  if (!latest) {
    return (
      <PanePlaceholder title="Preview" hint="Latest artifact preview appears here." />
    );
  }

  const isHtml = latest.content_type?.startsWith("text/html") || latest.url;

  return (
    <div className="flex h-full flex-col text-11">
      <div className="hairline flex items-center gap-2 px-3 py-1.5 text-text-muted">
        <span className="truncate text-text-base">{latest.title}</span>
        {latest.url && (
          <a
            href={latest.url}
            target="_blank"
            rel="noreferrer noopener"
            className="ml-auto inline-flex items-center gap-1 text-primary hover:text-primary-hover"
          >
            open <ExternalLink className="h-3 w-3" />
          </a>
        )}
      </div>
      <div className="min-h-0 flex-1 bg-surface-0">
        {isHtml && latest.url ? (
          <iframe
            title={latest.title}
            src={latest.url}
            className="h-full w-full border-0"
            sandbox="allow-scripts allow-same-origin"
          />
        ) : (
          <pre className="max-h-full overflow-auto scrollbar-thin p-3 font-mono text-11 text-text-base">
            {JSON.stringify(latest, null, 2)}
          </pre>
        )}
      </div>
    </div>
  );
}
