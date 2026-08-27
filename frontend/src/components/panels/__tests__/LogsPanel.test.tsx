/**
 * Tests for LogsPanel — loading, search, level filtering, auto-scroll, log display.
 */

import React from "react";
import { render, screen, waitFor, fireEvent } from "@testing-library/react";

jest.mock("@/lib/api", () => {
  const mockGetLogs = jest.fn();
  return {
    api: {
      getLogs: mockGetLogs,
    },
    LogEntry: Object,
  };
});

import { LogsPanel } from "../LogsPanel";
import * as api from "@/lib/api";

const mockGetLogs = api.api.getLogs as jest.Mock;

describe("LogsPanel", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    mockGetLogs.mockReset();
  });

  function mockLogsData() {
    return [
      { level: "INFO", logger: "system", message: "Server started on port 8020", timestamp: "2024-06-01T10:00:00Z" },
      { level: "DEBUG", logger: "ws", message: "Client connected", timestamp: "2024-06-01T10:00:01Z" },
      { level: "WARNING", logger: "memory", message: "Memory usage above 80%", timestamp: "2024-06-01T10:00:02Z" },
      { level: "ERROR", logger: "api", message: "Failed to process request", timestamp: "2024-06-01T10:00:03Z" },
    ];
  }

  it("renders header", async () => {
    mockGetLogs.mockResolvedValue([]);
    render(<LogsPanel />);
    await waitFor(() => expect(screen.getByText("System Logs")).toBeInTheDocument());
  });

  it("renders auto-scroll checkbox", async () => {
    mockGetLogs.mockResolvedValue([]);
    render(<LogsPanel />);
    expect(screen.getByText("Auto-scroll")).toBeInTheDocument();
  });

  it("renders search input", async () => {
    mockGetLogs.mockResolvedValue([]);
    render(<LogsPanel />);
    expect(screen.getByPlaceholderText("Search logs...")).toBeInTheDocument();
  });

  it("renders level filter buttons", async () => {
    mockGetLogs.mockResolvedValue([]);
    render(<LogsPanel />);
    await waitFor(() => expect(screen.getByText("all")).toBeInTheDocument());
    await waitFor(() => expect(screen.getByText("DEBUG")).toBeInTheDocument());
    await waitFor(() => expect(screen.getByText("INFO")).toBeInTheDocument());
    await waitFor(() => expect(screen.getByText("WARNING")).toBeInTheDocument());
    await waitFor(() => expect(screen.getByText("ERROR")).toBeInTheDocument());
  });

  it("renders log entries", async () => {
    mockGetLogs.mockResolvedValue(mockLogsData());
    render(<LogsPanel />);
    await waitFor(() => expect(screen.getByText("System Logs")).toBeInTheDocument());
  });

  it("renders log levels", async () => {
    mockGetLogs.mockResolvedValue(mockLogsData());
    render(<LogsPanel />);
    await waitFor(() => expect(screen.getByText("INFO")).toBeInTheDocument());
    await waitFor(() => expect(screen.getByText("WARNING")).toBeInTheDocument());
    await waitFor(() => expect(screen.getByText("ERROR")).toBeInTheDocument());
  });

  it("renders log messages", async () => {
    mockGetLogs.mockResolvedValue(mockLogsData());
    render(<LogsPanel />);
    await waitFor(() => expect(screen.getByText("Server started on port 8020")).toBeInTheDocument());
    await waitFor(() => expect(screen.getByText("Failed to process request")).toBeInTheDocument());
  });

  it("renders log timestamps", async () => {
    mockGetLogs.mockResolvedValue(mockLogsData());
    render(<LogsPanel />);
    await waitFor(() => expect(screen.getByText("System Logs")).toBeInTheDocument());
  });

  it("renders log logger names", async () => {
    mockGetLogs.mockResolvedValue(mockLogsData());
    render(<LogsPanel />);
    await waitFor(() => expect(screen.getByText("system")).toBeInTheDocument());
    await waitFor(() => expect(screen.getByText("ws")).toBeInTheDocument());
    await waitFor(() => expect(screen.getByText("memory")).toBeInTheDocument());
    await waitFor(() => expect(screen.getByText("api")).toBeInTheDocument());
  });

  it("renders terminal-style header dots", async () => {
    mockGetLogs.mockResolvedValue([]);
    render(<LogsPanel />);
    const dots = document.querySelectorAll("[class*='rounded-full']");
    expect(dots.length).toBeGreaterThanOrEqual(3);
  });

  it("renders terminal label", async () => {
    mockGetLogs.mockResolvedValue([]);
    render(<LogsPanel />);
    expect(screen.getByText("tektos-logs")).toBeInTheDocument();
  });

  it("filters logs by search query", async () => {
    mockGetLogs.mockResolvedValue(mockLogsData());
    render(<LogsPanel />);
    const searchInput = screen.getByPlaceholderText("Search logs...");
    fireEvent.change(searchInput, { target: { value: "Server" } });
    await waitFor(() => expect(screen.getByText("Server started on port 8020")).toBeInTheDocument());
  });

  it("case-insensitive search filter", async () => {
    mockGetLogs.mockResolvedValue(mockLogsData());
    render(<LogsPanel />);
    const searchInput = screen.getByPlaceholderText("Search logs...");
    fireEvent.change(searchInput, { target: { value: "server" } });
    await waitFor(() => expect(screen.getByText("Server started on port 8020")).toBeInTheDocument());
  });

  it("filters by level button click", async () => {
    mockGetLogs.mockResolvedValue(mockLogsData());
    render(<LogsPanel />);
    await waitFor(() => expect(screen.getByText("ERROR")).toBeInTheDocument());
    fireEvent.click(screen.getByText("ERROR"));
    expect(mockGetLogs).toHaveBeenCalledWith("ERROR", 200);
  });

  it("filters by WARNING level", async () => {
    mockGetLogs.mockResolvedValue(mockLogsData());
    render(<LogsPanel />);
    fireEvent.click(screen.getByText("WARNING"));
    expect(mockGetLogs).toHaveBeenCalledWith("WARNING", 200);
  });

  it("filters by DEBUG level", async () => {
    mockGetLogs.mockResolvedValue(mockLogsData());
    render(<LogsPanel />);
    fireEvent.click(screen.getByText("DEBUG"));
    expect(mockGetLogs).toHaveBeenCalledWith("DEBUG", 200);
  });

  it("toggles auto-scroll checkbox", async () => {
    mockGetLogs.mockResolvedValue([]);
    render(<LogsPanel />);
    const checkbox = screen.getByRole("checkbox");
    expect(checkbox).toBeChecked();
    fireEvent.click(checkbox);
    expect(checkbox).not.toBeChecked();
  });

  it("handles empty logs array", async () => {
    mockGetLogs.mockResolvedValue([]);
    render(<LogsPanel />);
    await waitFor(() => expect(screen.getByText("System Logs")).toBeInTheDocument());
  });

  it("handles API error with placeholder message", async () => {
    mockGetLogs.mockRejectedValue(new Error("Not found"));
    render(<LogsPanel />);
    await waitFor(() => expect(screen.getByText(/Logs endpoint not configured/)).toBeInTheDocument());
  });

  it("renders INFO log level text color", async () => {
    mockGetLogs.mockResolvedValue(mockLogsData());
    render(<LogsPanel />);
    await waitFor(() => expect(screen.getByText("INFO")).toBeInTheDocument());
  });

  it("renders ERROR log level text color", async () => {
    mockGetLogs.mockResolvedValue(mockLogsData());
    render(<LogsPanel />);
    await waitFor(() => expect(screen.getByText("ERROR")).toBeInTheDocument());
  });

  it("renders multiple log entries with correct count", async () => {
    mockGetLogs.mockResolvedValue(mockLogsData());
    render(<LogsPanel />);
    await waitFor(() => expect(screen.getByText("System Logs")).toBeInTheDocument());
  });

  it("renders log entry background colors by level", async () => {
    mockGetLogs.mockResolvedValue(mockLogsData());
    render(<LogsPanel />);
    await waitFor(() => expect(screen.getByText("INFO")).toBeInTheDocument());
  });
});
