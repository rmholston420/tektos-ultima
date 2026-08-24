/**
 * Tests for the Sidebar component — session list, theme switching, navigation.
 */

import React from "react";
import { render, screen, fireEvent, waitFor, act } from "@testing-library/react";
import { Sidebar } from "../Sidebar";
import { SessionStore, type SessionSnapshot } from "@/lib/session-store";
import { ProtocolClient } from "@/lib/protocol";

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
  jest.spyOn(store, "getAll").mockReturnValue(sessions);
  jest.spyOn(store, "searchSessions").mockImplementation((q) =>
    sessions.filter(
      (s) =>
        s.title.toLowerCase().includes(q.toLowerCase()) ||
        (s.tag ?? "").toLowerCase().includes(q.toLowerCase())
    )
  );
  jest.spyOn(store, "createSession").mockResolvedValue(makeSession({ id: "new-1" }));
  jest.spyOn(store, "renameSession").mockResolvedValue(undefined);
  jest.spyOn(store, "tagSession").mockResolvedValue(undefined);
  jest.spyOn(store, "forkSession").mockResolvedValue(makeSession({ id: "fork-1" }));
  jest.spyOn(store, "archiveSession").mockResolvedValue(undefined);
  jest.spyOn(store, "deleteSession").mockResolvedValue(undefined);
  jest.spyOn(store, "syncSessions").mockResolvedValue(undefined);
  jest.spyOn(store, "getSessions").mockResolvedValue(sessions);
  return store;
}

function getActiveSectionHeader(): HTMLElement | null {
  const all = screen.queryAllByText("Active");
  for (const el of all) {
    if (el.tagName === "P" && el.className.includes("uppercase")) return el;
  }
  return null;
}

function getHistorySectionHeader(): HTMLElement | null {
  const all = screen.queryAllByText("History");
  for (const el of all) {
    if (el.tagName === "P" && el.className.includes("uppercase")) return el;
  }
  return null;
}

function getFooterThemeButton(text: string): HTMLElement | null {
  const all = screen.queryAllByText(text);
  for (const el of all) {
    const btn = el.closest("button");
    if (btn) {
      const footer = btn.closest('aside > div[class*="border-t"]');
      if (footer) return btn;
    }
  }
  return null;
}

describe("Sidebar", () => {
  let store: SessionStore;
  let onNavigate: jest.Mock;
  let onCreateSession: jest.Mock;
  let onSelectSession: jest.Mock;

  beforeEach(() => {
    jest.clearAllMocks();
    onNavigate = jest.fn();
    onCreateSession = jest.fn();
    onSelectSession = jest.fn();
    global.fetch = jest.fn().mockResolvedValue({
      ok: true,
      json: () => Promise.resolve([]),
    });
    (window as any).prompt = jest.fn().mockReturnValue("test-tag");
    localStorage.clear();
  });

  function renderSidebar(sessions: SessionSnapshot[] = [], props?: Record<string, any>) {
    store = makeStore(sessions);
    return render(
      <Sidebar
        sessionStore={store}
        activeSessionId={null}
        onSelectSession={onSelectSession}
        onCreateSession={onCreateSession}
        theme="abyss"
        collapsed={false}
        onToggleCollapsed={jest.fn()}
        activePage="chat"
        onNavigate={onNavigate}
        {...props}
      />
    );
  }

  describe("expanded state", () => {
    it("renders the Sessions header", async () => {
      renderSidebar([]);
      await waitFor(() => expect(screen.getByText("Sessions")).toBeInTheDocument());
    });

    it("renders new session button", async () => {
      renderSidebar([]);
      await waitFor(() => expect(screen.getByTitle("New session")).toBeInTheDocument());
    });

    it("renders nav tabs for Chat and Dash", async () => {
      renderSidebar([]);
      await waitFor(() => {
        expect(screen.getByText("Chat")).toBeInTheDocument();
        expect(screen.getByText("Dash")).toBeInTheDocument();
      });
    });

    it("highlights active page in nav", async () => {
      renderSidebar([]);
      await waitFor(() => {
        const chatBtn = screen.getByText("Chat");
        expect(chatBtn.className).toContain("bg-accent");
      });
    });

    it("renders search input", async () => {
      renderSidebar([]);
      await waitFor(() => expect(screen.getByPlaceholderText("Search...")).toBeInTheDocument());
    });

    it("renders Active and Archive view toggle buttons", async () => {
      renderSidebar([]);
      await waitFor(() => {
        expect(screen.getByText("Active")).toBeInTheDocument();
        expect(screen.getByText("Archive")).toBeInTheDocument();
      });
    });

    it("highlights Active tab by default", async () => {
      renderSidebar([]);
      await waitFor(() => {
        const activeBtn = screen.getByText("Active");
        expect(activeBtn.className).toContain("bg-surface-active");
      });
    });

    it("renders theme selector with all three themes", async () => {
      renderSidebar([]);
      await waitFor(() => {
        expect(screen.getByText("Abyss")).toBeInTheDocument();
        expect(screen.getByText("Temple")).toBeInTheDocument();
        expect(screen.getByText("Clarity")).toBeInTheDocument();
      });
    });

    it("highlights current theme", async () => {
      renderSidebar([]);
      await waitFor(() => {
        const abyssBtn = getFooterThemeButton("Abyss");
        expect(abyssBtn).not.toBeNull();
        expect(abyssBtn?.className).toContain("bg-accent");
      });
    });

    it("renders session count in footer", async () => {
      renderSidebar([]);
      await waitFor(() => expect(screen.getByText("0 sessions")).toBeInTheDocument());
    });

    it("renders collapse button", async () => {
      renderSidebar([]);
      await waitFor(() => expect(screen.getByTitle("Collapse sidebar")).toBeInTheDocument());
    });
  });

  describe("collapsed state", () => {
    it("renders collapsed sidebar with new session button", () => {
      store = makeStore([]);
      render(
        <Sidebar
          sessionStore={store}
          activeSessionId={null}
          onSelectSession={onSelectSession}
          onCreateSession={onCreateSession}
          theme="abyss"
          collapsed={true}
          onToggleCollapsed={jest.fn()}
          activePage="chat"
          onNavigate={onNavigate}
        />
      );
      expect(screen.getByTitle("New session")).toBeInTheDocument();
    });

    it("renders collapsed nav buttons", () => {
      store = makeStore([]);
      render(
        <Sidebar
          sessionStore={store}
          activeSessionId={null}
          onSelectSession={onSelectSession}
          onCreateSession={onCreateSession}
          theme="abyss"
          collapsed={true}
          onToggleCollapsed={jest.fn()}
          activePage="chat"
          onNavigate={onNavigate}
        />
      );
      expect(screen.getByTitle("Chat")).toBeInTheDocument();
      expect(screen.getByTitle("Dashboard")).toBeInTheDocument();
    });

    it("highlights active page in collapsed nav", () => {
      store = makeStore([]);
      render(
        <Sidebar
          sessionStore={store}
          activeSessionId={null}
          onSelectSession={onSelectSession}
          onCreateSession={onCreateSession}
          theme="abyss"
          collapsed={true}
          onToggleCollapsed={jest.fn()}
          activePage="chat"
          onNavigate={onNavigate}
        />
      );
      const chatBtn = screen.getByTitle("Chat");
      expect(chatBtn.className).toContain("bg-accent/20");
    });

    it("renders archive toggle in collapsed state", () => {
      store = makeStore([]);
      render(
        <Sidebar
          sessionStore={store}
          activeSessionId={null}
          onSelectSession={onSelectSession}
          onCreateSession={onCreateSession}
          theme="abyss"
          collapsed={true}
          onToggleCollapsed={jest.fn()}
          activePage="chat"
          onNavigate={onNavigate}
        />
      );
      expect(screen.getByTitle("Show archive")).toBeInTheDocument();
    });

    it("renders theme switcher in collapsed state", () => {
      store = makeStore([]);
      render(
        <Sidebar
          sessionStore={store}
          activeSessionId={null}
          onSelectSession={onSelectSession}
          onCreateSession={onCreateSession}
          theme="abyss"
          collapsed={true}
          onToggleCollapsed={jest.fn()}
          activePage="chat"
          onNavigate={onNavigate}
        />
      );
      expect(screen.getByTitle(/Switch theme/)).toBeInTheDocument();
    });

    it("renders expand button in collapsed state", () => {
      store = makeStore([]);
      render(
        <Sidebar
          sessionStore={store}
          activeSessionId={null}
          onSelectSession={onSelectSession}
          onCreateSession={onCreateSession}
          theme="abyss"
          collapsed={true}
          onToggleCollapsed={jest.fn()}
          activePage="chat"
          onNavigate={onNavigate}
        />
      );
      expect(screen.getByTitle("Expand sidebar")).toBeInTheDocument();
    });
  });

  describe("session list", () => {
    it("shows active sessions section header", async () => {
      renderSidebar([makeSession({ id: "s1", is_active: true })]);
      await waitFor(() => {
        expect(getActiveSectionHeader()).toBeInTheDocument();
      });
    });

    it("shows inactive sessions section header", async () => {
      renderSidebar([makeSession({ id: "s1", is_active: false })]);
      await waitFor(() => {
        expect(getHistorySectionHeader()).toBeInTheDocument();
      });
    });

    it("does not show inactive header when no inactive sessions", async () => {
      renderSidebar([makeSession({ id: "s1", is_active: true })]);
      await waitFor(() => {
        expect(getHistorySectionHeader()).not.toBeInTheDocument();
      });
    });

    it("does not show active header when no active sessions", async () => {
      renderSidebar([makeSession({ id: "s1", is_active: false })]);
      await waitFor(() => {
        expect(getActiveSectionHeader()).not.toBeInTheDocument();
      });
    });

    it("displays session title", async () => {
      renderSidebar([makeSession({ id: "s1", title: "My Session" })]);
      await waitFor(() => expect(screen.getByText("My Session")).toBeInTheDocument());
    });

    it("highlights active session", async () => {
      renderSidebar([makeSession({ id: "s1", title: "My Session" })], { activeSessionId: "s1" });
      await waitFor(() => {
        const sessionSpan = screen.getByText("My Session");
        const sessionBtn = sessionSpan.closest("button");
        expect(sessionBtn?.className).toContain("bg-surface-active");
      });
    });

    it("shows status indicator for active session", async () => {
      renderSidebar([makeSession({ id: "s1", is_active: true, title: "My Session" })]);
      await waitFor(() => expect(screen.getByText("My Session")).toBeInTheDocument());
    });

    it("shows status indicator for failed session", async () => {
      renderSidebar([makeSession({ id: "s1", is_failed: true, title: "My Session" })]);
      await waitFor(() => expect(screen.getByText("My Session")).toBeInTheDocument());
    });

    it("shows status indicator for archived session", async () => {
      // Archived sessions are filtered out in Active view, so switch to Archive view first
      renderSidebar([makeSession({ id: "s1", is_archived: true, title: "My Session" })]);
      await waitFor(() => expect(screen.getByText("Archive")).toBeInTheDocument());
      const archiveBtn = screen.getByText("Archive");
      fireEvent.click(archiveBtn);
      await waitFor(() => expect(screen.getByText("My Session")).toBeInTheDocument());
    });

    it("shows 'No sessions yet' when empty", async () => {
      renderSidebar([]);
      await waitFor(() => expect(screen.getByText("No sessions yet")).toBeInTheDocument());
    });

    it("shows 'No sessions match' when search yields no results", async () => {
      renderSidebar([makeSession({ id: "s1", title: "Hello" })]);
      await waitFor(() => expect(screen.getByText("Hello")).toBeInTheDocument());
      const input = screen.getByPlaceholderText("Search...");
      fireEvent.change(input, { target: { value: "nonexistent" } });
      await waitFor(() => expect(screen.getByText("No sessions match")).toBeInTheDocument());
    });
  });

  describe("navigation", () => {
    it("navigates to chat when Chat tab clicked", async () => {
      renderSidebar([]);
      await waitFor(() => {
        const chatBtn = screen.getByText("Chat");
        fireEvent.click(chatBtn);
        expect(onNavigate).toHaveBeenCalledWith("chat");
      });
    });

    it("navigates to dashboard when Dash tab clicked", async () => {
      renderSidebar([]);
      await waitFor(() => {
        const dashBtn = screen.getByText("Dash");
        fireEvent.click(dashBtn);
        expect(onNavigate).toHaveBeenCalledWith("dashboard");
      });
    });

    it("highlights dashboard tab when active", async () => {
      renderSidebar([], { activePage: "dashboard" });
      await waitFor(() => {
        const dashBtn = screen.getByText("Dash");
        expect(dashBtn.className).toContain("bg-accent");
      });
    });
  });

  describe("theme switching", () => {
    it("cycles theme when theme button clicked", async () => {
      store = makeStore([]);
      render(
        <Sidebar
          sessionStore={store}
          activeSessionId={null}
          onSelectSession={onSelectSession}
          onCreateSession={onCreateSession}
          theme="abyss"
          collapsed={true}
          onToggleCollapsed={jest.fn()}
          activePage="chat"
          onNavigate={onNavigate}
        />
      );
      await waitFor(() => {
        const themeBtn = screen.getByTitle(/Switch theme/);
        fireEvent.click(themeBtn);
      });
    });

    it("switches theme when theme button in footer clicked", async () => {
      renderSidebar([]);
      await waitFor(() => {
        const templeBtn = getFooterThemeButton("Temple");
        expect(templeBtn).not.toBeNull();
        if (templeBtn) fireEvent.click(templeBtn);
      });
    });

    it("highlights selected theme in footer", async () => {
      renderSidebar([], { theme: "temple" });
      await waitFor(() => {
        const templeBtn = getFooterThemeButton("Temple");
        expect(templeBtn).not.toBeNull();
        expect(templeBtn?.className).toContain("bg-accent");
      });
    });
  });

  describe("view toggle", () => {
    it("switches to Archive view", async () => {
      renderSidebar([]);
      await waitFor(() => {
        const archiveBtn = screen.getByText("Archive");
        fireEvent.click(archiveBtn);
        expect(archiveBtn.className).toContain("bg-surface-active");
      });
    });

    it("switches back to Active view", async () => {
      renderSidebar([]);
      await waitFor(() => {
        const archiveBtn = screen.getByText("Archive");
        const activeBtn = screen.getByText("Active");
        fireEvent.click(archiveBtn);
        expect(archiveBtn.className).toContain("bg-surface-active");
        fireEvent.click(activeBtn);
        expect(activeBtn.className).toContain("bg-surface-active");
      });
    });

    it("renders ArchiveBrowser when archive is shown", async () => {
      renderSidebar([]);
      await waitFor(() => {
        const archiveBtn = screen.getByRole("button", { name: "Archive" });
        fireEvent.click(archiveBtn);
        // ArchiveBrowser renders its own "Archive" header as h2
        expect(screen.getByRole("heading", { name: "Archive" })).toBeInTheDocument();
      });
    });
  });

  describe("search", () => {
    it("filters sessions by title", async () => {
      renderSidebar([
        makeSession({ id: "s1", title: "Python session" }),
        makeSession({ id: "s2", title: "Data analysis" }),
      ]);
      await waitFor(() => expect(screen.getByText("Python session")).toBeInTheDocument());
      const input = screen.getByPlaceholderText("Search...");
      fireEvent.change(input, { target: { value: "python" } });
      await waitFor(() => {
        expect(screen.getByText("Python session")).toBeInTheDocument();
        expect(screen.queryByText("Data analysis")).not.toBeInTheDocument();
      });
    });

    it("filters sessions by tag", async () => {
      renderSidebar([
        makeSession({ id: "s1", title: "Session A", tag: "important" }),
        makeSession({ id: "s2", title: "Session B", tag: "draft" }),
      ]);
      await waitFor(() => expect(screen.getByText("Session A")).toBeInTheDocument());
      const input = screen.getByPlaceholderText("Search...");
      fireEvent.change(input, { target: { value: "important" } });
      await waitFor(() => {
        expect(screen.getByText("Session A")).toBeInTheDocument();
        expect(screen.queryByText("Session B")).not.toBeInTheDocument();
      });
    });

    it("clears search when input is cleared", async () => {
      renderSidebar([
        makeSession({ id: "s1", title: "Python session" }),
        makeSession({ id: "s2", title: "Data analysis" }),
      ]);
      await waitFor(() => expect(screen.getByText("Python session")).toBeInTheDocument());
      const input = screen.getByPlaceholderText("Search...");
      fireEvent.change(input, { target: { value: "python" } });
      await waitFor(() => expect(screen.queryByText("Data analysis")).not.toBeInTheDocument());
      fireEvent.change(input, { target: { value: "" } });
      await waitFor(() => expect(screen.getByText("Data analysis")).toBeInTheDocument());
    });
  });

  describe("session actions", () => {
    it("selects session when clicked", async () => {
      renderSidebar([makeSession({ id: "s1", title: "My Session" })]);
      await waitFor(() => {
        const sessionSpan = screen.getByText("My Session");
        const sessionItem = sessionSpan.closest("div, button");
        fireEvent.click(sessionItem!);
        expect(onSelectSession).toHaveBeenCalledWith("s1");
      });
    });

    it("creates new session when new button clicked", async () => {
      renderSidebar([]);
      await waitFor(() => {
        const newBtn = screen.getByTitle("New session");
        fireEvent.click(newBtn);
        expect(onCreateSession).toHaveBeenCalled();
      });
    });

    it("collapses sidebar when collapse button clicked", async () => {
      const onToggle = jest.fn();
      renderSidebar([], { onToggleCollapsed: onToggle });
      await waitFor(() => {
        const collapseBtn = screen.getByTitle("Collapse sidebar");
        fireEvent.click(collapseBtn);
        expect(onToggle).toHaveBeenCalled();
      });
    });
  });

  describe("session count", () => {
    it("shows correct count for multiple sessions", async () => {
      renderSidebar([
        makeSession({ id: "s1" }),
        makeSession({ id: "s2" }),
        makeSession({ id: "s3" }),
      ]);
      await waitFor(() => expect(screen.getByText("3 sessions")).toBeInTheDocument());
    });

    it("shows singular 'session' for one session", async () => {
      renderSidebar([makeSession({ id: "s1" })]);
      await waitFor(() => expect(screen.getByText("1 session")).toBeInTheDocument());
    });
  });

  describe("archived session visibility", () => {
    it("hides archived sessions in Active view", async () => {
      // Archived sessions are filtered out in Active view
      renderSidebar([
        makeSession({ id: "s1", is_archived: true, title: "Archived Session" }),
        makeSession({ id: "s2", is_archived: false, title: "Active Session" }),
      ]);
      await waitFor(() => {
        // Use role-based selector to get the tab button specifically
        const activeBtn = screen.getByRole("button", { name: "Active" });
        expect(activeBtn).toBeInTheDocument();
        expect(screen.queryByText("Archived Session")).not.toBeInTheDocument();
      });
    });

    it("shows archived sessions in Archive view", async () => {
      renderSidebar([makeSession({ id: "s1", is_archived: true, title: "Archived" })]);
      await waitFor(() => {
        const archiveBtn = screen.getByText("Archive");
        fireEvent.click(archiveBtn);
        expect(screen.getByText("Archived")).toBeInTheDocument();
      });
    });
  });

  describe("theme info", () => {
    it("shows theme description in title", async () => {
      store = makeStore([]);
      render(
        <Sidebar
          sessionStore={store}
          activeSessionId={null}
          onSelectSession={onSelectSession}
          onCreateSession={onCreateSession}
          theme="abyss"
          collapsed={true}
          onToggleCollapsed={jest.fn()}
          activePage="chat"
          onNavigate={onNavigate}
        />
      );
      await waitFor(() => {
        const themeBtn = screen.getByTitle(/Switch theme/);
        expect(themeBtn.title).toContain("Abyss");
      });
    });

    it("shows correct theme icon", async () => {
      store = makeStore([]);
      render(
        <Sidebar
          sessionStore={store}
          activeSessionId={null}
          onSelectSession={onSelectSession}
          onCreateSession={onCreateSession}
          theme="abyss"
          collapsed={true}
          onToggleCollapsed={jest.fn()}
          activePage="chat"
          onNavigate={onNavigate}
        />
      );
      await waitFor(() => {
        const themeBtn = screen.getByTitle(/Switch theme/);
        expect(themeBtn).toHaveTextContent("🌑");
      });
    });
  });
});
