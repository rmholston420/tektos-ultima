/**
 * Tektos Chat Panel — ACP-compatible agent chat with virtualized messages.
 *
 * A coding-agent chat surface with:
 * - Left: chat column (virtualized message list + input)
 * - Right: collapsible drawer with tabbed content (Files, Terminal, Preview)
 *
 * Protocol: ACP-compatible JSON-RPC over Streamable HTTP (with WebSocket fallback).
 * Security: All user/agent content rendered as text via React JSX escaping.
 * Performance: @tanstack/react-virtual for message list virtualization.
 * Accessibility: ARIA roles, keyboard navigation, focus management.
 *
 * Spec: docs/tektos-chat-panel-spec-v1.md
 */

"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useVirtualizer } from "@tanstack/react-virtual";
import {
  ChatBubbleLeftIcon,
  DocumentIcon,
  CommandLineIcon,
  EyeIcon,
  XMarkIcon,
  PaperAirplaneIcon,
  StopIcon,
  Cog6ToothIcon,
  SparklesIcon,
  ListBulletIcon,
} from "@heroicons/react/24/outline";
import {
  SparklesIcon as SparklesSolid,
  ChatBubbleLeftIcon as ChatBubbleSolid,
} from "@heroicons/react/24/solid";

// ── Types ───────────────────────────────────────────────────────────────────

interface ChatMessage {
  id: string;
  role: "user" | "assistant" | "system" | "tool";
  content: string;
  timestamp: string;
  toolName?: string;
  toolResult?: string;
}

interface FileNode {
  name: string;
  path: string;
  isDirectory: boolean;
  modified?: boolean;
  children?: FileNode[];
}

interface TerminalLine {
  id: string;
  command?: string;
  output: string;
  timestamp: string;
  isError?: boolean;
}

type DrawerTab = "files" | "terminal" | "preview";
type ConnectionState = "connected" | "connecting" | "disconnected" | "error";

// ── Background Task Model ───────────────────────────────────────────────────

interface BackgroundTask {
  id: string;
  sessionId: string;
  status: "running" | "paused" | "completed" | "failed";
  prompt: string;
  startedAt: string;
  completedAt?: string;
  messageCount: number;
}

// ── Tab definitions ─────────────────────────────────────────────────────────

const TABS: { id: DrawerTab; label: string; icon: string; shortcut: string }[] = [
  { id: "files", label: "Files", icon: "document", shortcut: "1" },
  { id: "terminal", label: "Terminal", icon: "terminal", shortcut: "2" },
  { id: "preview", label: "Preview", icon: "eye", shortcut: "3" },
];

// ── Empty state helper ──────────────────────────────────────────────────────

function EmptyState({ icon, message }: { icon: string; message: string }) {
  return (
    <div
      className="flex flex-col items-center justify-center h-full py-12 text-muted-foreground text-sm"
      role="status"
      aria-live="polite"
    >
      <span className="text-2xl mb-2 opacity-50">{icon}</span>
      <span>{message}</span>
    </div>
  );
}

// ── Connection indicator ────────────────────────────────────────────────────

function ConnectionIndicator({ state }: { state: ConnectionState }) {
  const config = {
    connected: { color: "bg-green-500", label: "Connected" },
    connecting: { color: "bg-yellow-500 animate-pulse", label: "Connecting..." },
    disconnected: { color: "bg-red-500", label: "Disconnected" },
    error: { color: "bg-red-500", label: "Error" },
  };
  const c = config[state];
  return (
    <div className="flex items-center gap-1.5 text-xs text-muted-foreground" title={c.label}>
      <span className={`w-2 h-2 rounded-full ${c.color}`} />
      <span className="hidden sm:inline">{c.label}</span>
    </div>
  );
}

// ── Virtualized Message Row ─────────────────────────────────────────────────

function MessageRow({ message }: { message: ChatMessage }) {
  return (
    <div
      className={`flex ${message.role === "user" ? "justify-end" : "justify-start"}`}
      role="article"
      aria-label={`${message.role} message`}
    >
      <div
        className={`max-w-[85%] rounded-lg px-3 py-2 text-sm ${
          message.role === "user"
            ? "bg-blue-600 text-white"
            : message.role === "tool"
            ? "bg-yellow-500/10 border border-yellow-500/30 text-yellow-200"
            : message.role === "system"
            ? "bg-red-500/10 border border-red-500/30 text-red-300"
            : "bg-surface text-foreground"
        }`}
      >
        {message.role === "tool" && message.toolName && (
          <div className="flex items-center gap-1 mb-1 text-xs opacity-70">
            <Cog6ToothIcon className="h-3 w-3" />
            <span>{message.toolName}</span>
          </div>
        )}
        {/* Content rendered as text — safe from XSS via React JSX escaping */}
        <div className="whitespace-pre-wrap break-words">{message.content}</div>
        <div className={`text-xs mt-1 ${message.role === "user" ? "text-blue-200" : "opacity-50"}`}>
          {new Date(message.timestamp).toLocaleTimeString()}
        </div>
      </div>
    </div>
  );
}

// ── Chat Column ─────────────────────────────────────────────────────────────

function ChatColumn({
  messages,
  onSend,
  loading,
  connectionState,
}: {
  messages: ChatMessage[];
  onSend: (text: string) => void;
  loading: boolean;
  connectionState: ConnectionState;
}) {
  const [input, setInput] = useState("");
  const inputRef = useRef<HTMLInputElement>(null);
  const parentRef = useRef<HTMLDivElement>(null);

  // Virtualized message list
  const virtualizer = useVirtualizer({
    count: messages.length,
    getScrollElement: () => parentRef.current,
    estimateSize: () => 80,
    overscan: 5,
  });

  // Auto-scroll to bottom on new messages (only when user is near bottom)
  const isNearBottom = useRef(true);
  useEffect(() => {
    if (isNearBottom.current && parentRef.current) {
      parentRef.current.scrollTo({ top: parentRef.current.scrollHeight, behavior: "smooth" });
    }
  }, [messages.length]);

  // Track if user is near bottom for auto-scroll behavior
  useEffect(() => {
    const el = parentRef.current;
    if (!el) return;
    const handleScroll = () => {
      const { scrollTop, scrollHeight, clientHeight } = el;
      isNearBottom.current = scrollHeight - scrollTop - clientHeight < 150;
    };
    el.addEventListener("scroll", handleScroll);
    return () => el.removeEventListener("scroll", handleScroll);
  }, []);

  // Focus input on mount
  useEffect(() => {
    inputRef.current?.focus();
  }, []);

  // Keyboard shortcut: Ctrl+Enter to send
  const handleKeyDown = (e: React.KeyboardEvent) => {
    if ((e.ctrlKey || e.metaKey) && e.key === "Enter") {
      e.preventDefault();
      handleSubmit(e);
    }
    if (e.key === "Escape") {
      inputRef.current?.blur();
    }
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    const text = input.trim();
    if (!text || loading) return;
    onSend(text);
    setInput("");
  };

  // Compute visible range for virtualized list
  const virtualItems = virtualizer.getVirtualItems();

  return (
    <div className="flex flex-col h-full" role="region" aria-label="Chat">
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-2 border-b border-border">
        <div className="flex items-center gap-2">
          <ChatBubbleLeftIcon className="h-4 w-4 text-blue-400" />
          <span className="font-medium text-sm">Tektos Chat</span>
          <ConnectionIndicator state={connectionState} />
        </div>
        <div className="text-xs text-muted-foreground">
          <span className="hidden sm:inline">Ctrl+Enter to send</span>
        </div>
      </div>

      {/* Messages — virtualized list container */}
      <div
        ref={parentRef}
        className="flex-1 overflow-y-auto"
        role="log"
        aria-live="polite"
        aria-label="Chat messages"
      >
        {/* Spacer for virtualized items */}
        <div style={{ height: `${virtualizer.getTotalSize()}px`, width: "100%", position: "relative" }}>
          {virtualItems.map(virtualRow => {
            const message = messages[virtualRow.index];
            if (!message) return null;
            return (
              <div
                key={virtualRow.key}
                data-index={virtualRow.index}
                ref={virtualizer.measureElement}
                style={{
                  position: "absolute",
                  top: 0,
                  left: 0,
                  width: "100%",
                  transform: `translateY(${virtualRow.start}px)`,
                }}
              >
                <MessageRow message={message} />
              </div>
            );
          })}
        </div>

        {messages.length === 0 && (
          <div className="flex flex-col items-center justify-center h-full text-muted-foreground text-sm">
            <ChatBubbleLeftIcon className="h-10 w-10 mb-3 opacity-40" />
            <p className="font-medium">Tektos Chat</p>
            <p className="mt-1">Send a message to start a coding task.</p>
          </div>
        )}

        {loading && (
          <div className="flex justify-start px-4 pb-2" role="status" aria-label="Agent is thinking">
            <div className="bg-surface rounded-lg px-3 py-2 text-sm text-muted-foreground">
              <span className="animate-spin inline-block mr-1">⏳</span>
              Thinking...
            </div>
          </div>
        )}
      </div>

      {/* Input */}
      <form onSubmit={handleSubmit} className="p-3 border-t border-border">
        <div className="flex gap-2">
          <input
            ref={inputRef}
            type="text"
            placeholder="Describe what you want to build..."
            value={input}
            onChange={e => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            className="flex-1 bg-bg-3 border border-border rounded-lg px-3 py-2 text-sm placeholder-muted-foreground focus:border-accent focus:ring-1 focus:ring-accent/20 transition-all"
            disabled={loading || connectionState === "error"}
            aria-label="Chat input"
          />
          <button
            type="submit"
            disabled={!input.trim() || loading || connectionState === "error"}
            className="h-9 px-3 flex items-center justify-center rounded-lg bg-accent text-white hover:bg-accent-hover transition-all disabled:opacity-30 disabled:cursor-not-allowed text-sm"
            aria-label="Send message"
          >
            <PaperAirplaneIcon className="h-4 w-4 mr-1 rotate-90" />
            Send
          </button>
        </div>
      </form>
    </div>
  );
}

// ── Files Tab ───────────────────────────────────────────────────────────────

function FilesTab() {
  const [files, setFiles] = useState<FileNode[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchFiles = useCallback(async () => {
    try {
      setError(null);
      // Placeholder: backend needs a file-tree endpoint
      // e.g., GET /api/files?path=/workspace
      setFiles([]);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load files");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { fetchFiles(); }, [fetchFiles]);

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <span className="animate-spin inline-block mr-2">⏳</span>
        <span className="text-muted-foreground text-sm">Loading files...</span>
      </div>
    );
  }

  return (
    <div className="space-y-2" role="tree" aria-label="File tree">
      {error && (
        <div className="p-3 rounded-md bg-red-500/10 border border-red-500/30 text-red-400 text-sm" role="alert">
          {error}
        </div>
      )}
      {files.length === 0 ? (
        <EmptyState icon="📁" message="No files modified yet." />
      ) : (
        <div className="space-y-1">
          {files.map(f => (
            <div
              key={f.path}
              className={`flex items-center gap-2 px-2 py-1 rounded text-sm cursor-pointer hover:bg-surface-hover ${
                f.isDirectory ? "font-medium" : ""
              }`}
              role="treeitem"
              aria-label={f.name}
            >
              <DocumentIcon className="h-4 w-4 text-muted-foreground" />
              <span className="truncate">{f.name}</span>
              {f.modified && (
                <span className="text-xs px-1.5 py-0.5 rounded bg-yellow-500/20 text-yellow-400">modified</span>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

// ── Terminal Tab ────────────────────────────────────────────────────────────

function TerminalTab() {
  const [lines, setLines] = useState<TerminalLine[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [lines]);

  // Placeholder: subscribe to terminal stream
  useEffect(() => {
    const timer = setTimeout(() => setLoading(false), 500);
    return () => clearTimeout(timer);
  }, []);

  return (
    <div className="space-y-2" role="region" aria-label="Terminal output">
      {error && (
        <div className="p-3 rounded-md bg-red-500/10 border border-red-500/30 text-red-400 text-sm" role="alert">
          {error}
        </div>
      )}
      {loading ? (
        <div className="flex items-center justify-center h-64">
          <span className="animate-spin inline-block mr-2">⏳</span>
          <span className="text-muted-foreground text-sm">Loading terminal...</span>
        </div>
      ) : lines.length === 0 ? (
        <EmptyState icon="⌨️" message="No terminal output yet." />
      ) : (
        <div className="bg-black/20 rounded-md p-3 font-mono text-xs space-y-1 max-h-[500px] overflow-y-auto">
          {lines.map(line => (
            <div key={line.id}>
              {line.command && (
                <div className="text-green-400">$ {line.command}</div>
              )}
              {/* Output rendered as text — safe from XSS */}
              <div className={line.isError ? "text-red-400" : "text-muted-foreground"}>
                {line.output}
              </div>
            </div>
          ))}
          <div ref={bottomRef} />
        </div>
      )}
    </div>
  );
}

// ── Preview Tab ─────────────────────────────────────────────────────────────

function PreviewTab() {
  return (
    <div className="space-y-2" role="region" aria-label="Preview">
      <EmptyState icon="👁️" message="No preview available yet." />
    </div>
  );
}

// ── Drawer (right side) ─────────────────────────────────────────────────────

function Drawer({
  open,
  onClose,
}: {
  open: boolean;
  onClose: () => void;
}) {
  const [activeTab, setActiveTab] = useState<DrawerTab>("files");

  // Keyboard shortcut: Alt+1/2/3 to switch tabs
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (e.altKey && e.key === "1") { e.preventDefault(); setActiveTab("files"); }
      if (e.altKey && e.key === "2") { e.preventDefault(); setActiveTab("terminal"); }
      if (e.altKey && e.key === "3") { e.preventDefault(); setActiveTab("preview"); }
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, []);

  if (!open) return null;

  return (
    <div className="flex flex-col h-full border-l border-border" role="complementary" aria-label="Side drawer">
      {/* Tabs */}
      <div className="flex items-center border-b border-border">
        {TABS.map(tab => (
          <button
            key={tab.id}
            onClick={() => setActiveTab(tab.id)}
            role="tab"
            aria-selected={activeTab === tab.id}
            aria-controls={`panel-${tab.id}`}
            className={`flex items-center gap-1.5 px-3 py-2 text-xs font-medium border-b-2 transition-colors ${
              activeTab === tab.id
                ? "border-blue-500 text-blue-400"
                : "border-transparent text-muted-foreground hover:text-foreground"
            }`}
          >
            {tab.icon === "document" && <DocumentIcon className="h-3.5 w-3.5" />}
            {tab.icon === "terminal" && <CommandLineIcon className="h-3.5 w-3.5" />}
            {tab.icon === "eye" && <EyeIcon className="h-3.5 w-3.5" />}
            <span className="hidden sm:inline">{tab.label}</span>
            <span className="sm:hidden">{tab.label[0]}</span>
          </button>
        ))}
        <div className="flex-1" />
        <button
          onClick={onClose}
          title="Close drawer (Escape)"
          aria-label="Close drawer"
          className="p-2 hover:bg-surface-hover rounded-md transition-colors"
        >
          <XMarkIcon className="h-4 w-4" />
        </button>
      </div>

      {/* Tab panels */}
      <div className="flex-1 overflow-hidden p-3">
        <div
          id="panel-files"
          role="tabpanel"
          aria-labelledby={TABS[0].label}
          className={activeTab === "files" ? "" : "hidden"}
        >
          <FilesTab />
        </div>
        <div
          id="panel-terminal"
          role="tabpanel"
          aria-labelledby={TABS[1].label}
          className={activeTab === "terminal" ? "" : "hidden"}
        >
          <TerminalTab />
        </div>
        <div
          id="panel-preview"
          role="tabpanel"
          aria-labelledby={TABS[2].label}
          className={activeTab === "preview" ? "" : "hidden"}
        >
          <PreviewTab />
        </div>
      </div>
    </div>
  );
}

// ── Active Tasks Bar ────────────────────────────────────────────────────────

function ActiveTasksBar({
  tasks,
  onShowSession,
}: {
  tasks: BackgroundTask[];
  onShowSession: (sessionId: string) => void;
}) {
  if (tasks.length === 0) return null;

  return (
    <div className="flex items-center gap-2 px-4 py-1.5 border-b border-border bg-surface text-xs">
      <ListBulletIcon className="h-3.5 w-3.5 text-muted-foreground" />
      <span className="text-muted-foreground">Active tasks:</span>
      {tasks.map(task => (
        <button
          key={task.id}
          onClick={() => onShowSession(task.sessionId)}
          className={`flex items-center gap-1 px-2 py-0.5 rounded-full transition-colors ${
            task.status === "running"
              ? "bg-blue-500/20 text-blue-400 hover:bg-blue-500/30"
              : task.status === "paused"
              ? "bg-yellow-500/20 text-yellow-400 hover:bg-yellow-500/30"
              : task.status === "failed"
              ? "bg-red-500/20 text-red-400 hover:bg-red-500/30"
              : "bg-green-500/20 text-green-400 hover:bg-green-500/30"
          }`}
          title={task.prompt}
        >
          {task.status === "running" && <span className="w-1.5 h-1.5 rounded-full bg-blue-400 animate-pulse" />}
          <span className="truncate max-w-[120px]">{task.prompt.slice(0, 30)}...</span>
        </button>
      ))}
    </div>
  );
}

// ── Main Component ──────────────────────────────────────────────────────────

export function TektosChatPanel() {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [drawerOpen, setDrawerOpen] = useState(true);
  const [sending, setSending] = useState(false);
  const [connectionState, setConnectionState] = useState<ConnectionState>("connected");
  const [activeTasks, setActiveTasks] = useState<BackgroundTask[]>([]);
  const [currentSessionId, setCurrentSessionId] = useState<string | null>(null);

  // Handle Escape key to close drawer
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (e.key === "Escape" && drawerOpen) {
        setDrawerOpen(false);
      }
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [drawerOpen]);

  const handleSend = useCallback(async (text: string) => {
    setSending(true);
    setConnectionState("connecting");

    const userMsg: ChatMessage = {
      id: `msg-${Date.now()}-user`,
      role: "user",
      content: text,
      timestamp: new Date().toISOString(),
    };
    setMessages(prev => [...prev, userMsg]);

    // Placeholder: connect to Tektos backend via ACP-compatible protocol
    // In the full implementation, this would:
    // 1. POST to /api/agent/prompt with the user message
    // 2. Subscribe to SSE/WebSocket stream for agent updates
    // 3. Map session/update notifications to ChatMessage objects
    try {
      await new Promise(resolve => setTimeout(resolve, 800));
      const assistantMsg: ChatMessage = {
        id: `msg-${Date.now()}-assistant`,
        role: "assistant",
        content: `I received your request: "${text}". This is a placeholder response — the full implementation will connect to the Tektos backend via the ACP-compatible protocol.`,
        timestamp: new Date().toISOString(),
      };
      setMessages(prev => [...prev, assistantMsg]);
      setConnectionState("connected");

      // Track as a background task
      const taskId = `task-${Date.now()}`;
      const task: BackgroundTask = {
        id: taskId,
        sessionId: `sess-placeholder`,
        status: "running",
        prompt: text,
        startedAt: new Date().toISOString(),
        messageCount: 0,
      };
      setActiveTasks(prev => [...prev, task]);
      setCurrentSessionId(task.sessionId);
    } catch {
      setMessages(prev => [...prev, {
        id: `msg-${Date.now()}-error`,
        role: "system",
        content: "Failed to connect to the agent. Please check the backend is running.",
        timestamp: new Date().toISOString(),
      }]);
      setConnectionState("error");
    } finally {
      setSending(false);
    }
  }, []);

  const handleShowSession = useCallback((sessionId: string) => {
    console.log("Showing session:", sessionId);
  }, []);

  return (
    <div className="flex h-full" role="main" aria-label="Tektos Chat Panel">
      {/* Chat column */}
      <div
        className={`flex flex-col transition-all duration-200 ${
          drawerOpen ? "w-1/2 min-w-[320px]" : "w-full"
        }`}
      >
        {/* Active tasks bar */}
        <ActiveTasksBar tasks={activeTasks} onShowSession={handleShowSession} />

        <ChatColumn
          messages={messages}
          onSend={handleSend}
          loading={sending}
          connectionState={connectionState}
        />
      </div>

      {/* Drawer */}
      <Drawer open={drawerOpen} onClose={() => setDrawerOpen(false)} />
    </div>
  );
}
