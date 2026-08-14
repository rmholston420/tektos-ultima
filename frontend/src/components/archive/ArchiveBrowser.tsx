/**
 * Tektos-Ultima v1 — Session Archive Browser
 *
 * Full archive browser with search, detail view, resume/fork/rename/tag operations.
 * Shows archived and completed sessions with rich metadata and actions.
 *
 * Exemplar pattern: Search-driven archive with inline actions and modal detail view.
 */

"use client";

import React, { useState, useMemo, useCallback } from "react";
import { SessionStore, type SessionSnapshot } from "@/lib/session-store";
import {
  ArchiveBoxIcon,
  MagnifyingGlassIcon,
  DocumentDuplicateIcon,
  PencilIcon,
  TagIcon,
  TrashIcon,
  ClockIcon,
  ArrowPathIcon,
  EyeIcon,
} from "@heroicons/react/24/outline";

// ---------------------------------------------------------------------------
// Archive Browser props
// ---------------------------------------------------------------------------

interface ArchiveBrowserProps {
  sessionStore: SessionStore;
  activeSessionId: string | null;
  onSelectSession: (sessionId: string) => void;
  onOpenModal: (session: SessionSnapshot) => void;
  collapsed: boolean;
}

export function ArchiveBrowser({
  sessionStore,
  activeSessionId,
  onSelectSession,
  onOpenModal,
  collapsed,
}: ArchiveBrowserProps) {
  const [searchQuery, setSearchQuery] = useState("");
  const [sortBy, setSortBy] = useState<"updated_at" | "created_at" | "title">(
    "updated_at"
  );
  const [sortOrder, setSortOrder] = useState<"asc" | "desc">("desc");
  const [viewMode, setViewMode] = useState<"list" | "grid">("list");

  // Handlers
  const handleSort = (field: "updated_at" | "created_at" | "title") => {
    if (sortBy === field) {
      setSortOrder((prev) => (prev === "asc" ? "desc" : "asc"));
    } else {
      setSortBy(field);
      setSortOrder("desc");
    }
  };

  const handleResume = async (session: SessionSnapshot) => {
    try {
      const response = await fetch("/api/sessions", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          model: session.model,
          cwd: session.cwd,
          resume_session_id: session.id,
        }),
      });
      if (response.ok) {
        const data = await response.json();
        onSelectSession(data.id);
      }
    } catch (err) {
      console.error("Failed to resume session:", err);
    }
  };

  const handleFork = async (session: SessionSnapshot) => {
    try {
      const response = await fetch(`/api/sessions/${session.id}/fork`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ model: session.model }),
      });
      if (response.ok) {
        const data = await response.json();
        onSelectSession(data.id);
      }
    } catch (err) {
      console.error("Failed to fork session:", err);
    }
  };

  const handleRename = async (sessionId: string, newTitle: string) => {
    if (!newTitle.trim()) return;
    await fetch(`/api/sessions/${sessionId}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ title: newTitle }),
    });
  };

  const handleTag = async (sessionId: string, tag: string) => {
    if (!tag.trim()) return;
    await fetch(`/api/sessions/${sessionId}/tag`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ tag }),
    });
  };

  const handleDelete = async (sessionId: string) => {
    if (
      confirm(
        "Delete this session? This cannot be undone.\nAll events will be permanently removed."
      )
    ) {
      await fetch(`/api/sessions/${sessionId}`, {
        method: "DELETE",
      });
    }
  };

  // Filtered and sorted sessions
  const sessions = useMemo(() => {
    const all = sessionStore.getAll();
    // Show all sessions (both archived and active for archive browser)
    let filtered = all;

    // Apply search
    if (searchQuery) {
      const lower = searchQuery.toLowerCase();
      filtered = all.filter(
        (s) =>
          s.title.toLowerCase().includes(lower) ||
          (s.tag ?? "").toLowerCase().includes(lower) ||
          s.model.toLowerCase().includes(lower)
      );
    }

    // Apply sort
    return filtered.sort((a, b) => {
      const multiplier = sortOrder === "asc" ? 1 : -1;
      switch (sortBy) {
        case "title":
          return multiplier * a.title.localeCompare(b.title);
        case "created_at":
          return multiplier * (new Date(a.created_at).getTime() - new Date(b.created_at).getTime());
        case "updated_at":
        default:
          return multiplier * (new Date(a.updated_at).getTime() - new Date(b.updated_at).getTime());
      }
    });
  }, [sessionStore, searchQuery, sortBy, sortOrder]);

  if (collapsed) {
    return (
      <aside className="w-14 min-w-[3.5rem] bg-bg-2 border-r border-border flex flex-col items-center py-4 gap-3">
        <button
          onClick={() => {}} // Would toggle archive view
          className="w-9 h-9 rounded-lg flex items-center justify-center
                     bg-accent/10 text-accent hover:bg-accent/20 transition-colors"
          title="Archive browser"
        >
          <ArchiveBoxIcon className="w-5 h-5" />
        </button>
        <div className="flex-1" />
      </aside>
    );
  }

  return (
    <aside className="shell-sidebar">
      {/* Header */}
      <div className="h-12 min-h-[3rem] border-b border-border flex items-center justify-between px-3">
        <h2 className="text-sm font-semibold text-text-primary">Archive</h2>
        <div className="flex items-center gap-1">
          <button
            onClick={() => setViewMode("list")}
            className={`w-7 h-7 rounded-md flex items-center justify-center transition-colors ${
              viewMode === "list"
                ? "bg-surface-active text-text-primary"
                : "text-text-muted hover:text-text-secondary"
            }`}
            title="List view"
          >
            <svg xmlns="http://www.w3.org/2000/svg" className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M4 6h16M4 12h16M4 18h16" />
            </svg>
          </button>
          <button
            onClick={() => setViewMode("grid")}
            className={`w-7 h-7 rounded-md flex items-center justify-center transition-colors ${
              viewMode === "grid"
                ? "bg-surface-active text-text-primary"
                : "text-text-muted hover:text-text-secondary"
            }`}
            title="Grid view"
          >
            <svg xmlns="http://www.w3.org/2000/svg" className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M3 3h7v7H3zM14 3h7v7h-7zM3 14h7v7H3zM14 14h7v7h-7z" />
            </svg>
          </button>
        </div>
      </div>

      {/* Search + Sort */}
      <div className="px-3 py-2 space-y-2">
        {/* Search */}
        <div className="relative">
          <MagnifyingGlassIcon className="absolute left-2.5 top-1/2 -translate-y-1/2 w-4 h-4 text-text-muted" />
          <input
            type="text"
            placeholder="Search archive..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="w-full bg-bg-3 border border-border rounded-md pl-8 pr-3 py-1.5
                       text-sm placeholder-text-muted
                       focus:border-accent focus:ring-1 focus:ring-accent/20
                       transition-colors"
          />
        </div>

        {/* Sort controls */}
        <div className="flex items-center gap-1">
          <span className="text-xs text-text-muted">Sort:</span>
          <select
            value={sortBy}
            onChange={(e) => handleSort(e.target.value as "updated_at" | "created_at" | "title")}
            className="flex-1 bg-bg-3 border border-border rounded-md px-2 py-1
                       text-xs text-text-secondary focus:border-accent focus:ring-1 focus:ring-accent/20"
          >
            <option value="updated_at">Updated</option>
            <option value="created_at">Created</option>
            <option value="title">Title</option>
          </select>
          <button
            onClick={() => setSortOrder((prev) => (prev === "asc" ? "desc" : "asc"))}
            className="w-7 h-7 rounded-md flex items-center justify-center
                       text-text-muted hover:text-text-secondary hover:bg-surface-active
                       transition-colors"
            title={sortOrder === "asc" ? "Ascending" : "Descending"}
          >
            <ArrowPathIcon className={`w-3.5 h-3.5 transition-transform ${sortOrder === "asc" ? "rotate-180" : ""}`} />
          </button>
        </div>
      </div>

      <div className="w-full h-px bg-border" />

      {/* Session count */}
      <div className="px-3 py-2 flex items-center justify-between">
        <span className="text-xs text-text-muted">
          {sessions.length} session{sessions.length !== 1 ? "s" : ""}
        </span>
      </div>

      {/* Session list */}
      <div className="flex-1 overflow-y-auto px-2 py-2">
        {viewMode === "list" ? (
          <ListMode sessions={sessions} activeSessionId={activeSessionId}
            onSelectSession={onSelectSession}
            onOpenModal={onOpenModal}
            onRename={handleRename}
            onTag={handleTag}
            onFork={handleFork}
            onArchive={handleDelete}
          />
        ) : (
          <GridMode sessions={sessions} activeSessionId={activeSessionId}
            onSelectSession={onSelectSession}
            onOpenModal={onOpenModal}
            onRename={handleRename}
            onTag={handleTag}
            onFork={handleFork}
            onArchive={handleDelete}
          />
        )}

        {sessions.length === 0 && (
          <div className="px-4 py-8 text-center text-text-muted text-sm">
            {searchQuery ? "No sessions match your search" : "No sessions in archive"}
          </div>
        )}
      </div>

      {/* Footer */}
      <div className="h-10 min-h-[2.5rem] border-t border-border flex items-center justify-between px-3">
        <span className="text-xs text-text-muted">Archive Browser</span>
        <span className="text-xs text-text-muted">
          {sessions.filter((s) => s.is_archived).length} archived
        </span>
      </div>
    </aside>
  );
}

// ---------------------------------------------------------------------------
// List mode view
// ---------------------------------------------------------------------------

function ListMode({
  sessions,
  activeSessionId,
  onSelectSession,
  onOpenModal,
  onRename,
  onTag,
  onFork,
  onArchive,
}: {
  sessions: SessionSnapshot[];
  activeSessionId: string | null;
  onSelectSession: (sessionId: string) => void;
  onOpenModal: (session: SessionSnapshot) => void;
  onRename: (sessionId: string, title: string) => void;
  onTag: (sessionId: string, tag: string) => void;
  onFork: (session: SessionSnapshot) => void;
  onArchive: (sessionId: string) => void;
}) {
  const [renamingId, setRenamingId] = useState<string | null>(null);
  const [renameValue, setRenameValue] = useState("");
  const [tagSessionId, setTagSessionId] = useState<string | null>(null);
  const [tagValue, setTagValue] = useState("");

  return (
    <div className="space-y-1">
      {sessions.map((session) => (
        <div
          key={session.id}
          className={`group rounded-md transition-colors ${
            session.id === activeSessionId
              ? "bg-surface-active"
              : "hover:bg-surface-hover"
          }`}
        >
          {/* Main row */}
          <button
            onClick={() => onSelectSession(session.id)}
            className="w-full flex items-center gap-2 px-3 py-2 text-left"
          >
            {/* Status indicator */}
            <div className={`w-1.5 h-1.5 rounded-full flex-shrink-0 ${
              session.is_archived
                ? "bg-text-muted"
                : session.is_failed
                ? "bg-status-error"
                : session.is_active
                ? "bg-status-success"
                : "bg-text-secondary"
            }`} />

            {/* Title */}
            <div className="flex-1 min-w-0">
              {renamingId === session.id ? (
                <input
                  autoFocus
                  value={renameValue}
                  onChange={(e) => setRenameValue(e.target.value)}
                  onBlur={() => onRename(session.id, renameValue)}
                  onKeyDown={(e) => {
                    if (e.key === "Enter") onRename(session.id, renameValue);
                    if (e.key === "Escape") {
                      setRenamingId(null);
                      setRenameValue("");
                    }
                  }}
                  className="w-full bg-bg-3 border border-border rounded px-1.5 py-0.5
                             text-sm text-text-primary"
                />
              ) : (
                <span className="text-sm text-text-secondary truncate block">
                  {session.title}
                </span>
              )}
              {/* Meta line */}
              <div className="flex items-center gap-2 text-xs text-text-muted">
                <span>{session.model}</span>
                {session.tag && (
                  <>
                    <span>•</span>
                    <span className="text-accent/70">{session.tag}</span>
                  </>
                )}
                <span>•</span>
                <span>{formatDate(session.updated_at)}</span>
              </div>
            </div>

            {/* Actions (hover) */}
            <div className="flex items-center gap-0.5 opacity-0 group-hover:opacity-100 transition-opacity">
              {!session.is_archived && (
                <>
                  <button
                    onClick={(e) => {
                      e.stopPropagation();
                      onFork(session);
                    }}
                    className="w-6 h-6 rounded flex items-center justify-center
                               text-text-muted hover:text-accent hover:bg-surface-active
                               transition-colors"
                    title="Fork"
                  >
                    <DocumentDuplicateIcon className="w-3.5 h-3.5" />
                  </button>
                  <button
                    onClick={(e) => {
                      e.stopPropagation();
                      setRenamingId(session.id);
                      setRenameValue(session.title);
                    }}
                    className="w-6 h-6 rounded flex items-center justify-center
                               text-text-muted hover:text-text-accent hover:bg-surface-active
                               transition-colors"
                    title="Rename"
                  >
                    <PencilIcon className="w-3.5 h-3.5" />
                  </button>
                  <button
                    onClick={(e) => {
                      e.stopPropagation();
                      setTagSessionId(session.id);
                    }}
                    className="w-6 h-6 rounded flex items-center justify-center
                               text-text-muted hover:text-text-accent hover:bg-surface-active
                               transition-colors"
                    title="Tag"
                  >
                    <TagIcon className="w-3.5 h-3.5" />
                  </button>
                </>
              )}
              <button
                onClick={(e) => {
                  e.stopPropagation();
                  onOpenModal(session);
                }}
                className="w-6 h-6 rounded flex items-center justify-center
                           text-text-muted hover:text-accent hover:bg-surface-active
                           transition-colors"
                title="View details"
              >
                <EyeIcon className="w-3.5 h-3.5" />
              </button>
              <button
                onClick={(e) => {
                  e.stopPropagation();
                  onArchive(session.id);
                }}
                className="w-6 h-6 rounded flex items-center justify-center
                           text-text-muted hover:text-status-error hover:bg-surface-active
                           transition-colors"
                title="Delete"
              >
                <TrashIcon className="w-3.5 h-3.5" />
              </button>
            </div>
          </button>

          {/* Tag input (when active) */}
          {tagSessionId === session.id && (
            <div className="px-3 pb-2" onClick={(e) => e.stopPropagation()}>
              <div className="flex items-center gap-1">
                <TagIcon className="w-3.5 h-3.5 text-text-muted flex-shrink-0" />
                <input
                  autoFocus
                  value={tagValue}
                  onChange={(e) => setTagValue(e.target.value)}
                  onBlur={() => {
                    if (tagValue.trim()) onTag(session.id, tagValue.trim());
                    setTagSessionId(null);
                    setTagValue("");
                  }}
                  onKeyDown={(e) => {
                    if (e.key === "Enter" && tagValue.trim()) {
                      onTag(session.id, tagValue.trim());
                      setTagSessionId(null);
                      setTagValue("");
                    }
                    if (e.key === "Escape") {
                      setTagSessionId(null);
                      setTagValue("");
                    }
                  }}
                  placeholder="Enter tag..."
                  className="flex-1 bg-bg-3 border border-border rounded px-1.5 py-0.5
                             text-xs text-text-primary"
                />
              </div>
            </div>
          )}
        </div>
      ))}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Grid mode view
// ---------------------------------------------------------------------------

function GridMode({
  sessions,
  activeSessionId,
  onSelectSession,
  onOpenModal,
  onFork,
  onArchive,
}: {
  sessions: SessionSnapshot[];
  activeSessionId: string | null;
  onSelectSession: (sessionId: string) => void;
  onOpenModal: (session: SessionSnapshot) => void;
  onFork: (session: SessionSnapshot) => void;
  onArchive: (sessionId: string) => void;
}) {
  return (
    <div className="grid grid-cols-1 gap-2">
      {sessions.map((session) => (
        <div
          key={session.id}
          className={`rounded-lg border border-border p-3 transition-all ${
            session.id === activeSessionId
              ? "bg-surface-active border-accent/30"
              : "bg-bg-3 hover:bg-bg-2 hover:border-border/80"
          }`}
        >
          <button
            onClick={() => onSelectSession(session.id)}
            className="w-full text-left"
          >
            <div className="flex items-center justify-between mb-1">
              <h3 className="text-sm font-medium text-text-primary truncate">
                {session.title}
              </h3>
              <div className={`w-2 h-2 rounded-full flex-shrink-0 ${
                session.is_archived
                  ? "bg-text-muted"
                  : session.is_failed
                  ? "bg-status-error"
                  : session.is_active
                  ? "bg-status-success"
                  : "bg-text-secondary"
              }`} />
            </div>
            <div className="flex items-center gap-2 text-xs text-text-muted">
              <ClockIcon className="w-3.5 h-3.5" />
              <span>{formatDate(session.updated_at)}</span>
            </div>
            <div className="flex items-center gap-1 mt-1">
              <span className="text-xs text-text-muted bg-bg-2 px-1.5 py-0.5 rounded">
                {session.model}
              </span>
              {session.tag && (
                <span className="text-xs text-accent/70 bg-accent/10 px-1.5 py-0.5 rounded">
                  {session.tag}
                </span>
              )}
            </div>
          </button>

          {/* Actions */}
          <div className="flex items-center gap-1 mt-2 pt-2 border-t border-border/50">
            {!session.is_archived && (
              <button
                onClick={(e) => {
                  e.stopPropagation();
                  onFork(session);
                }}
                className="flex-1 flex items-center justify-center gap-1 px-2 py-1 rounded
                           text-xs text-text-secondary hover:text-accent hover:bg-accent/10
                           transition-colors"
              >
                <DocumentDuplicateIcon className="w-3.5 h-3.5" />
                Fork
              </button>
            )}
            <button
              onClick={(e) => {
                e.stopPropagation();
                onOpenModal(session);
              }}
              className="flex-1 flex items-center justify-center gap-1 px-2 py-1 rounded
                         text-xs text-text-secondary hover:text-accent hover:bg-accent/10
                         transition-colors"
            >
              <EyeIcon className="w-3.5 h-3.5" />
              View
            </button>
            <button
              onClick={(e) => {
                e.stopPropagation();
                onArchive(session.id);
              }}
              className="flex items-center justify-center px-2 py-1 rounded
                         text-text-muted hover:text-status-error hover:bg-status-error/10
                         transition-colors"
            >
              <TrashIcon className="w-3.5 h-3.5" />
            </button>
          </div>
        </div>
      ))}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function formatDate(iso: string): string {
  const date = new Date(iso);
  const now = new Date();
  const diffMs = now.getTime() - date.getTime();
  const diffMin = Math.floor(diffMs / 60000);
  const diffHr = Math.floor(diffMin / 60);
  const diffDay = Math.floor(diffHr / 24);

  if (diffMin < 1) return "just now";
  if (diffMin < 60) return `${diffMin}m ago`;
  if (diffHr < 24) return `${diffHr}h ago`;
  if (diffDay < 7) return `${diffDay}d ago`;
  if (diffDay < 30) return `${Math.floor(diffDay / 7)}w ago`;
  return date.toLocaleDateString();
}
