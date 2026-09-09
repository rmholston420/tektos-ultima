"use client";

import type { ComponentType } from "react";
import {
  FolderTree,
  FileCode,
  GitCompare,
  TerminalSquare,
  Eye,
  Network,
  ScrollText,
  type LucideIcon,
} from "lucide-react";

export type PaneId =
  | "files"
  | "editor"
  | "diff"
  | "terminal"
  | "preview"
  | "graph"
  | "logs";

export interface PaneMeta {
  id: PaneId;
  label: string;
  icon: LucideIcon;
  loader: () => Promise<{ default: ComponentType<Record<string, unknown>> }>;
}

/**
 * Ordered list of right-rail panes. Loaders are dynamic so heavy deps
 * (Monaco, xterm) don't ship in the initial bundle.
 */
export const PANES: PaneMeta[] = [
  { id: "files",    label: "Files",    icon: FolderTree,      loader: () => import("./FilesPane") },
  { id: "editor",   label: "Editor",   icon: FileCode,        loader: () => import("./EditorPane") },
  { id: "diff",     label: "Diff",     icon: GitCompare,      loader: () => import("./DiffPane") },
  { id: "terminal", label: "Terminal", icon: TerminalSquare,  loader: () => import("./TerminalPane") },
  { id: "preview",  label: "Preview",  icon: Eye,             loader: () => import("./PreviewPane") },
  { id: "graph",    label: "Graph",    icon: Network,         loader: () => import("./GraphPane") },
  { id: "logs",     label: "Logs",     icon: ScrollText,      loader: () => import("./LogsPane") },
];

export function getPane(id: PaneId): PaneMeta | undefined {
  return PANES.find((p) => p.id === id);
}
