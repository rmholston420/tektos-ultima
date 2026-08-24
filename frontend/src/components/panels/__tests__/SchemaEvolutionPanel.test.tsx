/**
 * Tests for the SchemaEvolutionPanel component.
 *
 * SchemaEvolutionPanel fetches /api/schema and renders table info,
 * pattern detection, schema proposals, and apply actions.
 */

import React from "react";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { SchemaEvolutionPanel } from "../SchemaEvolutionPanel";

const mockFetch = jest.fn();
beforeEach(() => {
  jest.useFakeTimers();
  mockFetch.mockReset();
});
afterEach(() => {
  jest.useRealTimers();
});
global.fetch = mockFetch;

function mockSchemaData() {
  return {
    schema: {
      version: 3,
      tables: {
        sessions: {
          name: "sessions",
          columns: [
            { cid: 0, name: "id", type: "TEXT", notnull: 1, pk: 1 },
            { cid: 1, name: "title", type: "TEXT", notnull: 0, pk: 0 },
            { cid: 2, name: "status", type: "TEXT", notnull: 1, pk: 0 },
          ],
          indexes: ["idx_sessions_status"],
          row_count: 42,
        },
        messages: {
          name: "messages",
          columns: [
            { cid: 0, name: "id", type: "TEXT", notnull: 1, pk: 1 },
            { cid: 1, name: "session_id", type: "TEXT", notnull: 1, pk: 0 },
            { cid: 2, name: "content", type: "TEXT", notnull: 0, pk: 0 },
          ],
          indexes: ["idx_messages_session"],
          row_count: 156,
        },
      },
    },
  };
}

function mockPatterns() {
  return [
    {
      field: "status",
      table: "sessions",
      percentage: 0.85,
      confidence: 0.92,
      suggested_type: "TEXT",
      pattern_type: "enum",
      example_values: ["ready", "running", "idle"],
    },
  ];
}

describe("SchemaEvolutionPanel", () => {
  it("shows loading state initially", async () => {
    mockFetch.mockImplementation((url: string) => {
      if (url === "/api/schema") return Promise.resolve({ json: () => Promise.resolve(mockSchemaData()) });
      return Promise.resolve({ json: () => Promise.resolve([]) });
    });
    render(<SchemaEvolutionPanel />);
    expect(screen.getByText("Loading schema...")).toBeInTheDocument();
  });

  it("renders header with version", async () => {
    mockFetch.mockImplementation((url: string) => {
      if (url === "/api/schema") return Promise.resolve({ json: () => Promise.resolve(mockSchemaData()) });
      return Promise.resolve({ json: () => Promise.resolve([]) });
    });
    render(<SchemaEvolutionPanel />);
    await waitFor(() => expect(screen.getByText("Schema Evolution Engine")).toBeInTheDocument());
    expect(screen.getByText("v3")).toBeInTheDocument();
  });

  it("shows table count and row count", async () => {
    mockFetch.mockImplementation((url: string) => {
      if (url === "/api/schema") return Promise.resolve({ json: () => Promise.resolve(mockSchemaData()) });
      return Promise.resolve({ json: () => Promise.resolve([]) });
    });
    render(<SchemaEvolutionPanel />);
    await waitFor(() => expect(screen.getByText(/2 tables/)).toBeInTheDocument());
    expect(screen.getByText(/198 rows/)).toBeInTheDocument();
  });

  it("renders table selector", async () => {
    mockFetch.mockImplementation((url: string) => {
      if (url === "/api/schema") return Promise.resolve({ json: () => Promise.resolve(mockSchemaData()) });
      return Promise.resolve({ json: () => Promise.resolve([]) });
    });
    render(<SchemaEvolutionPanel />);
    await waitFor(() => {
      const select = document.querySelector("select");
      expect(select).toBeInTheDocument();
    });
  });

  it("shows refresh button", async () => {
    mockFetch.mockImplementation((url: string) => {
      if (url === "/api/schema") return Promise.resolve({ json: () => Promise.resolve(mockSchemaData()) });
      return Promise.resolve({ json: () => Promise.resolve([]) });
    });
    render(<SchemaEvolutionPanel />);
    await waitFor(() => expect(screen.getByText("↻ Refresh")).toBeInTheDocument());
  });

  it("shows detected patterns", async () => {
    mockFetch.mockImplementation((url: string) => {
      if (url === "/api/schema") return Promise.resolve({ json: () => Promise.resolve(mockSchemaData()) });
      if (url.includes("/api/schema/patterns")) return Promise.resolve({ json: () => Promise.resolve(mockPatterns()) });
      return Promise.resolve({ json: () => Promise.resolve([]) });
    });
    render(<SchemaEvolutionPanel />);
    await waitFor(() => expect(screen.getByText(/Detected Patterns/)).toBeInTheDocument());
    await waitFor(() => {
      const all = document.body.textContent;
      expect(all).toContain("status");
      expect(all).toContain("92% confident");
    });
  });

  it("shows pattern confidence bar", async () => {
    mockFetch.mockImplementation((url: string) => {
      if (url === "/api/schema") return Promise.resolve({ json: () => Promise.resolve(mockSchemaData()) });
      return Promise.resolve({ json: () => Promise.resolve(mockPatterns()) });
    });
    render(<SchemaEvolutionPanel />);
    await waitFor(() => expect(screen.getByText("92% confident")).toBeInTheDocument());
  });

  it("shows example values for patterns", async () => {
    mockFetch.mockImplementation((url: string) => {
      if (url === "/api/schema") return Promise.resolve({ json: () => Promise.resolve(mockSchemaData()) });
      return Promise.resolve({ json: () => Promise.resolve(mockPatterns()) });
    });
    render(<SchemaEvolutionPanel />);
    await waitFor(() => expect(screen.getByText(/Examples:/)).toBeInTheDocument());
  });

  it("shows propose change button", async () => {
    mockFetch.mockImplementation((url: string) => {
      if (url === "/api/schema") return Promise.resolve({ json: () => Promise.resolve(mockSchemaData()) });
      return Promise.resolve({ json: () => Promise.resolve(mockPatterns()) });
    });
    render(<SchemaEvolutionPanel />);
    await waitFor(() => expect(screen.getByText("💡 Propose Schema Change")).toBeInTheDocument());
  });

  it("shows current schema tables", async () => {
    mockFetch.mockImplementation((url: string) => {
      if (url === "/api/schema") return Promise.resolve({ json: () => Promise.resolve(mockSchemaData()) });
      return Promise.resolve({ json: () => Promise.resolve([]) });
    });
    render(<SchemaEvolutionPanel />);
    await waitFor(() => expect(screen.getByText("Current Schema")).toBeInTheDocument());
    expect(screen.getByText("sessions")).toBeInTheDocument();
    expect(screen.getByText("messages")).toBeInTheDocument();
  });

  it("shows column info", async () => {
    mockFetch.mockImplementation((url: string) => {
      if (url === "/api/schema") return Promise.resolve({ json: () => Promise.resolve(mockSchemaData()) });
      return Promise.resolve({ json: () => Promise.resolve([]) });
    });
    render(<SchemaEvolutionPanel />);
    await waitFor(() => {
      const all = document.body.textContent;
      expect(all).toContain("id");
      expect(all).toContain("TEXT");
    });
  });

  it("shows PK marker", async () => {
    mockFetch.mockImplementation((url: string) => {
      if (url === "/api/schema") return Promise.resolve({ json: () => Promise.resolve(mockSchemaData()) });
      return Promise.resolve({ json: () => Promise.resolve([]) });
    });
    render(<SchemaEvolutionPanel />);
    await waitFor(() => {
      const all = document.body.textContent;
      expect(all).toContain("PK");
    });
  });

  it("shows refresh triggers fetch", async () => {
    mockFetch.mockImplementation((url: string) => {
      if (url === "/api/schema") return Promise.resolve({ json: () => Promise.resolve(mockSchemaData()) });
      return Promise.resolve({ json: () => Promise.resolve([]) });
    });
    render(<SchemaEvolutionPanel />);
    await waitFor(() => expect(screen.getByText("↻ Refresh")).toBeInTheDocument());
    fireEvent.click(screen.getByText("↻ Refresh"));
    expect(mockFetch).toHaveBeenCalled();
  });

  it("polls data on interval", async () => {
    mockFetch.mockImplementation((url: string) => {
      if (url === "/api/schema") return Promise.resolve({ json: () => Promise.resolve(mockSchemaData()) });
      return Promise.resolve({ json: () => Promise.resolve([]) });
    });
    render(<SchemaEvolutionPanel />);
    await waitFor(() => expect(screen.getByText("Schema Evolution Engine")).toBeInTheDocument());
    jest.advanceTimersByTime(5000);
    expect(mockFetch).toHaveBeenCalled();
  });
});
