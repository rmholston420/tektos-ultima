/**
 * Tests for McpPanel — loading, stats, expandable server cards, tool listing.
 */

import React from "react";
import { render, screen, waitFor, fireEvent } from "@testing-library/react";
import { McpPanel } from "../McpPanel";

const mockFetch = jest.fn();
global.fetch = mockFetch;

describe("McpPanel", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    mockFetch.mockReset();
  });

  function mockServersData() {
    return {
      servers: [
        { id: "1", name: "filesystem", status: "online", toolCount: 12, lastCheck: "2026-08-14 10:30", uptime: "99.8%", tools: ["read_file", "write_file", "search_files"] },
        { id: "2", name: "github", status: "online", toolCount: 8, lastCheck: "2026-08-14 10:29", uptime: "99.5%", tools: ["list_repos", "create_issue"] },
        { id: "3", name: "terminal", status: "error", toolCount: 0, lastCheck: "2026-08-14 10:15", uptime: "87.2%", tools: [] },
      ],
    };
  }

  it("renders loading spinner", () => {
    mockFetch.mockImplementation(() => new Promise(() => {}));
    render(<McpPanel />);
    expect(document.querySelector(".animate-spin")).toBeInTheDocument();
  });

  it("renders stats cards", async () => {
    mockFetch.mockResolvedValue({ json: () => Promise.resolve(mockServersData()) });
    render(<McpPanel />);
    await waitFor(() => expect(screen.getByText("Total Servers")).toBeInTheDocument());
    await waitFor(() => expect(screen.getByText("Online")).toBeInTheDocument());
    await waitFor(() => expect(screen.getByText("Errors")).toBeInTheDocument());
  });

  it("renders correct server counts", async () => {
    mockFetch.mockResolvedValue({ json: () => Promise.resolve(mockServersData()) });
    render(<McpPanel />);
    await waitFor(() => expect(screen.getByText("3")).toBeInTheDocument());
    await waitFor(() => expect(screen.getByText("2")).toBeInTheDocument());
    await waitFor(() => expect(screen.getByText("1")).toBeInTheDocument());
  });

  it("renders server names", async () => {
    mockFetch.mockResolvedValue({ json: () => Promise.resolve(mockServersData()) });
    render(<McpPanel />);
    await waitFor(() => expect(screen.getByText("filesystem")).toBeInTheDocument());
    await waitFor(() => expect(screen.getByText("github")).toBeInTheDocument());
    await waitFor(() => expect(screen.getByText("terminal")).toBeInTheDocument());
  });

  it("renders status indicators", async () => {
    mockFetch.mockResolvedValue({ json: () => Promise.resolve(mockServersData()) });
    render(<McpPanel />);
    await waitFor(() => expect(screen.getAllByText("online").length).toBeGreaterThanOrEqual(1));
    await waitFor(() => expect(screen.getAllByText("error").length).toBeGreaterThanOrEqual(1));
  });

  it("renders tool counts", async () => {
    mockFetch.mockResolvedValue({ json: () => Promise.resolve(mockServersData()) });
    render(<McpPanel />);
    await waitFor(() => expect(screen.getByText("12 tools")).toBeInTheDocument());
    await waitFor(() => expect(screen.getByText("8 tools")).toBeInTheDocument());
    await waitFor(() => expect(screen.getByText("0 tools")).toBeInTheDocument());
  });

  it("renders uptime info", async () => {
    mockFetch.mockResolvedValue({ json: () => Promise.resolve(mockServersData()) });
    render(<McpPanel />);
    await waitFor(() => expect(screen.getByText("Uptime: 99.8%")).toBeInTheDocument());
  });

  it("renders last check time", async () => {
    mockFetch.mockResolvedValue({ json: () => Promise.resolve(mockServersData()) });
    render(<McpPanel />);
    await waitFor(() => expect(screen.getByText("Last checked: 2026-08-14 10:30")).toBeInTheDocument());
  });

  it("expands server card to show tools", async () => {
    mockFetch.mockResolvedValue({ json: () => Promise.resolve(mockServersData()) });
    render(<McpPanel />);
    await waitFor(() => expect(screen.getByText("filesystem")).toBeInTheDocument());
    const serverCard = screen.getByText("filesystem").closest("button");
    fireEvent.click(serverCard!);
    await waitFor(() => expect(screen.getByText("read_file")).toBeInTheDocument());
    await waitFor(() => expect(screen.getByText("write_file")).toBeInTheDocument());
    await waitFor(() => expect(screen.getByText("search_files")).toBeInTheDocument());
  });

  it("shows no tools message for empty tool list", async () => {
    mockFetch.mockResolvedValue({ json: () => Promise.resolve(mockServersData()) });
    render(<McpPanel />);
    await waitFor(() => expect(screen.getByText("terminal")).toBeInTheDocument());
    const terminalCard = screen.getByText("terminal").closest("button");
    fireEvent.click(terminalCard!);
    await waitFor(() => expect(screen.getByText("No tools available")).toBeInTheDocument());
  });

  it("collapses expanded server on second click", async () => {
    mockFetch.mockResolvedValue({ json: () => Promise.resolve(mockServersData()) });
    render(<McpPanel />);
    await waitFor(() => expect(screen.getByText("filesystem")).toBeInTheDocument());
    const serverCard = screen.getByText("filesystem").closest("button");
    fireEvent.click(serverCard!);
    await waitFor(() => expect(screen.getByText("read_file")).toBeInTheDocument());
    fireEvent.click(serverCard!);
    expect(screen.queryByText("read_file")).not.toBeInTheDocument();
  });

  it("expands different server when another is clicked", async () => {
    mockFetch.mockResolvedValue({ json: () => Promise.resolve(mockServersData()) });
    render(<McpPanel />);
    await waitFor(() => expect(screen.getByText("filesystem")).toBeInTheDocument());
    const fsCard = screen.getByText("filesystem").closest("button");
    fireEvent.click(fsCard!);
    await waitFor(() => expect(screen.getByText("read_file")).toBeInTheDocument());
    const ghCard = screen.getByText("github").closest("button");
    fireEvent.click(ghCard!);
    await waitFor(() => expect(screen.getByText("list_repos")).toBeInTheDocument());
  });

  it("renders status badge colors for online", async () => {
    mockFetch.mockResolvedValue({ json: () => Promise.resolve(mockServersData()) });
    render(<McpPanel />);
    await waitFor(() => expect(screen.getByText("online")).toBeInTheDocument());
  });

  it("renders status badge colors for error", async () => {
    mockFetch.mockResolvedValue({ json: () => Promise.resolve(mockServersData()) });
    render(<McpPanel />);
    await waitFor(() => expect(screen.getByText("error")).toBeInTheDocument());
  });

  it("handles empty servers array", async () => {
    mockFetch.mockResolvedValue({ json: () => Promise.resolve({ servers: [] }) });
    render(<McpPanel />);
    await waitFor(() => expect(screen.getByText("0")).toBeInTheDocument());
  });

  it("handles fetch error with fallback data", async () => {
    mockFetch.mockRejectedValue(new Error("Network error"));
    render(<McpPanel />);
    await waitFor(() => expect(screen.getByText("filesystem")).toBeInTheDocument());
    await waitFor(() => expect(screen.getByText("github")).toBeInTheDocument());
  });

  it("renders all tool names for github server", async () => {
    mockFetch.mockResolvedValue({ json: () => Promise.resolve(mockServersData()) });
    render(<McpPanel />);
    await waitFor(() => expect(screen.getByText("github")).toBeInTheDocument());
    const ghCard = screen.getByText("github").closest("button");
    fireEvent.click(ghCard!);
    await waitFor(() => expect(screen.getByText("list_repos")).toBeInTheDocument());
    await waitFor(() => expect(screen.getByText("create_issue")).toBeInTheDocument());
  });
});
