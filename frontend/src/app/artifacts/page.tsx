"use client";

import { useStore } from "@nanostores/react";
import { ExternalLink, FileText } from "lucide-react";
import { $artifacts, $artifactOrder } from "@/lib/stores/session";

/**
 * Artifacts destination: cards for every artifact created in the current
 * session. In later phases this will also pull persisted artifacts from
 * the backend so cross-session artifacts are accessible.
 */
export default function ArtifactsPage() {
  const byId = useStore($artifacts);
  const order = useStore($artifactOrder);
  const list = order.map((id) => byId[id]).filter(Boolean);

  return (
    <div className="flex h-full min-h-0 flex-col overflow-auto scrollbar-thin bg-surface-1">
      <div className="hairline flex items-center justify-between px-4 py-3">
        <h1 className="text-14 font-medium text-text-base">Artifacts</h1>
        <span className="text-11 text-text-muted">{list.length} in session</span>
      </div>
      {list.length === 0 ? (
        <div className="flex flex-1 flex-col items-center justify-center gap-2 text-11 text-text-muted">
          <FileText className="h-6 w-6 text-text-faint" />
          <span>No artifacts yet.</span>
          <span className="text-text-faint">
            Ask Tektos to generate an artifact and it will appear here.
          </span>
        </div>
      ) : (
        <ul className="grid grid-cols-1 gap-2 p-4 sm:grid-cols-2 xl:grid-cols-3">
          {list.map((a) => (
            <li
              key={a.id}
              className="hairline rounded-md bg-surface-2 p-3 transition-colors duration-fast ease hover:bg-surface-3"
            >
              <div className="flex items-center gap-2">
                <FileText className="h-3.5 w-3.5 text-primary" />
                <div className="min-w-0 flex-1 truncate text-12 text-text-base">
                  {a.title}
                </div>
                {a.url && (
                  <a
                    href={a.url}
                    target="_blank"
                    rel="noreferrer noopener"
                    className="text-primary hover:text-primary-hover"
                    title="Open"
                  >
                    <ExternalLink className="h-3 w-3" />
                  </a>
                )}
              </div>
              {(a.content_type || a.path) && (
                <div className="mt-1 text-11 text-text-faint">
                  {a.content_type ?? a.path}
                </div>
              )}
              <div className="mt-2 flex items-center gap-2 text-11 text-text-muted">
                <span>v{a.version}</span>
                {typeof a.bytes === "number" && <span>· {a.bytes} B</span>}
                <span>· {a.kind}</span>
              </div>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
