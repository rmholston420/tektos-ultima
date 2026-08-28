/**
 * ChatSessionList — ChatGPT-style session switcher.
 *
 * Mirrors the Hermes Agent desktop GUI session list:
 *   - "New chat" button
 *   - Session rows with title, time-ago, message count
 *   - Active session highlighting
 *   - Error handling with retry
 */

import {
  ExclamationTriangleIcon,
  PlusIcon,
  ArrowPathIcon,
} from "@heroicons/react/24/outline";
import { useCallback, useEffect, useRef, useState } from "react";
import type { SessionSnapshot } from "@/lib/session-store";

interface ChatSessionListProps {
  activeSessionId: string | null;
  profile?: string;
  className?: string;
  onPicked?: (id: string) => void;
  onNewChat?: () => void;
}

function rowLabel(session: SessionSnapshot, untitled: string): string {
  const title = session.title?.trim();
  if (title && title !== "Untitled") return title;
  return untitled;
}

function timeAgo(dateStr: string | undefined): string {
  if (!dateStr) return "";
  const date = new Date(dateStr);
  const now = new Date();
  const diffMs = now.getTime() - date.getTime();
  const diffMin = Math.floor(diffMs / 60000);
  const diffHr = Math.floor(diffMin / 60);
  const diffDay = Math.floor(diffHr / 24);

  if (diffMin < 1) return "just now";
  if (diffMin < 60) return `${diffMin}m ago`;
  if (diffHr < 24) return `${diffHr}h ago`;
  return `${diffDay}d ago`;
}

export function ChatSessionList({
  activeSessionId,
  className,
  onPicked,
  onNewChat,
}: ChatSessionListProps) {
  const [sessions, setSessions] = useState<SessionSnapshot[] | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [reloadNonce, setReloadNonce] = useState(0);

  const reqRef = useRef(0);

  const load = useCallback(() => {
    const myReq = ++reqRef.current;
    setLoading(true);
    setError(null);
    fetch("/api/sessions?limit=30&archived=false")
      .then((r) => r.json())
      .then((data) => {
        if (reqRef.current !== myReq) return;
        const raw = Array.isArray(data) ? data : (data.sessions ?? []);
        setSessions(raw);
      })
      .catch((e: Error) => {
        if (reqRef.current !== myReq) return;
        setError(e.message || "failed to load sessions");
      })
      .finally(() => {
        if (reqRef.current === myReq) setLoading(false);
      });
  }, []);

  useEffect(() => {
    load();
  }, [load, reloadNonce]);

  const reload = useCallback(() => setReloadNonce((n) => n + 1), []);

  const pick = useCallback(
    (id: string) => {
      onPicked?.(id);
    },
    [onPicked],
  );

  const startNew = useCallback(() => {
    onNewChat?.();
  }, [onNewChat]);

  const content = (() => {
    if (loading && sessions === null) {
      return (
        <div className="flex items-center justify-center gap-2 px-2 py-6 text-xs text-text-muted">
          <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-text-muted" />
          Loading…
        </div>
      );
    }
    if (error) {
      return (
        <div className="flex flex-col items-start gap-2 px-2 py-4 text-xs">
          <div className="flex items-start gap-2 text-destructive">
            <ExclamationTriangleIcon className="mt-0.5 h-3.5 w-3.5 shrink-0" />
            <span className="break-words">{error}</span>
          </div>
          <button
            onClick={reload}
            className="px-3 py-1.5 bg-accent text-white rounded-lg text-xs hover:bg-accent-hover transition-colors"
          >
            Retry
          </button>
        </div>
      );
    }
    if (!sessions || sessions.length === 0) {
      return (
        <div className="px-2 py-6 text-center text-xs text-text-muted">
          No sessions yet
        </div>
      );
    }
    return (
      <div className="flex flex-col gap-0.5">
        {sessions.map((s) => {
          const isActive = s.id === activeSessionId;
          return (
            <button
              key={s.id}
              onClick={() => pick(s.id)}
              className={`flex-col items-start gap-0.5 rounded px-2 py-1.5 text-left transition-colors normal-case tracking-normal ${
                isActive
                  ? "bg-accent/10 text-text-primary border-l-2 border-accent"
                  : "text-text-muted hover:bg-surface-hover hover:text-text-primary"
              }`}
            >
              <span className="w-full truncate text-sm font-medium">
                {rowLabel(s, "Untitled")}
              </span>
              <span className="flex w-full items-center gap-1.5 text-[0.6875rem] text-text-muted">
                <span>{timeAgo(s.updated_at)}</span>
                {s.current_seq > 0 && (
                  <>
                    <span aria-hidden>·</span>
                    <span>{s.current_seq} msgs</span>
                  </>
                )}
              </span>
            </button>
          );
        })}
      </div>
    );
  })();

  return (
    <aside className={`flex h-full w-full min-w-0 shrink-0 flex-col overflow-hidden ${className || ""}`}>
      <div className="flex items-center justify-between gap-2 px-2 pb-2">
        <span className="text-xs tracking-wider text-text-muted uppercase">
          Sessions
        </span>
        <button
          onClick={reload}
          aria-label="Refresh"
          className="text-text-muted hover:text-text-primary transition-colors"
        >
          <ArrowPathIcon className={`h-3.5 w-3.5 ${loading ? "animate-spin" : ""}`} />
        </button>
      </div>

      <button
        onClick={startNew}
        className="mx-2 mb-2 justify-center px-3 py-1.5 bg-accent text-white rounded-lg text-xs font-medium hover:bg-accent-hover transition-colors flex items-center gap-1.5"
      >
        <PlusIcon className="h-3.5 w-3.5" />
        New chat
      </button>

      <div className="min-h-0 flex-1 overflow-y-auto overflow-x-hidden px-1 pb-1">
        {content}
      </div>
    </aside>
  );
}
