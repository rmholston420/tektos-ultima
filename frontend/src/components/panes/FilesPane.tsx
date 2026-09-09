"use client";

import { useEffect, useMemo, useState } from "react";
import { useStore } from "@nanostores/react";
import { Folder, FolderOpen, File as FileIcon, ChevronRight, ChevronDown, RefreshCw } from "lucide-react";
import { $sessionCwd } from "@/lib/stores/session";
import { PanePlaceholder } from "./PanePlaceholder";

interface DirEntry {
  name: string;
  path: string;
  parent: string;
  type: "file" | "dir";
  size?: number | null;
  mtime?: number | null;
  depth: number;
}

interface DirResponse {
  path: string;
  depth: number;
  count: number;
  entries: DirEntry[];
  error?: string;
}

async function fetchDir(path: string, depth = 1): Promise<DirResponse | null> {
  try {
    const params = new URLSearchParams({ path, depth: String(depth) });
    const res = await fetch(`/api/directory_list?${params}`);
    if (!res.ok) return null;
    return (await res.json()) as DirResponse;
  } catch {
    return null;
  }
}

function humanSize(n?: number | null): string {
  if (n === null || n === undefined) return "";
  if (n < 1024) return `${n} B`;
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(1)} KB`;
  if (n < 1024 * 1024 * 1024) return `${(n / 1024 / 1024).toFixed(1)} MB`;
  return `${(n / 1024 / 1024 / 1024).toFixed(1)} GB`;
}

/**
 * Files pane: live directory tree served by /api/directory_list. Root is the
 * session CWD; directories are expandable/collapsible with lazy loading on
 * first expand.
 */
export default function FilesPane() {
  const cwd = useStore($sessionCwd);
  const rootPath = cwd || "/";
  const [rootEntries, setRootEntries] = useState<DirEntry[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [expanded, setExpanded] = useState<Record<string, DirEntry[]>>({});
  const [loadingPath, setLoadingPath] = useState<string | null>(null);
  const [reloadKey, setReloadKey] = useState(0);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      setError(null);
      const res = await fetchDir(rootPath, 1);
      if (cancelled) return;
      if (!res) {
        setError("Failed to load directory");
        setRootEntries([]);
      } else if (res.error) {
        setError(res.error);
        setRootEntries([]);
      } else {
        setRootEntries(res.entries);
        setExpanded({});
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [rootPath, reloadKey]);

  const toggle = async (entry: DirEntry) => {
    if (entry.type !== "dir") return;
    if (expanded[entry.path]) {
      const next = { ...expanded };
      delete next[entry.path];
      setExpanded(next);
      return;
    }
    setLoadingPath(entry.path);
    const res = await fetchDir(entry.path, 1);
    setLoadingPath(null);
    if (res && !res.error) {
      setExpanded((prev) => ({ ...prev, [entry.path]: res.entries }));
    }
  };

  const rows = useMemo(() => {
    const out: DirEntry[] = [];
    const visit = (entries: DirEntry[]) => {
      for (const e of entries) {
        out.push(e);
        if (e.type === "dir" && expanded[e.path]) {
          visit(expanded[e.path]);
        }
      }
    };
    if (rootEntries) visit(rootEntries);
    return out;
  }, [rootEntries, expanded]);

  if (!cwd) {
    return <PanePlaceholder title="No workspace" hint="Session has no CWD yet." />;
  }

  return (
    <div className="flex h-full flex-col text-11">
      <div className="hairline flex items-center gap-2 px-3 py-2 text-text-muted">
        <Folder className="h-3 w-3 text-primary" />
        <span className="truncate font-mono text-text-base flex-1">{rootPath}</span>
        <button
          onClick={() => setReloadKey((k) => k + 1)}
          className="rounded p-1 hover:bg-surface-6 text-text-muted"
          title="Reload"
        >
          <RefreshCw className="h-3 w-3" />
        </button>
      </div>
      {error && (
        <div className="px-3 py-2 text-11 text-red-400">
          {error}
        </div>
      )}
      <div className="flex-1 overflow-auto scrollbar-thin py-1">
        {rootEntries === null && !error && (
          <div className="px-3 py-2 text-text-faint">Loading…</div>
        )}
        {rows.map((e) => {
          const isDir = e.type === "dir";
          const isOpen = isDir && expanded[e.path] !== undefined;
          const indent = 8 + (e.depth - 1) * 12;
          return (
            <button
              key={e.path}
              onClick={() => (isDir ? toggle(e) : null)}
              className="flex w-full items-center gap-1.5 px-3 py-0.5 text-left hover:bg-surface-6 text-text-base"
              style={{ paddingLeft: indent }}
              disabled={!isDir}
            >
              {isDir ? (
                isOpen ? (
                  <ChevronDown className="h-3 w-3 flex-shrink-0 text-text-muted" />
                ) : (
                  <ChevronRight className="h-3 w-3 flex-shrink-0 text-text-muted" />
                )
              ) : (
                <span className="w-3 flex-shrink-0" />
              )}
              {isDir ? (
                isOpen ? (
                  <FolderOpen className="h-3 w-3 flex-shrink-0 text-primary" />
                ) : (
                  <Folder className="h-3 w-3 flex-shrink-0 text-primary" />
                )
              ) : (
                <FileIcon className="h-3 w-3 flex-shrink-0 text-text-muted" />
              )}
              <span className="truncate font-mono flex-1">{e.name}</span>
              {!isDir && (
                <span className="text-text-faint text-10 pr-2">{humanSize(e.size)}</span>
              )}
              {isDir && loadingPath === e.path && (
                <span className="text-text-faint text-10 pr-2">…</span>
              )}
            </button>
          );
        })}
      </div>
    </div>
  );
}
