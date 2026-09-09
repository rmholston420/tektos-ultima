"use client";

import { useStore } from "@nanostores/react";
import { Folder, File as FileIcon } from "lucide-react";
import { $sessionCwd } from "@/lib/stores/session";
import { PanePlaceholder } from "./PanePlaceholder";

/**
 * Files pane: shows the current session CWD and, in later phases,
 * an interactive tree fed by the backend directory_list tool. For
 * Phase 5 we render the CWD and a hint until backend directory
 * events are wired.
 */
export default function FilesPane() {
  const cwd = useStore($sessionCwd);
  if (!cwd) {
    return <PanePlaceholder title="No workspace" hint="Session has no CWD yet." />;
  }
  return (
    <div className="flex h-full flex-col text-11">
      <div className="hairline flex items-center gap-2 px-3 py-2 text-text-muted">
        <Folder className="h-3 w-3 text-primary" />
        <span className="truncate font-mono text-text-base">{cwd}</span>
      </div>
      <div className="flex-1 overflow-auto scrollbar-thin px-3 py-2 text-text-faint">
        <div className="flex items-center gap-1.5">
          <FileIcon className="h-3 w-3" />
          <span>
            Tree loads from directory_list tool events. Ask Tektos to list this
            directory to populate.
          </span>
        </div>
      </div>
    </div>
  );
}
