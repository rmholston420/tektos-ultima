/**
 * Tests for DatabasePanel — loading state, tab switching, data display.
 */

import React from "react";
import { render, screen, waitFor, fireEvent } from "@testing-library/react";
import { DatabasePanel } from "../DatabasePanel";

const mockFetch = jest.fn();
global.fetch = mockFetch;

describe("DatabasePanel", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    mockFetch.mockReset();
  });

  function mockDbResponse() {
    return {
      stats: { tables: 3, total_rows: 1500, total_size_bytes: 524288, indexes: 5, last_vacuum: "2024-01-01", journal_mode: "WAL" },
      schema: { tables: {
        users: { columns: [{ name: "id", type: "INTEGER", notnull: true, pk: true, default: null }], indexes: [], row_count: 100, size_bytes: 16384 },
        sessions: { columns: [{ name: "id", type: "TEXT", notnull: true, pk: true, default: null }], indexes: [{ name: "idx_session", columns: ["session_id"], unique: false }], row_count: 500, size_bytes: 32768 },
        messages: { columns: [{ name: "id", type: "INTEGER", notnull: true, pk: true, default: null }], indexes: [], row_count: 900, size_bytes: 475136 },
      }},
      analyses: {
        users: { table: "users", row_count: 100, column_stats: {}, missing_indexes: [], duplicate_indexes: [], suggestions: ["Add index on email"], data_quality_issues: [] },
        sessions: { table: "sessions", row_count: 500, column_stats: {}, missing_indexes: ["session_id"], duplicate_indexes: [], suggestions: [], data_quality_issues: [] },
        messages: { table: "messages", row_count: 900, column_stats: {}, missing_indexes: [], duplicate_indexes: [], suggestions: [], data_quality_issues: [{ column: "content", issue: "NULL values", severity: "warning" }] },
      },
      backups: [
        { path: "/backups/db_20240101.sqlite", timestamp: 1704067200, size_bytes: 524288, table_count: 3, row_count: 1500, checksum: "abc123def456" },
      ],
    };
  }

  function setupMock(data: ReturnType<typeof mockDbResponse>) {
    mockFetch.mockImplementation((url: string) => {
      if (url.includes("/api/db/schema")) return Promise.resolve({ ok: true, json: () => Promise.resolve(data.schema) });
      if (url.includes("/api/db/analyze")) return Promise.resolve({ ok: true, json: () => Promise.resolve(data.analyses) });
      if (url.includes("/api/db/backups")) return Promise.resolve({ ok: true, json: () => Promise.resolve(data.backups) });
      if (url.includes("/api/db")) return Promise.resolve({ ok: true, json: () => Promise.resolve(data.stats) });
      return Promise.resolve({ ok: false });
    });
  }

  it("renders loading state", () => {
    mockFetch.mockImplementation(() => new Promise(() => {}));
    render(<DatabasePanel />);
    expect(screen.getByText("Loading database...")).toBeInTheDocument();
  });

  it("renders overview cards with data", async () => {
    const data = mockDbResponse();
    setupMock(data);
    render(<DatabasePanel />);
    await waitFor(() => expect(screen.getByText("Tables")).toBeInTheDocument());
    await waitFor(() => expect(screen.getByText("3")).toBeInTheDocument());
    await waitFor(() => expect(screen.getByText("Total Rows")).toBeInTheDocument());
    await waitFor(() => expect(screen.getByText("Indexes")).toBeInTheDocument());
  });

  it("renders schema tab with tables", async () => {
    const data = mockDbResponse();
    setupMock(data);
    render(<DatabasePanel />);
    await waitFor(() => expect(screen.getByText(/Schema/)).toBeInTheDocument());
    await waitFor(() => expect(screen.getByText("users")).toBeInTheDocument());
    await waitFor(() => expect(screen.getByText("sessions")).toBeInTheDocument());
    await waitFor(() => expect(screen.getByText("messages")).toBeInTheDocument());
  });

  it("renders analysis tab with suggestions", async () => {
    const data = mockDbResponse();
    setupMock(data);
    render(<DatabasePanel />);
    await waitFor(() => expect(screen.getByText(/Analysis/)).toBeInTheDocument());
    const analysisTab = screen.getByText(/Analysis/);
    fireEvent.click(analysisTab);
    await waitFor(() => expect(screen.getByText("Suggestions")).toBeInTheDocument());
    await waitFor(() => expect(screen.getByText("Add index on email")).toBeInTheDocument());
  });

  it("renders backups tab", async () => {
    const data = mockDbResponse();
    setupMock(data);
    render(<DatabasePanel />);
    await waitFor(() => expect(screen.getByText(/Backups/)).toBeInTheDocument());
    const backupsTab = screen.getByText(/Backups/);
    fireEvent.click(backupsTab);
    await waitFor(() => expect(screen.getByText("db_20240101.sqlite")).toBeInTheDocument());
  });

  it("renders database configuration section", async () => {
    const data = mockDbResponse();
    setupMock(data);
    render(<DatabasePanel />);
    await waitFor(() => expect(screen.getByText("Database Configuration")).toBeInTheDocument());
    await waitFor(() => expect(screen.getByText("Journal Mode")).toBeInTheDocument());
    await waitFor(() => expect(screen.getByText("WAL")).toBeInTheDocument());
  });

  it("handles fetch error gracefully", async () => {
    mockFetch.mockRejectedValueOnce(new Error("Network error"));
    const consoleSpy = jest.spyOn(console, "error").mockImplementation(() => {});
    render(<DatabasePanel />);
    await waitFor(() => expect(screen.queryByText("Loading database...")).not.toBeInTheDocument());
    consoleSpy.mockRestore();
  });

  it("renders empty tables message when no tables", async () => {
    const data = mockDbResponse();
    data.stats.tables = 0;
    data.stats.total_rows = 0;
    data.stats.total_size_bytes = 0;
    data.stats.indexes = 0;
    data.schema.tables = {} as typeof data.schema.tables;
    setupMock(data);
    render(<DatabasePanel />);
    await waitFor(() => expect(screen.getByText(/Schema/)).toBeInTheDocument());
    await waitFor(() => expect(screen.getByText("No tables found")).toBeInTheDocument());
  });

  it("renders data quality issues with severity colors", async () => {
    const data = mockDbResponse();
    data.analyses.messages.data_quality_issues = [
      { column: "content", issue: "NULL values", severity: "warning" },
      { column: "user_id", issue: "Missing foreign key", severity: "critical" },
    ];
    setupMock(data);
    render(<DatabasePanel />);
    await waitFor(() => expect(screen.getByText(/Analysis/)).toBeInTheDocument());
    const analysisTab = screen.getByText(/Analysis/);
    fireEvent.click(analysisTab);
    await waitFor(() => expect(screen.getByText("Data Quality Issues")).toBeInTheDocument());
  });

  it("renders healthy table message when no issues", async () => {
    const data = mockDbResponse();
    data.analyses.users = {
      table: "users", row_count: 100, column_stats: {},
      missing_indexes: [], duplicate_indexes: [],
      suggestions: [], data_quality_issues: [],
    };
    setupMock(data);
    render(<DatabasePanel />);
    await waitFor(() => expect(screen.getByText(/Analysis/)).toBeInTheDocument());
    const analysisTab = screen.getByText(/Analysis/);
    fireEvent.click(analysisTab);
    await waitFor(() => expect(screen.getByText(/Table looks healthy/)).toBeInTheDocument());
  });

  it("renders column info with PK indicator", async () => {
    const data = mockDbResponse();
    setupMock(data);
    render(<DatabasePanel />);
    await waitFor(() => expect(screen.getByText("users")).toBeInTheDocument());
    const usersRow = screen.getByText("users");
    fireEvent.click(usersRow);
    await waitFor(() => expect(screen.getByText("id")).toBeInTheDocument());
  });

  it("renders index badges", async () => {
    const data = mockDbResponse();
    setupMock(data);
    render(<DatabasePanel />);
    await waitFor(() => expect(screen.getByText("sessions")).toBeInTheDocument());
    const sessionsRow = screen.getByText("sessions");
    fireEvent.click(sessionsRow);
    await waitFor(() => expect(screen.getByText("idx_session")).toBeInTheDocument());
  });

  it("renders backup checksum truncated", async () => {
    const data = mockDbResponse();
    setupMock(data);
    render(<DatabasePanel />);
    await waitFor(() => expect(screen.getByText(/Backups/)).toBeInTheDocument());
    const backupsTab = screen.getByText(/Backups/);
    fireEvent.click(backupsTab);
    await waitFor(() => expect(screen.getByText("abc123def456")).toBeInTheDocument());
  });

  it("renders no backups message when empty", async () => {
    const data = mockDbResponse();
    data.backups = [];
    setupMock(data);
    render(<DatabasePanel />);
    await waitFor(() => expect(screen.getByText(/Backups/)).toBeInTheDocument());
    const backupsTab = screen.getByText(/Backups/);
    fireEvent.click(backupsTab);
    await waitFor(() => expect(screen.getByText("No backups found")).toBeInTheDocument());
  });
});
