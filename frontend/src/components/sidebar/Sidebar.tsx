/**
 * Tektos-Ultima v1 — Session Sidebar with Theme Selector
 *
 * Left panel: session list, theme switcher, navigation between Chat
 * and Dashboard. Three themes: Abyss (dark), Temple (Tibetan), Clarity
 * (minimalist). Organic design with breathing animations.
 */

"use client";

import React, { useState, useMemo, useEffect } from "react";
import { SessionStore, type SessionSnapshot } from "@/lib/session-store";
import { themeStore, type ThemeName, THEMES } from "@/lib/theme-store";
import {
  PlusIcon,
  MagnifyingGlassIcon,
  FolderIcon,
  FolderOpenIcon as FolderOpenIconAlt,
  ArchiveBoxIcon,
  TrashIcon,
  TagIcon,
  DocumentDuplicateIcon,
  ChevronDoubleLeftIcon,
  ChevronDoubleRightIcon,
  HomeIcon,
  ChartBarIcon,
} from "@heroicons/react/24/outline";
import { FolderOpenIcon, ArchiveBoxIcon as ArchiveBoxOutline, TagIcon as TagSolid } from "@heroicons/react/24/solid";
import { ArchiveBrowser } from "@/components/archive/ArchiveBrowser";

// ─── Props ─────────────────────────────────────────────────────

interface SidebarProps {
  sessionStore: SessionStore;
  activeSessionId: string | null;
  onSelectSession: (sessionId: string) => void;
  onCreateSession: () => void;
  theme: ThemeName;
  collapsed: boolean;
  onToggleCollapsed: () => void;
  activePage: "chat" | "dashboard";
  onNavigate: (page: "chat" | "dashboard") => void;
}

// ─── Sidebar ──────────────────────────────────────────────────

export function Sidebar({
  sessionStore,
  activeSessionId,
  onSelectSession,
  onCreateSession,
  theme,
  collapsed,
  onToggleCollapsed,
  activePage,
  onNavigate,
}: SidebarProps) {
  const [searchQuery, setSearchQuery] = useState("");
  const [showArchive, setShowArchive] = useState(false);
  const [renamingId, setRenamingId] = useState<string | null>(null);
  const [renameValue, setRenameValue] = useState("");

  // Derived state
  const sessions = useMemo(() => {
    const all = sessionStore.getAll();
    const visible = showArchive ? all : all.filter((s) => !s.is_archived);
    if (!searchQuery) return visible;
    return sessionStore.searchSessions(searchQuery);
  }, [sessionStore, searchQuery, showArchive]);

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

  // Theme cycling
  const cycleTheme = () => {
    const names: ThemeName[] = ["abyss", "temple", "clarity"];
    const currentIdx = names.indexOf(theme);
    const nextTheme = names[(currentIdx + 1) % names.length];
    themeStore.set(nextTheme);
  };

  // ── Collapsed state ──

  if (collapsed) {
    return (
      <aside className="w-14 min-w-[3.5rem] bg-surface border-r border-border flex flex-col items-center py-4 gap-3">
        {/* New session */}
        <button
          onClick={handleCreate}
          className="w-9 h-9 rounded-xl flex items-center justify-center bg-accent/10 text-accent hover:bg-accent/20 transition-all hover:scale-105"
          title="New session"
        >
          <PlusIcon className="w-5 h-5" />
        </button>

        {/* Nav */}
        <div className="flex flex-col gap-1 w-full px-1.5">
          <button
            onClick={() => onNavigate("chat")}
            className={`w-9 h-9 rounded-lg flex items-center justify-center transition-all ${
              activePage === "chat"
                ? "bg-accent/20 text-accent"
                : "text-text-muted hover:text-text-primary hover:bg-surface-hover"
            }`}
            title="Chat"
          >
            <HomeIcon className="w-4 h-4" />
          </button>
          <button
            onClick={() => onNavigate("dashboard")}
            className={`w-9 h-9 rounded-lg flex items-center justify-center transition-all ${
              activePage === "dashboard"
                ? "bg-accent/20 text-accent"
                : "text-text-muted hover:text-text-primary hover:bg-surface-hover"
            }`}
            title="Dashboard"
          >
            <ChartBarIcon className="w-4 h-4" />
          </button>
        </div>

        <div className="w-7 h-px bg-border" />

        {/* Archive toggle */}
        <button
          onClick={() => setShowArchive(!showArchive)}
          className={`w-9 h-9 rounded-lg flex items-center justify-center transition-all ${
            showArchive ? "bg-surface-active text-text-primary" : "text-text-muted hover:text-text-primary hover:bg-surface-hover"
          }`}
          title={showArchive ? "Hide archive" : "Show archive"}
        >
          {showArchive ? <FolderOpenIconAlt className="w-5 h-5" /> : <ArchiveBoxIcon className="w-5 h-5" />}
        </button>

        <div className="flex-1" />

        {/* Theme switcher */}
        <button
          onClick={cycleTheme}
          className="w-9 h-9 rounded-lg flex items-center justify-center text-text-muted hover:text-text-primary hover:bg-surface-hover transition-all"
          title={`Switch theme (current: ${THEMES[theme].label})`}
        >
          <span className="text-sm">{THEMES[theme].icon}</span>
        </button>

        {/* Collapse */}
        <button
          onClick={onToggleCollapsed}
          className="w-9 h-9 rounded-lg flex items-center justify-center text-text-muted hover:text-text-primary hover:bg-surface-hover transition-all"
          title="Expand sidebar"
        >
          <ChevronDoubleRightIcon className="w-4 h-4" />
        </button>
      </aside>
    );
  }

  // ── Expanded state ──

  return (
    <aside className="shell-sidebar">
      {/* Header */}
      <div className="h-12 min-h-[3rem] border-b border-border flex items-center justify-between px-3">
        <h2 className="text-sm font-semibold text-text-primary">Sessions</h2>
        <button
          onClick={handleCreate}
          className="w-7 h-7 rounded-lg flex items-center justify-center bg-accent text-white hover:bg-accent-hover transition-all hover:scale-105"
          title="New session"
        >
          <PlusIcon className="w-4 h-4" />
        </button>
      </div>

      {/* Nav tabs */}
      <div className="px-3 pt-3 pb-2">
        <div className="flex items-center gap-1 bg-bg-3 rounded-lg p-0.5">
          <button
            onClick={() => onNavigate("chat")}
            className={`flex-1 flex items-center justify-center gap-1.5 px-2 py-1.5 text-xs font-medium rounded-md transition-all ${
              activePage === "chat"
                ? "bg-accent text-white shadow-sm"
                : "text-text-muted hover:text-text-primary"
            }`}
          >
            <HomeIcon className="w-3.5 h-3.5" />
            Chat
          </button>
          <button
            onClick={() => onNavigate("dashboard")}
            className={`flex-1 flex items-center justify-center gap-1.5 px-2 py-1.5 text-xs font-medium rounded-md transition-all ${
              activePage === "dashboard"
                ? "bg-accent text-white shadow-sm"
                : "text-text-muted hover:text-text-primary"
            }`}
          >
            <ChartBarIcon className="w-3.5 h-3.5" />
            Dash
          </button>
        </div>
      </div>

      {/* Search */}
      <div className="px-3 py-2">
        <div className="relative">
          <MagnifyingGlassIcon className="absolute left-2.5 top-1/2 -translate-y-1/2 w-4 h-4 text-text-muted" />
          <input
            type="text"
            placeholder="Search..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="w-full bg-bg-3 border border-border rounded-lg pl-8 pr-3 py-2 text-sm placeholder-text-muted focus:border-accent focus:ring-1 focus:ring-accent/20 transition-all"
          />
        </div>
      </div>

      {/* View toggle */}
      <div className="px-3 pb-2 flex items-center gap-2">
        <button
          onClick={() => setShowArchive(false)}
          className={`flex-1 text-xs px-2 py-1.5 rounded-lg transition-all ${
            !showArchive ? "bg-surface-active text-text-primary" : "text-text-muted hover:text-text-secondary"
          }`}
        >
          Active
        </button>
        <button
          onClick={() => setShowArchive(true)}
          className={`flex-1 text-xs px-2 py-1.5 rounded-lg transition-all ${
            showArchive ? "bg-surface-active text-text-primary" : "text-text-muted hover:text-text-secondary"
          }`}
        >
          Archive
        </button>
      </div>

      <div className="w-full h-px bg-border" />

      {/* Session list or Archive */}
      {!showArchive ? (
        <div className="flex-1 overflow-y-auto px-2 py-2">
          {activeSessions.length > 0 && (
            <div className="mb-3">
              <p className="px-2 mb-1.5 text-xs font-medium text-text-muted uppercase tracking-wider">Active</p>
              {activeSessions.map((session) => (
                <SessionItem
                  key={session.id}
                  session={session}
                  isActive={session.id === activeSessionId}
                  renamingId={renamingId}
                  renameValue={renameValue}
                  setRenameValue={setRenameValue}
                  onRenameSubmit={handleRename}
                  onTag={handleTag}
                  onFork={handleFork}
                  onArchive={() => handleArchive(session.id)}
                  onDelete={() => handleDelete(session.id)}
                  onSelect={() => onSelectSession(session.id)}
                />
              ))}
            </div>
          )}

          {inactiveSessions.length > 0 && (
            <div>
              <p className="px-2 mb-1.5 text-xs font-medium text-text-muted uppercase tracking-wider">History</p>
              {inactiveSessions.map((session) => (
                <SessionItem
                  key={session.id}
                  session={session}
                  isActive={session.id === activeSessionId}
                  renamingId={renamingId}
                  renameValue={renameValue}
                  setRenameValue={setRenameValue}
                  onRenameSubmit={handleRename}
                  onTag={handleTag}
                  onFork={handleFork}
                  onArchive={() => handleArchive(session.id)}
                  onDelete={() => handleDelete(session.id)}
                  onSelect={() => onSelectSession(session.id)}
                />
              ))}
            </div>
          )}

          {sessions.length === 0 && (
            <div className="px-4 py-8 text-center text-text-muted text-sm">
              {searchQuery ? "No sessions match" : "No sessions yet"}
            </div>
          )}
        </div>
      ) : (
        <div className="flex-1 overflow-y-auto">
          <ArchiveBrowser
            sessionStore={sessionStore}
            activeSessionId={activeSessionId}
            onSelectSession={onSelectSession}
            collapsed={false}
          />
        </div>
      )}

      {/* Footer */}
      <div className="h-12 min-h-[3rem] border-t border-border px-3">
        {/* Theme selector */}
        <div className="flex items-center gap-1.5 mb-2">
          <span className="text-xs text-text-muted">Theme:</span>
          {(["abyss", "temple", "clarity"] as ThemeName[]).map((t) => (
            <button
              key={t}
              onClick={() => themeStore.set(t)}
              className={`flex-1 flex items-center justify-center gap-1 px-2 py-1 text-xs rounded-md transition-all ${
                theme === t
                  ? "bg-accent text-white shadow-sm"
                  : "text-text-muted hover:text-text-primary hover:bg-surface-hover"
              }`}
              title={THEMES[t].description}
            >
              <span className="text-xs">{THEMES[t].icon}</span>
              <span className="truncate">{THEMES[t].label}</span>
            </button>
          ))}
        </div>

        <div className="flex items-center justify-between">
          <span className="text-xs text-text-muted">{sessions.length} session{sessions.length !== 1 ? "s" : ""}</span>
          <button
            onClick={onToggleCollapsed}
            className="w-7 h-7 rounded-lg flex items-center justify-center text-text-muted hover:text-text-primary hover:bg-surface-hover transition-all"
            title="Collapse sidebar"
          >
            <ChevronDoubleLeftIcon className="w-4 h-4" />
          </button>
        </div>
      </div>
    </aside>
  );
}

// ─── Session Item ──────────────────────────────────────────────

function SessionItem({
  session,
  isActive,
  renamingId,
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
  renamingId: string | null;
  renameValue: string;
  setRenameValue: (v: string) => void;
  onRenameSubmit: (id: string) => void;
  onTag: (id: string) => void;
  onFork: (session: SessionSnapshot) => void;
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
        onMouseLeave={() => { setIsHovering(false); setShowMenu(false); }}
        onClick={onSelect}
        className="w-full flex items-center gap-2 px-3 py-2 rounded-xl bg-surface-active text-text-primary text-sm hover:bg-surface-hover transition-all group"
      >
        <div className={`w-1.5 h-1.5 rounded-full ${statusColor} flex-shrink-0 animate-pulse`} />
        <span className="flex-1 text-left truncate">{session.title}</span>
        <span className="text-xs text-text-muted">{formatDate(session.updated_at)}</span>
      </button>
    );
  }

  return (
    <button
      onMouseEnter={() => setIsHovering(true)}
      onMouseLeave={() => { setIsHovering(false); setShowMenu(false); }}
      onClick={onSelect}
      className="w-full flex items-center gap-2 px-3 py-2 rounded-xl text-sm text-text-secondary hover:text-text-primary hover:bg-surface-hover transition-all group"
    >
      <div className={`w-1.5 h-1.5 rounded-full ${statusColor} flex-shrink-0`} />

      {isHovering || showMenu ? (
        <div className="flex-1 flex items-center gap-1" onClick={(e) => e.stopPropagation()}>
          {session.is_archived ? (
            <ArchiveBoxOutline className="w-3.5 h-3.5 text-text-muted flex-shrink-0" />
          ) : (
            <FolderOpenIcon className="w-3.5 h-3.5 text-text-muted flex-shrink-0" />
          )}
          {renamingId === session.id ? (
            <input
              autoFocus
              value={renameValue}
              onChange={(e) => setRenameValue(e.target.value)}
              onBlur={() => onRenameSubmit(session.id)}
              onKeyDown={(e) => { if (e.key === "Enter") onRenameSubmit(session.id); if (e.key === "Escape") onRenameSubmit(session.id); }}
              className="flex-1 bg-bg-3 border border-border rounded-md px-1.5 py-0.5 text-sm text-text-primary text-left"
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
        <div className="flex-shrink-0 flex items-center gap-0.5" onClick={(e) => e.stopPropagation()}>
          <button onClick={() => onTag(session.id)} className="w-5 h-5 rounded-md flex items-center justify-center text-text-muted hover:text-accent hover:bg-surface-active transition-all" title="Tag">
            <TagIcon className="w-3.5 h-3.5" />
          </button>
          <button onClick={() => onFork(session)} className="w-5 h-5 rounded-md flex items-center justify-center text-text-muted hover:text-accent hover:bg-surface-active transition-all" title="Fork">
            <DocumentDuplicateIcon className="w-3.5 h-3.5" />
          </button>
          <button onClick={() => onDelete()} className="w-5 h-5 rounded-md flex items-center justify-center text-text-muted hover:text-status-error hover:bg-surface-active transition-all" title="Delete">
            <TrashIcon className="w-3.5 h-3.5" />
          </button>
        </div>
      )}
    </button>
  );
}
