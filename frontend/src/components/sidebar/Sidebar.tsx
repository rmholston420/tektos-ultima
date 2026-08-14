/**
 * Tektos-Ultima v1 — Session Sidebar
 *
 * Left panel showing session list with create, search, rename, tag,
 * fork, archive, and delete actions.
 *
 * Exemplar pattern: Derived state from SessionStore with optimistic UI.
 */

"use client";

import React, { useState, useMemo } from "react";
import { SessionStore, type SessionSnapshot } from "@/lib/session-store";
import {
  PlusIcon,
  MagnifyingGlassIcon,
  FolderIcon,
  FolderOpenIcon as FolderOpenIconAlt,
  ArchiveBoxIcon,
  TrashIcon,
  TagIcon,
  ChatBubbleLeftRightIcon,
  DocumentDuplicateIcon,
} from "@heroicons/react/24/outline";
import {
  FolderOpenIcon,
  ArchiveBoxIcon as ArchiveBoxIconOutline,
  TagIcon as TagSolidIcon,
} from "@heroicons/react/24/solid";

// ---------------------------------------------------------------------------
// Sidebar component
// ---------------------------------------------------------------------------

interface SidebarProps {
  sessionStore: SessionStore;
  activeSessionId: string | null;
  onSelectSession: (sessionId: string) => void;
  onCreateSession: () => void;
  theme: "dark" | "tibet";
  onToggleTheme: () => void;
  collapsed: boolean;
  onToggleCollapsed: () => void;
}

export function Sidebar({
  sessionStore,
  activeSessionId,
  onSelectSession,
  onCreateSession,
  theme,
  onToggleTheme,
  collapsed,
  onToggleCollapsed,
}: SidebarProps) {
  const [searchQuery, setSearchQuery] = useState("");
  const [showArchived, setShowArchived] = useState(false);
  const [renamingId, setRenamingId] = useState<string | null>(null);
  const [renameValue, setRenameValue] = useState("");

  // Derived state
  const sessions = useMemo(() => {
    const all = sessionStore.getAll();
    const visible = showArchived
      ? all
      : all.filter((s) => !s.is_archived);

    if (!searchQuery) return visible;
    return sessionStore.searchSessions(searchQuery);
  }, [sessionStore, searchQuery, showArchived]);

  const activeSessions = useMemo(
    () => sessions.filter((s) => !s.is_archived && s.is_active),
    [sessions]
  );

  const inactiveSessions = useMemo(
    () => sessions.filter((s) => !(s.is_active && !s.is_archived)),
    [sessions]
  );

  // Handlers
  const handleCreate = async () => {
    try {
      const session = await sessionStore.createSession();
      onSelectSession(session.id);
      onCreateSession();
    } catch (err) {
      console.error("Failed to create session:", err);
    }
  };

  const handleRename = async (sessionId: string) => {
    if (!renameValue.trim()) {
      setRenamingId(null);
      return;
    }
    await sessionStore.renameSession(sessionId, renameValue.trim());
    setRenamingId(null);
  };

  const handleTag = async (sessionId: string) => {
    const tag = prompt("Enter tag:");
    if (tag) {
      await sessionStore.tagSession(sessionId, tag);
    }
  };

  const handleFork = async (parent: SessionSnapshot) => {
    try {
      const forked = await sessionStore.forkSession(parent.id);
      onSelectSession(forked.id);
    } catch (err) {
      console.error("Failed to fork session:", err);
    }
  };

  const handleArchive = async (sessionId: string) => {
    await sessionStore.archiveSession(sessionId);
  };

  const handleDelete = async (sessionId: string) => {
    if (confirm("Delete this session? This cannot be undone.")) {
      await sessionStore.deleteSession(sessionId);
    }
  };

  // -----------------------------------------------------------------------
  // Render
  // -----------------------------------------------------------------------

  if (collapsed) {
    return (
      <aside className="w-14 min-w-[3.5rem] bg-bg-2 border-r border-border flex flex-col items-center py-4 gap-3">
        <button
          onClick={handleCreate}
          className="w-9 h-9 rounded-lg flex items-center justify-center
                     bg-accent/10 text-accent hover:bg-accent/20 transition-colors"
          title="New session"
        >
          <PlusIcon className="w-5 h-5" />
        </button>

        <div className="w-7 h-px bg-border" />

        <button
          onClick={() => setShowArchived(!showArchived)}
          className={`w-9 h-9 rounded-lg flex items-center justify-center
                     transition-colors ${
                       showArchived
                         ? "bg-surface-active text-text-primary"
                         : "text-text-secondary hover:text-text-primary hover:bg-surface-hover"
                     }`}
          title={showArchived ? "Hide archived" : "Show archived"}
        >
          {showArchived ? (
            <FolderOpenIcon className="w-5 h-5" />
          ) : (
            <ArchiveBoxIcon className="w-5 h-5" />
          )}
        </button>

        <button
          onClick={onToggleCollapsed}
          className="w-9 h-9 rounded-lg flex items-center justify-center
                     text-text-secondary hover:text-text-primary hover:bg-surface-hover
                     transition-colors"
          title="Expand sidebar"
        >
          <ChatBubbleLeftRightIcon className="w-5 h-5" />
        </button>

        <div className="flex-1" />

        <button
          onClick={onToggleTheme}
          className="w-9 h-9 rounded-lg flex items-center justify-center
                     text-text-secondary hover:text-text-primary hover:bg-surface-hover
                     transition-colors"
          title={`Switch to ${theme === "dark" ? "Tibet" : "Dark"} theme`}
        >
          <svg xmlns="http://www.w3.org/2000/svg" className="w-5 h-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}>
            <circle cx="12" cy="12" r="5" />
            <path d="M12 1v2M12 21v2M4.22 4.22l1.42 1.42M18.36 18.36l1.42 1.42M1 12h2M21 12h2M4.22 19.78l1.42-1.42M18.36 5.64l1.42-1.42" />
          </svg>
        </button>
      </aside>
    );
  }

  return (
    <aside className="shell-sidebar">
      {/* Header */}
      <div className="h-12 min-h-[3rem] border-b border-border flex items-center justify-between px-3">
        <h2 className="text-sm font-semibold text-text-primary">Sessions</h2>
        <button
          onClick={handleCreate}
          className="w-7 h-7 rounded-md flex items-center justify-center
                     bg-accent text-white hover:bg-accent-hover transition-colors"
          title="New session"
        >
          <PlusIcon className="w-4 h-4" />
        </button>
      </div>

      {/* Search */}
      <div className="px-3 py-2">
        <div className="relative">
          <MagnifyingGlassIcon className="absolute left-2.5 top-1/2 -translate-y-1/2 w-4 h-4 text-text-muted" />
          <input
            type="text"
            placeholder="Search sessions..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="w-full bg-bg-3 border border-border rounded-md pl-8 pr-3 py-1.5
                       text-sm placeholder-text-muted
                       focus:border-accent focus:ring-1 focus:ring-accent/20
                       transition-colors"
          />
        </div>
      </div>

      {/* View toggle */}
      <div className="px-3 pb-2 flex items-center gap-2">
        <button
          onClick={() => setShowArchived(false)}
          className={`flex-1 text-xs px-2 py-1 rounded-md transition-colors ${
            !showArchived
              ? "bg-surface-active text-text-primary"
              : "text-text-muted hover:text-text-secondary"
          }`}
        >
          Active
        </button>
        <button
          onClick={() => setShowArchived(true)}
          className={`flex-1 text-xs px-2 py-1 rounded-md transition-colors ${
            showArchived
              ? "bg-surface-active text-text-primary"
              : "text-text-muted hover:text-text-secondary"
          }`}
        >
          Archived
        </button>
      </div>

      <div className="w-full h-px bg-border" />

      {/* Session list */}
      <div className="flex-1 overflow-y-auto px-2 py-2">
        {activeSessions.length > 0 && (
          <div className="mb-3">
            <p className="px-2 mb-1 text-xs font-medium text-text-muted uppercase tracking-wider">
              Active
            </p>
            {activeSessions.map((session) => (
              <SessionItem
                key={session.id}
                session={session}
                isActive={session.id === activeSessionId}
                onRename={setRenamingId}
                renameValue={renamingId === session.id ? renameValue : ""}
                setRenameValue={setRenameValue}
                onRenameSubmit={() => handleRename(session.id)}
                onTag={() => handleTag(session.id)}
                onFork={() => handleFork(session)}
                onArchive={() => handleArchive(session.id)}
                onDelete={() => handleDelete(session.id)}
                onSelect={() => onSelectSession(session.id)}
              />
            ))}
          </div>
        )}

        {inactiveSessions.length > 0 && (
          <div>
            <p className="px-2 mb-1 text-xs font-medium text-text-muted uppercase tracking-wider">
              History
            </p>
            {inactiveSessions.map((session) => (
              <SessionItem
                key={session.id}
                session={session}
                isActive={session.id === activeSessionId}
                onRename={setRenamingId}
                renameValue={renamingId === session.id ? renameValue : ""}
                setRenameValue={setRenameValue}
                onRenameSubmit={() => handleRename(session.id)}
                onTag={() => handleTag(session.id)}
                onFork={() => handleFork(session)}
                onArchive={() => handleArchive(session.id)}
                onDelete={() => handleDelete(session.id)}
                onSelect={() => onSelectSession(session.id)}
              />
            ))}
          </div>
        )}

        {sessions.length === 0 && (
          <div className="px-4 py-8 text-center text-text-muted text-sm">
            {searchQuery ? "No sessions match your search" : "No sessions yet"}
          </div>
        )}
      </div>

      {/* Footer */}
      <div className="h-10 min-h-[2.5rem] border-t border-border flex items-center justify-between px-3">
        <button
          onClick={onToggleTheme}
          className="text-xs text-text-muted hover:text-text-secondary transition-colors"
          title={`Switch to ${theme === "dark" ? "Tibet" : "Dark"} theme`}
        >
          {theme === "dark" ? "Dark Mode" : "Tibet Theme"}
        </button>
        <span className="text-xs text-text-muted">
          {sessions.length} session{sessions.length !== 1 ? "s" : ""}
        </span>
      </div>
    </aside>
  );
}

// ---------------------------------------------------------------------------
// Session item component
// ---------------------------------------------------------------------------

function SessionItem({
  session,
  isActive,
  onRename,
  renameValue,
  setRenameValue,
  onRenameSubmit,
  onTag,
  onFork,
  onArchive,
  onDelete,
  onSelect,
}: {
  session: SessionSnapshot;
  isActive: boolean;
  onRename: (id: string) => void;
  renameValue: string;
  setRenameValue: (v: string) => void;
  onRenameSubmit: () => void;
  onTag: () => void;
  onFork: () => void;
  onArchive: () => void;
  onDelete: () => void;
  onSelect: () => void;
}) {
  const [isHovering, setIsHovering] = useState(false);
  const [showMenu, setShowMenu] = useState(false);

  const statusColor = useMemo(() => {
    if (session.is_archived) return "bg-text-muted";
    if (session.is_failed) return "bg-status-error";
    if (session.is_active) return "bg-status-success";
    return "bg-text-secondary";
  }, [session.is_archived, session.is_failed, session.is_active]);

  const formatDate = (iso: string) => {
    const date = new Date(iso);
    const now = new Date();
    const diffMs = now.getTime() - date.getTime();
    const diffMin = Math.floor(diffMs / 60000);
    const diffHr = Math.floor(diffMin / 60);
    const diffDay = Math.floor(diffHr / 24);

    if (diffMin < 1) return "just now";
    if (diffMin < 60) return `${diffMin}m ago`;
    if (diffHr < 24) return `${diffHr}h ago`;
    return `${diffDay}d ago`;
  };

  if (isActive) {
    return (
      <button
        onMouseEnter={() => setIsHovering(true)}
        onMouseLeave={() => {
          setIsHovering(false);
          setShowMenu(false);
        }}
        onClick={onSelect}
        className="w-full flex items-center gap-2 px-3 py-2 rounded-md
                   bg-surface-active text-text-primary text-sm
                   hover:bg-surface-hover transition-colors group"
      >
        <div className={`w-1.5 h-1.5 rounded-full ${statusColor} flex-shrink-0`} />
        <span className="flex-1 text-left truncate">{session.title}</span>
        <span className="text-xs text-text-muted">{formatDate(session.updated_at)}</span>
      </button>
    );
  }

  return (
    <button
      onMouseEnter={() => setIsHovering(true)}
      onMouseLeave={() => {
        setIsHovering(false);
        setShowMenu(false);
      }}
      onClick={onSelect}
      className="w-full flex items-center gap-2 px-3 py-2 rounded-md
                 text-sm text-text-secondary
                 hover:text-text-primary hover:bg-surface-hover transition-colors group"
    >
      <div className={`w-1.5 h-1.5 rounded-full ${statusColor} flex-shrink-0`} />

      {isHovering || showMenu ? (
        <div className="flex-1 flex items-center gap-1" onClick={(e) => e.stopPropagation()}>
          {session.is_archived ? (
            <ArchiveBoxIcon className="w-3.5 h-3.5 text-text-muted flex-shrink-0" />
          ) : (
            <FolderOpenIcon className="w-3.5 h-3.5 text-text-muted flex-shrink-0" />
          )}
          {renamingId === session.id ? (
            <input
              autoFocus
              value={renameValue}
              onChange={(e) => setRenameValue(e.target.value)}
              onBlur={() => onRenameSubmit()}
              onKeyDown={(e) => {
                if (e.key === "Enter") onRenameSubmit();
                if (e.key === "Escape") onRenameSubmit();
              }}
              className="flex-1 bg-bg-3 border border-border rounded px-1.5 py-0.5
                         text-sm text-text-primary text-left"
            />
          ) : (
            <span className="flex-1 truncate">{session.title}</span>
          )}
        </div>
      ) : (
        <>
          {session.is_archived ? (
            <ArchiveBoxIcon className="w-3.5 h-3.5 text-text-muted flex-shrink-0" />
          ) : (
            <FolderIcon className="w-3.5 h-3.5 text-text-muted flex-shrink-0" />
          )}
          <span className="flex-1 truncate">{session.title}</span>
          <span className="text-xs text-text-muted">{formatDate(session.updated_at)}</span>
        </>
      )}

      {isHovering && (
        <div
          className="flex-shrink-0 flex items-center gap-0.5"
          onClick={(e) => e.stopPropagation()}
        >
          <button
            onClick={() => onTag()}
            className="w-5 h-5 rounded flex items-center justify-center
                       text-text-muted hover:text-text-accent hover:bg-surface-active
                       transition-colors"
            title="Tag"
          >
            <TagIcon className="w-3.5 h-3.5" />
          </button>
          <button
            onClick={() => onFork()}
            className="w-5 h-5 rounded flex items-center justify-center
                       text-text-muted hover:text-text-accent hover:bg-surface-active
                       transition-colors"
            title="Fork"
          >
            <DocumentDuplicateIcon className="w-3.5 h-3.5" />
          </button>
          <button
            onClick={() => onDelete()}
            className="w-5 h-5 rounded flex items-center justify-center
                       text-text-muted hover:text-status-error hover:bg-surface-active
                       transition-colors"
            title="Delete"
          >
            <TrashIcon className="w-3.5 h-3.5" />
          </button>
        </div>
      )}
    </button>
  );
}
