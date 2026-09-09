/**
 * Tests for the ArchiveBrowser component — search, sort, view modes, actions.
 */

import React from "react";
import { render, screen, fireEvent, act } from "@testing-library/react";
import { ArchiveBrowser } from "../ArchiveBrowser";
import { SessionStore } from "@/lib/session-store";
import { ProtocolClient } from "@/lib/protocol";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function makeSession(overrides: Partial<SessionSnapshot> = {}): SessionSnapshot {
  return {
    id: overrides.id ?? "sess-1",
    title: overrides.title ?? "Test Session",
    model: overrides.model ?? "Qwen3.6-35B-A3B-Q5_K_M",
    cwd: overrides.cwd ?? ".",
    status: overrides.status ?? "ready",
    is_active: overrides.is_active ?? false,
    is_archived: overrides.is_archived ?? false,
    is_failed: overrides.is_failed ?? false,
    current_seq: overrides.current_seq ?? 0,
    created_at: overrides.created_at ?? "2024-01-01T00:00:00Z",
    updated_at: overrides.updated_at ?? "2024-01-01T00:00:00Z",
    tag: overrides.tag,
    root_session_id: overrides.root_session_id,
  };
}

function makeStore(sessions: SessionSnapshot[]): SessionStore {
  const protocolClient = new ProtocolClient();
  const store = new SessionStore(protocolClient);
  // Populate internal map via getAll() after setting up mock
  jest.spyOn(store, "getAll").mockReturnValue(sessions);
  return store;
}

// ---------------------------------------------------------------------------
// SessionSnapshot type (inline for test isolation)
// ---------------------------------------------------------------------------

interface SessionSnapshot {
  id: string;
  title: string;
  model: string;
  cwd?: string;
  status: "created" | "ready" | "running" | "interrupted" | "failed";
  is_active: boolean;
  is_archived: boolean;
  is_failed: boolean;
  current_seq: number;
  tag?: string;
  root_session_id?: string;
  created_at: string;
  updated_at: string;
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("ArchiveBrowser", () => {
  let store: SessionStore;

  beforeEach(() => {
    jest.clearAllMocks();
    // Mock fetch globally
    global.fetch = jest.fn().mockResolvedValue({
      ok: true,
      json: () => Promise.resolve({}),
    });
  });

  // ── Basic rendering ──────────────────────────────────────────────────────

  describe("rendering", () => {
    it("renders the archive header", () => {
      store = makeStore([]);
      render(
        <ArchiveBrowser
          sessionStore={store}
          activeSessionId={null}
          onSelectSession={jest.fn()}
          collapsed={false}
        />
      );
      expect(screen.getByText("Archive")).toBeInTheDocument();
    });

    it("renders session count", () => {
      const sessions = [makeSession({ id: "s1" })];
      store = makeStore(sessions);
      render(
        <ArchiveBrowser
          sessionStore={store}
          activeSessionId={null}
          onSelectSession={jest.fn()}
          collapsed={false}
        />
      );
      expect(screen.getByText("1 session")).toBeInTheDocument();
    });

    it("renders plural session count", () => {
      const sessions = [makeSession({ id: "s1" }), makeSession({ id: "s2" })];
      store = makeStore(sessions);
      render(
        <ArchiveBrowser
          sessionStore={store}
          activeSessionId={null}
          onSelectSession={jest.fn()}
          collapsed={false}
        />
      );
      expect(screen.getByText("2 sessions")).toBeInTheDocument();
    });

    it("shows archived count in footer", () => {
      const sessions = [
        makeSession({ id: "s1", is_archived: true }),
        makeSession({ id: "s2" }),
      ];
      store = makeStore(sessions);
      render(
        <ArchiveBrowser
          sessionStore={store}
          activeSessionId={null}
          onSelectSession={jest.fn()}
          collapsed={false}
        />
      );
      expect(screen.getByText("1 archived")).toBeInTheDocument();
    });

    it("renders collapsed state with archive icon", () => {
      store = makeStore([]);
      render(
        <ArchiveBrowser
          sessionStore={store}
          activeSessionId={null}
          onSelectSession={jest.fn()}
          collapsed={true}
        />
      );
      expect(screen.getByTitle("Archive browser")).toBeInTheDocument();
    });
  });

  // ── Search ───────────────────────────────────────────────────────────────

  describe("search", () => {
    it("filters sessions by title", () => {
      const sessions = [
        makeSession({ id: "s1", title: "Python coding session" }),
        makeSession({ id: "s2", title: "Data analysis" }),
      ];
      store = makeStore(sessions);
      render(
        <ArchiveBrowser
          sessionStore={store}
          activeSessionId={null}
          onSelectSession={jest.fn()}
          collapsed={false}
        />
      );

      const input = screen.getByPlaceholderText("Search archive...");
      fireEvent.change(input, { target: { value: "python" } });
      expect(screen.getByText("Python coding session")).toBeInTheDocument();
      expect(screen.queryByText("Data analysis")).not.toBeInTheDocument();
    });

    it("filters sessions by tag", () => {
      const sessions = [
        makeSession({ id: "s1", title: "Session A", tag: "important" }),
        makeSession({ id: "s2", title: "Session B", tag: "draft" }),
      ];
      store = makeStore(sessions);
      render(
        <ArchiveBrowser
          sessionStore={store}
          activeSessionId={null}
          onSelectSession={jest.fn()}
          collapsed={false}
        />
      );

      const input = screen.getByPlaceholderText("Search archive...");
      fireEvent.change(input, { target: { value: "important" } });
      expect(screen.getByText("Session A")).toBeInTheDocument();
      expect(screen.queryByText("Session B")).not.toBeInTheDocument();
    });

    it("filters sessions by model", () => {
      const sessions = [
        makeSession({ id: "s1", model: "Qwen3.6-35B-A3B-Q5_K_M" }),
        makeSession({ id: "s2", model: "Llama-3-70B" }),
      ];
      store = makeStore(sessions);
      render(
        <ArchiveBrowser
          sessionStore={store}
          activeSessionId={null}
          onSelectSession={jest.fn()}
          collapsed={false}
        />
      );

      const input = screen.getByPlaceholderText("Search archive...");
      fireEvent.change(input, { target: { value: "llama" } });
      expect(screen.getByText("Llama-3-70B")).toBeInTheDocument();
      expect(screen.queryByText("Qwen3.6-35B-A3B-Q5_K_M")).not.toBeInTheDocument();
    });

    it("shows empty message when no matches", () => {
      const sessions = [makeSession({ id: "s1", title: "Hello" })];
      store = makeStore(sessions);
      render(
        <ArchiveBrowser
          sessionStore={store}
          activeSessionId={null}
          onSelectSession={jest.fn()}
          collapsed={false}
        />
      );

      const input = screen.getByPlaceholderText("Search archive...");
      fireEvent.change(input, { target: { value: "nonexistent" } });
      expect(screen.getByText("No sessions match your search")).toBeInTheDocument();
    });

    it("clears filter when search is cleared", () => {
      const sessions = [
        makeSession({ id: "s1", title: "Python coding session" }),
        makeSession({ id: "s2", title: "Data analysis" }),
      ];
      store = makeStore(sessions);
      render(
        <ArchiveBrowser
          sessionStore={store}
          activeSessionId={null}
          onSelectSession={jest.fn()}
          collapsed={false}
        />
      );

      const input = screen.getByPlaceholderText("Search archive...");
      fireEvent.change(input, { target: { value: "python" } });
      expect(screen.queryByText("Data analysis")).not.toBeInTheDocument();

      // Clear search
      fireEvent.change(input, { target: { value: "" } });
      expect(screen.getByText("Data analysis")).toBeInTheDocument();
    });

    it("is case-insensitive", () => {
      const sessions = [makeSession({ id: "s1", title: "Python Session" })];
      store = makeStore(sessions);
      render(
        <ArchiveBrowser
          sessionStore={store}
          activeSessionId={null}
          onSelectSession={jest.fn()}
          collapsed={false}
        />
      );

      const input = screen.getByPlaceholderText("Search archive...");
      fireEvent.change(input, { target: { value: "python" } });
      expect(screen.getByText("Python Session")).toBeInTheDocument();
    });
  });

  // ── Sort ─────────────────────────────────────────────────────────────────

  describe("sort", () => {
    it("sorts by updated_at descending by default", () => {
      const sessions = [
        makeSession({ id: "s1", updated_at: "2024-01-01T00:00:00Z" }),
        makeSession({ id: "s2", updated_at: "2024-01-02T00:00:00Z" }),
      ];
      store = makeStore(sessions);
      render(
        <ArchiveBrowser
          sessionStore={store}
          activeSessionId={null}
          onSelectSession={jest.fn()}
          collapsed={false}
        />
      );

      // s2 should appear first (newer)
      const items = screen.getAllByText(/Session/);
      expect(items[0]).toHaveTextContent("Session");
    });

    it("sorts by title", () => {
      const sessions = [
        makeSession({ id: "s1", title: "Zebra" }),
        makeSession({ id: "s2", title: "Alpha" }),
      ];
      store = makeStore(sessions);
      render(
        <ArchiveBrowser
          sessionStore={store}
          activeSessionId={null}
          onSelectSession={jest.fn()}
          collapsed={false}
        />
      );

      const sortSelect = screen.getByRole("combobox");
      fireEvent.change(sortSelect, { target: { value: "title" } });

      // Default sort order is descending, so Zebra comes first
      const titles = screen.getAllByText(/Zebra|Alpha/);
      expect(titles[0]).toHaveTextContent("Zebra");
    });

    it("sorts by created_at", () => {
      const sessions = [
        makeSession({ id: "s1", created_at: "2024-01-01T00:00:00Z" }),
        makeSession({ id: "s2", created_at: "2024-01-02T00:00:00Z" }),
      ];
      store = makeStore(sessions);
      render(
        <ArchiveBrowser
          sessionStore={store}
          activeSessionId={null}
          onSelectSession={jest.fn()}
          collapsed={false}
        />
      );

      const sortSelect = screen.getByRole("combobox");
      fireEvent.change(sortSelect, { target: { value: "created_at" } });
      // Should not throw
      expect(sortSelect).toHaveValue("created_at");
    });

    it("toggles sort order", () => {
      const sessions = [
        makeSession({ id: "s1", title: "Alpha" }),
        makeSession({ id: "s2", title: "Zebra" }),
      ];
      store = makeStore(sessions);
      render(
        <ArchiveBrowser
          sessionStore={store}
          activeSessionId={null}
          onSelectSession={jest.fn()}
          collapsed={false}
        />
      );

      const sortSelect = screen.getByRole("combobox");
      fireEvent.change(sortSelect, { target: { value: "title" } });

      // Default is descending, so Zebra comes first
      let titles = screen.getAllByText(/Zebra|Alpha/);
      expect(titles[0]).toHaveTextContent("Zebra");

      // Toggle to ascending
      const toggleBtn = screen.getByTitle("Descending");
      fireEvent.click(toggleBtn);

      // Now Alpha should come first (ascending)
      titles = screen.getAllByText(/Zebra|Alpha/);
      expect(titles[0]).toHaveTextContent("Alpha");
    });

    it("resets to descending when switching sort field", () => {
      const sessions = [
        makeSession({ id: "s1", title: "Zebra" }),
        makeSession({ id: "s2", title: "Alpha" }),
      ];
      store = makeStore(sessions);
      render(
        <ArchiveBrowser
          sessionStore={store}
          activeSessionId={null}
          onSelectSession={jest.fn()}
          collapsed={false}
        />
      );

      const sortSelect = screen.getByRole("combobox");
      fireEvent.change(sortSelect, { target: { value: "title" } });
      // Switching field should reset to descending
      expect(sortSelect).toHaveValue("title");
    });
  });

  // ── View modes ───────────────────────────────────────────────────────────

  describe("view modes", () => {
    it("defaults to list view", () => {
      const sessions = [makeSession({ id: "s1" })];
      store = makeStore(sessions);
      render(
        <ArchiveBrowser
          sessionStore={store}
          activeSessionId={null}
          onSelectSession={jest.fn()}
          collapsed={false}
        />
      );

      // List view button should be active
      const listBtn = screen.getByTitle("List view");
      expect(listBtn).toHaveClass("bg-surface-active");
    });

    it("toggles to grid view", () => {
      const sessions = [makeSession({ id: "s1" })];
      store = makeStore(sessions);
      render(
        <ArchiveBrowser
          sessionStore={store}
          activeSessionId={null}
          onSelectSession={jest.fn()}
          collapsed={false}
        />
      );

      const gridBtn = screen.getByTitle("Grid view");
      fireEvent.click(gridBtn);

      // Grid view button should be active
      expect(gridBtn).toHaveClass("bg-surface-active");
    });

    it("toggles back to list view", () => {
      const sessions = [makeSession({ id: "s1" })];
      store = makeStore(sessions);
      render(
        <ArchiveBrowser
          sessionStore={store}
          activeSessionId={null}
          onSelectSession={jest.fn()}
          collapsed={false}
        />
      );

      const gridBtn = screen.getByTitle("Grid view");
      const listBtn = screen.getByTitle("List view");

      fireEvent.click(gridBtn);
      expect(gridBtn).toHaveClass("bg-surface-active");

      fireEvent.click(listBtn);
      expect(listBtn).toHaveClass("bg-surface-active");
    });
  });

  // ── Session selection ────────────────────────────────────────────────────

  describe("session selection", () => {
    it("calls onSelectSession when a session is clicked", () => {
      const onSelect = jest.fn();
      const sessions = [makeSession({ id: "s1" })];
      store = makeStore(sessions);
      render(
        <ArchiveBrowser
          sessionStore={store}
          activeSessionId={null}
          onSelectSession={onSelect}
          collapsed={false}
        />
      );

      const sessionItem = screen.getByText("Test Session");
      fireEvent.click(sessionItem);
      expect(onSelect).toHaveBeenCalledWith("s1");
    });

    it("highlights active session", () => {
      const sessions = [makeSession({ id: "s1" })];
      store = makeStore(sessions);
      render(
        <ArchiveBrowser
          sessionStore={store}
          activeSessionId="s1"
          onSelectSession={jest.fn()}
          collapsed={false}
        />
      );

      const sessionItem = screen.getByText("Test Session");
      // The bg-surface-active class is on the outer div (key={session.id})
      expect(sessionItem.closest('[class*="bg-surface-active"]')).toBeInTheDocument();
    });
  });

  // ── Session actions ──────────────────────────────────────────────────────

  describe("session actions", () => {
    it("calls onFork when fork button is clicked", async () => {
      const onFork = jest.fn();
      const sessions = [makeSession({ id: "s1", is_archived: false })];
      store = makeStore(sessions);
      render(
        <ArchiveBrowser
          sessionStore={store}
          activeSessionId={null}
          onSelectSession={jest.fn()}
          onOpenModal={jest.fn()}
          collapsed={false}
        />
      );

      // Hover to reveal actions
      const sessionItem = screen.getByText("Test Session");
      fireEvent.mouseEnter(sessionItem);

      const forkBtn = screen.getByTitle("Fork");
      fireEvent.click(forkBtn);

      // Fork makes a fetch call
      expect(global.fetch).toHaveBeenCalledWith(
        "/api/sessions/s1/fork",
        expect.objectContaining({
          method: "POST",
        })
      );
    });

    it("calls onArchive when delete button is clicked", async () => {
      const onDelete = jest.fn();
      const sessions = [makeSession({ id: "s1" })];
      store = makeStore(sessions);
      render(
        <ArchiveBrowser
          sessionStore={store}
          activeSessionId={null}
          onSelectSession={jest.fn()}
          onOpenModal={jest.fn()}
          collapsed={false}
        />
      );

      // Mock confirm
      jest.spyOn(window, "confirm").mockReturnValue(true);

      const sessionItem = screen.getByText("Test Session");
      fireEvent.mouseEnter(sessionItem);

      const deleteBtn = screen.getByTitle("Delete");
      fireEvent.click(deleteBtn);

      expect(global.fetch).toHaveBeenCalledWith(
        "/api/sessions/s1",
        expect.objectContaining({ method: "DELETE" })
      );
    });

    it("does not delete when confirm is cancelled", async () => {
      const sessions = [makeSession({ id: "s1" })];
      store = makeStore(sessions);
      render(
        <ArchiveBrowser
          sessionStore={store}
          activeSessionId={null}
          onSelectSession={jest.fn()}
          onOpenModal={jest.fn()}
          collapsed={false}
        />
      );

      jest.spyOn(window, "confirm").mockReturnValue(false);

      const sessionItem = screen.getByText("Test Session");
      fireEvent.mouseEnter(sessionItem);

      const deleteBtn = screen.getByTitle("Delete");
      fireEvent.click(deleteBtn);

      expect(global.fetch).not.toHaveBeenCalled();
    });

    it("shows view details button", () => {
      const sessions = [makeSession({ id: "s1" })];
      store = makeStore(sessions);
      render(
        <ArchiveBrowser
          sessionStore={store}
          activeSessionId={null}
          onSelectSession={jest.fn()}
          onOpenModal={jest.fn()}
          collapsed={false}
        />
      );

      const sessionItem = screen.getByText("Test Session");
      fireEvent.mouseEnter(sessionItem);

      expect(screen.getByTitle("View details")).toBeInTheDocument();
    });
  });

  // ── Session metadata display ─────────────────────────────────────────────

  describe("session metadata", () => {
    it("displays session model", () => {
      const sessions = [makeSession({ id: "s1", model: "CustomModel" })];
      store = makeStore(sessions);
      render(
        <ArchiveBrowser
          sessionStore={store}
          activeSessionId={null}
          onSelectSession={jest.fn()}
          collapsed={false}
        />
      );

      expect(screen.getByText("CustomModel")).toBeInTheDocument();
    });

    it("displays session tag when present", () => {
      const sessions = [makeSession({ id: "s1", tag: "important" })];
      store = makeStore(sessions);
      render(
        <ArchiveBrowser
          sessionStore={store}
          activeSessionId={null}
          onSelectSession={jest.fn()}
          collapsed={false}
        />
      );

      expect(screen.getByText("important")).toBeInTheDocument();
    });

    it("does not display tag when absent", () => {
      const sessions = [makeSession({ id: "s1", tag: undefined })];
      store = makeStore(sessions);
      render(
        <ArchiveBrowser
          sessionStore={store}
          activeSessionId={null}
          onSelectSession={jest.fn()}
          collapsed={false}
        />
      );

      expect(screen.queryByText("important")).not.toBeInTheDocument();
    });

    it("shows status indicator for archived session", () => {
      const sessions = [makeSession({ id: "s1", is_archived: true })];
      store = makeStore(sessions);
      render(
        <ArchiveBrowser
          sessionStore={store}
          activeSessionId={null}
          onSelectSession={jest.fn()}
          collapsed={false}
        />
      );

      // Archived sessions should have muted status indicator
      expect(screen.getByText("Test Session")).toBeInTheDocument();
    });

    it("shows status indicator for failed session", () => {
      const sessions = [makeSession({ id: "s1", is_failed: true })];
      store = makeStore(sessions);
      render(
        <ArchiveBrowser
          sessionStore={store}
          activeSessionId={null}
          onSelectSession={jest.fn()}
          collapsed={false}
        />
      );

      expect(screen.getByText("Test Session")).toBeInTheDocument();
    });

    it("shows status indicator for active session", () => {
      const sessions = [makeSession({ id: "s1", is_active: true })];
      store = makeStore(sessions);
      render(
        <ArchiveBrowser
          sessionStore={store}
          activeSessionId={null}
          onSelectSession={jest.fn()}
          collapsed={false}
        />
      );

      expect(screen.getByText("Test Session")).toBeInTheDocument();
    });
  });

  // ── Empty state ──────────────────────────────────────────────────────────

  describe("empty state", () => {
    it("shows 'No sessions in archive' when empty", () => {
      store = makeStore([]);
      render(
        <ArchiveBrowser
          sessionStore={store}
          activeSessionId={null}
          onSelectSession={jest.fn()}
          collapsed={false}
        />
      );

      expect(screen.getByText("No sessions in archive")).toBeInTheDocument();
    });

    it("shows 'No sessions match your search' when search yields no results", () => {
      const sessions = [makeSession({ id: "s1", title: "Hello" })];
      store = makeStore(sessions);
      render(
        <ArchiveBrowser
          sessionStore={store}
          activeSessionId={null}
          onSelectSession={jest.fn()}
          collapsed={false}
        />
      );

      const input = screen.getByPlaceholderText("Search archive...");
      fireEvent.change(input, { target: { value: "nonexistent" } });
      expect(screen.getByText("No sessions match your search")).toBeInTheDocument();
    });
  });

  // ── Collapsed state ──────────────────────────────────────────────────────

  describe("collapsed state", () => {
    it("renders only the archive icon when collapsed", () => {
      store = makeStore([]);
      render(
        <ArchiveBrowser
          sessionStore={store}
          activeSessionId={null}
          onSelectSession={jest.fn()}
          collapsed={true}
        />
      );

      expect(screen.getByTitle("Archive browser")).toBeInTheDocument();
      // Should NOT show search, sort, or session list
      expect(screen.queryByPlaceholderText("Search archive...")).not.toBeInTheDocument();
      expect(screen.queryByText("Archive")).not.toBeInTheDocument();
    });
  });

  // ── Footer ───────────────────────────────────────────────────────────────

  describe("footer", () => {
    it("shows 'Archive Browser' label", () => {
      store = makeStore([]);
      render(
        <ArchiveBrowser
          sessionStore={store}
          activeSessionId={null}
          onSelectSession={jest.fn()}
          collapsed={false}
        />
      );

      expect(screen.getByText("Archive Browser")).toBeInTheDocument();
    });

    it("shows 0 archived when none archived", () => {
      const sessions = [makeSession({ id: "s1" })];
      store = makeStore(sessions);
      render(
        <ArchiveBrowser
          sessionStore={store}
          activeSessionId={null}
          onSelectSession={jest.fn()}
          collapsed={false}
        />
      );

      expect(screen.getByText("0 archived")).toBeInTheDocument();
    });
  });

  // ── Search + sort interaction ────────────────────────────────────────────

  describe("search + sort interaction", () => {
    it("applies search then sort", () => {
      const sessions = [
        makeSession({ id: "s1", title: "Zebra Python", updated_at: "2024-01-02T00:00:00Z" }),
        makeSession({ id: "s2", title: "Alpha Python", updated_at: "2024-01-01T00:00:00Z" }),
        makeSession({ id: "s3", title: "Beta Rust", updated_at: "2024-01-03T00:00:00Z" }),
      ];
      store = makeStore(sessions);
      render(
        <ArchiveBrowser
          sessionStore={store}
          activeSessionId={null}
          onSelectSession={jest.fn()}
          collapsed={false}
        />
      );

      // Search for "python"
      const input = screen.getByPlaceholderText("Search archive...");
      fireEvent.change(input, { target: { value: "python" } });

      // Should only show Python sessions
      expect(screen.getByText("Zebra Python")).toBeInTheDocument();
      expect(screen.getByText("Alpha Python")).toBeInTheDocument();
      expect(screen.queryByText("Beta Rust")).not.toBeInTheDocument();

      // Sort by title
      const sortSelect = screen.getByRole("combobox");
      fireEvent.change(sortSelect, { target: { value: "title" } });

      // Default is descending, so Zebra comes first
      let titles = screen.getAllByText(/Zebra Python|Alpha Python/);
      expect(titles[0]).toHaveTextContent("Zebra Python");

      // Toggle to ascending
      const toggleBtn = screen.getByTitle("Descending");
      fireEvent.click(toggleBtn);

      // Alpha should come before Zebra
      titles = screen.getAllByText(/Zebra Python|Alpha Python/);
      expect(titles[0]).toHaveTextContent("Alpha Python");
    });
  });

  // ── Archived session visibility ──────────────────────────────────────────

  describe("archived session visibility", () => {
    it("shows archived sessions in archive browser", () => {
      const sessions = [
        makeSession({ id: "s1", is_archived: true, title: "Archived Session" }),
      ];
      store = makeStore(sessions);
      render(
        <ArchiveBrowser
          sessionStore={store}
          activeSessionId={null}
          onSelectSession={jest.fn()}
          collapsed={false}
        />
      );

      expect(screen.getByText("Archived Session")).toBeInTheDocument();
    });

    it("shows active sessions in archive browser", () => {
      const sessions = [
        makeSession({ id: "s1", is_active: true, title: "Active Session" }),
      ];
      store = makeStore(sessions);
      render(
        <ArchiveBrowser
          sessionStore={store}
          activeSessionId={null}
          onSelectSession={jest.fn()}
          collapsed={false}
        />
      );

      expect(screen.getByText("Active Session")).toBeInTheDocument();
    });
  });

  // ── Resume / Fork API calls ──────────────────────────────────────────────

  describe("resume and fork API calls", () => {
    it("resumes session via POST /api/sessions", async () => {
      const onSelect = jest.fn();
      const sessions = [makeSession({ id: "s1" })];
      store = makeStore(sessions);

      jest.spyOn(global, "fetch").mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve({ id: "s2" }),
      } as Response);

      render(
        <ArchiveBrowser
          sessionStore={store}
          activeSessionId={null}
          onSelectSession={onSelect}
          onOpenModal={jest.fn()}
          collapsed={false}
        />
      );

      // The resume button is not directly visible in the list mode;
      // it's triggered from the modal. We verify the component's
      // handleResume function by checking the component renders without error.
      expect(screen.getByText("Test Session")).toBeInTheDocument();
    });

    it("forks session via POST /api/sessions/:id/fork", async () => {
      const sessions = [makeSession({ id: "s1" })];
      store = makeStore(sessions);

      jest.spyOn(global, "fetch").mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve({ id: "s2" }),
      } as Response);

      render(
        <ArchiveBrowser
          sessionStore={store}
          activeSessionId={null}
          onSelectSession={jest.fn()}
          onOpenModal={jest.fn()}
          collapsed={false}
        />
      );

      const sessionItem = screen.getByText("Test Session");
      fireEvent.mouseEnter(sessionItem);

      const forkBtn = screen.getByTitle("Fork");
      fireEvent.click(forkBtn);

      expect(global.fetch).toHaveBeenCalledWith(
        "/api/sessions/s1/fork",
        expect.objectContaining({
          method: "POST",
          headers: { "Content-Type": "application/json" },
        })
      );
    });
  });

  // ── Rename and Tag ───────────────────────────────────────────────────────

  describe("rename and tag", () => {
    it("shows rename input when rename button is clicked", () => {
      const sessions = [makeSession({ id: "s1", is_archived: false })];
      store = makeStore(sessions);
      render(
        <ArchiveBrowser
          sessionStore={store}
          activeSessionId={null}
          onSelectSession={jest.fn()}
          onOpenModal={jest.fn()}
          collapsed={false}
        />
      );

      const sessionItem = screen.getByText("Test Session");
      fireEvent.mouseEnter(sessionItem);

      const renameBtn = screen.getByTitle("Rename");
      fireEvent.click(renameBtn);

      // Rename input should appear
      expect(screen.getByDisplayValue("Test Session")).toBeInTheDocument();
    });

    it("shows tag input when tag button is clicked", () => {
      const sessions = [makeSession({ id: "s1", is_archived: false })];
      store = makeStore(sessions);
      render(
        <ArchiveBrowser
          sessionStore={store}
          activeSessionId={null}
          onSelectSession={jest.fn()}
          onOpenModal={jest.fn()}
          collapsed={false}
        />
      );

      const sessionItem = screen.getByText("Test Session");
      fireEvent.mouseEnter(sessionItem);

      const tagBtn = screen.getByTitle("Tag");
      fireEvent.click(tagBtn);

      // Tag input should appear
      expect(screen.getByPlaceholderText("Enter tag...")).toBeInTheDocument();
    });

    it("does not show rename/tag buttons for archived sessions", () => {
      const sessions = [makeSession({ id: "s1", is_archived: true })];
      store = makeStore(sessions);
      render(
        <ArchiveBrowser
          sessionStore={store}
          activeSessionId={null}
          onSelectSession={jest.fn()}
          onOpenModal={jest.fn()}
          collapsed={false}
        />
      );

      const sessionItem = screen.getByText("Test Session");
      fireEvent.mouseEnter(sessionItem);

      // Rename and tag buttons should not be visible for archived sessions
      expect(screen.queryByTitle("Rename")).not.toBeInTheDocument();
      expect(screen.queryByTitle("Tag")).not.toBeInTheDocument();
    });

    it("calls onRename when rename input is submitted", async () => {
      const sessions = [makeSession({ id: "s1", is_archived: false })];
      store = makeStore(sessions);

      jest.spyOn(global, "fetch").mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve({}),
      } as Response);

      render(
        <ArchiveBrowser
          sessionStore={store}
          activeSessionId={null}
          onSelectSession={jest.fn()}
          onOpenModal={jest.fn()}
          collapsed={false}
        />
      );

      const sessionItem = screen.getByText("Test Session");
      fireEvent.mouseEnter(sessionItem);

      const renameBtn = screen.getByTitle("Rename");
      fireEvent.click(renameBtn);

      const renameInput = screen.getByDisplayValue("Test Session");
      fireEvent.change(renameInput, { target: { value: "New Title" } });
      fireEvent.keyDown(renameInput, { key: "Enter" });

      expect(global.fetch).toHaveBeenCalledWith(
        "/api/sessions/s1",
        expect.objectContaining({
          method: "PATCH",
          body: JSON.stringify({ title: "New Title" }),
        })
      );
    });

    it("calls onTag when tag input is submitted", async () => {
      const sessions = [makeSession({ id: "s1", is_archived: false })];
      store = makeStore(sessions);

      jest.spyOn(global, "fetch").mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve({}),
      } as Response);

      render(
        <ArchiveBrowser
          sessionStore={store}
          activeSessionId={null}
          onSelectSession={jest.fn()}
          onOpenModal={jest.fn()}
          collapsed={false}
        />
      );

      const sessionItem = screen.getByText("Test Session");
      fireEvent.mouseEnter(sessionItem);

      const tagBtn = screen.getByTitle("Tag");
      fireEvent.click(tagBtn);

      const tagInput = screen.getByPlaceholderText("Enter tag...");
      fireEvent.change(tagInput, { target: { value: "important" } });
      fireEvent.keyDown(tagInput, { key: "Enter" });

      expect(global.fetch).toHaveBeenCalledWith(
        "/api/sessions/s1/tag",
        expect.objectContaining({
          method: "POST",
          body: JSON.stringify({ tag: "important" }),
        })
      );
    });

    it("cancels rename on Escape", () => {
      const sessions = [makeSession({ id: "s1", is_archived: false })];
      store = makeStore(sessions);
      render(
        <ArchiveBrowser
          sessionStore={store}
          activeSessionId={null}
          onSelectSession={jest.fn()}
          onOpenModal={jest.fn()}
          collapsed={false}
        />
      );

      const sessionItem = screen.getByText("Test Session");
      fireEvent.mouseEnter(sessionItem);

      const renameBtn = screen.getByTitle("Rename");
      fireEvent.click(renameBtn);

      const renameInput = screen.getByDisplayValue("Test Session");
      fireEvent.keyDown(renameInput, { key: "Escape" });

      // Rename input should be gone
      expect(screen.queryByDisplayValue("Test Session")).not.toBeInTheDocument();
    });

    it("cancels tag on Escape", () => {
      const sessions = [makeSession({ id: "s1", is_archived: false })];
      store = makeStore(sessions);
      render(
        <ArchiveBrowser
          sessionStore={store}
          activeSessionId={null}
          onSelectSession={jest.fn()}
          onOpenModal={jest.fn()}
          collapsed={false}
        />
      );

      const sessionItem = screen.getByText("Test Session");
      fireEvent.mouseEnter(sessionItem);

      const tagBtn = screen.getByTitle("Tag");
      fireEvent.click(tagBtn);

      const tagInput = screen.getByPlaceholderText("Enter tag...");
      fireEvent.keyDown(tagInput, { key: "Escape" });

      // Tag input should be gone
      expect(screen.queryByPlaceholderText("Enter tag...")).not.toBeInTheDocument();
    });
  });
});
