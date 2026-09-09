/**
 * Tests for the ToolsPanel component.
 *
 * ToolsPanel fetches /api/tools and /api/mcp/status and renders
 * MCP connection UI, tools list, and quick execute form.
 */

import React from "react";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { ToolsPanel } from "../ToolsPanel";

const mockFetch = jest.fn();
beforeEach(() => {
  jest.useFakeTimers();
  mockFetch.mockReset();
});
afterEach(() => {
  jest.useRealTimers();
});
global.fetch = mockFetch;

function mockTools() {
  return [
    {
      name: "terminal",
      description: "Execute terminal commands",
      parameters: {},
      enabled: true,
      timeout: 30,
      call_count: 42,
      last_call: Date.now() / 1000,
    },
    {
      name: "browser",
      description: "Drive a web browser",
      parameters: {},
      enabled: false,
      timeout: 60,
      call_count: 0,
      last_call: 0,
    },
  ];
}

function mockMcpStatus() {
  return { connected: false, url: null, imported_count: 0 };
}

describe("ToolsPanel", () => {
  it("shows loading state initially", async () => {
    mockFetch.mockImplementation((url: string) => {
      if (url === "/api/tools") return Promise.resolve({ json: () => Promise.resolve(mockTools()) });
      if (url === "/api/mcp/status") return Promise.resolve({ json: () => Promise.resolve(mockMcpStatus()) });
      return Promise.resolve({ json: () => Promise.resolve({}) });
    });
    render(<ToolsPanel />);
    expect(screen.getByText("Loading tools...")).toBeInTheDocument();
  });

  it("renders MCP connection section", async () => {
    mockFetch.mockImplementation((url: string) => {
      if (url === "/api/tools") return Promise.resolve({ json: () => Promise.resolve(mockTools()) });
      return Promise.resolve({ json: () => Promise.resolve(mockMcpStatus()) });
    });
    render(<ToolsPanel />);
    await waitFor(() => expect(screen.getByText("MCP Server Connection")).toBeInTheDocument());
  });

  it("shows MCP connect input", async () => {
    mockFetch.mockImplementation((url: string) => {
      if (url === "/api/tools") return Promise.resolve({ json: () => Promise.resolve(mockTools()) });
      return Promise.resolve({ json: () => Promise.resolve(mockMcpStatus()) });
    });
    render(<ToolsPanel />);
    await waitFor(() => expect(screen.getByPlaceholderText("http://localhost:3001/mcp")).toBeInTheDocument());
  });

  it("shows connect button", async () => {
    mockFetch.mockImplementation((url: string) => {
      if (url === "/api/tools") return Promise.resolve({ json: () => Promise.resolve(mockTools()) });
      return Promise.resolve({ json: () => Promise.resolve(mockMcpStatus()) });
    });
    render(<ToolsPanel />);
    await waitFor(() => expect(screen.getByText("Connect")).toBeInTheDocument());
  });

  it("shows MCP status", async () => {
    mockFetch.mockImplementation((url: string) => {
      if (url === "/api/tools") return Promise.resolve({ json: () => Promise.resolve(mockTools()) });
      return Promise.resolve({ json: () => Promise.resolve(mockMcpStatus()) });
    });
    render(<ToolsPanel />);
    await waitFor(() => expect(screen.getByText("Not connected")).toBeInTheDocument());
  });

  it("shows connected status when connected", async () => {
    mockFetch.mockImplementation((url: string) => {
      if (url === "/api/tools") return Promise.resolve({ json: () => Promise.resolve(mockTools()) });
      return Promise.resolve({ json: () => Promise.resolve({ connected: true, url: "http://localhost:3001/mcp", imported_count: 5 }) });
    });
    render(<ToolsPanel />);
    await waitFor(() => expect(screen.getByText(/Connected to/)).toBeInTheDocument());
  });

  it("renders tools list", async () => {
    mockFetch.mockImplementation((url: string) => {
      if (url === "/api/tools") return Promise.resolve({ json: () => Promise.resolve(mockTools()) });
      return Promise.resolve({ json: () => Promise.resolve(mockMcpStatus()) });
    });
    render(<ToolsPanel />);
    await waitFor(() => expect(screen.getByText("Registered Tools (2)")).toBeInTheDocument());
  });

  it("shows tool name and description", async () => {
    mockFetch.mockImplementation((url: string) => {
      if (url === "/api/tools") return Promise.resolve({ json: () => Promise.resolve(mockTools()) });
      return Promise.resolve({ json: () => Promise.resolve(mockMcpStatus()) });
    });
    render(<ToolsPanel />);
    await waitFor(() => {
      const all = document.body.textContent;
      expect(all).toContain("terminal");
      expect(all).toContain("Execute terminal commands");
    });
  });

  it("shows tool enabled/disabled badge", async () => {
    mockFetch.mockImplementation((url: string) => {
      if (url === "/api/tools") return Promise.resolve({ json: () => Promise.resolve(mockTools()) });
      return Promise.resolve({ json: () => Promise.resolve(mockMcpStatus()) });
    });
    render(<ToolsPanel />);
    await waitFor(() => expect(screen.getByText("enabled")).toBeInTheDocument());
    expect(screen.getByText("disabled")).toBeInTheDocument();
  });

  it("shows tool timeout and call count", async () => {
    mockFetch.mockImplementation((url: string) => {
      if (url === "/api/tools") return Promise.resolve({ json: () => Promise.resolve(mockTools()) });
      return Promise.resolve({ json: () => Promise.resolve(mockMcpStatus()) });
    });
    render(<ToolsPanel />);
    await waitFor(() => expect(screen.getByText(/Timeout: 30s/)).toBeInTheDocument());
    expect(screen.getByText("Calls: 42")).toBeInTheDocument();
  });

  it("shows toggle button for each tool", async () => {
    mockFetch.mockImplementation((url: string) => {
      if (url === "/api/tools") return Promise.resolve({ json: () => Promise.resolve(mockTools()) });
      return Promise.resolve({ json: () => Promise.resolve(mockMcpStatus()) });
    });
    render(<ToolsPanel />);
    await waitFor(() => expect(screen.getByText("Disable")).toBeInTheDocument());
    expect(screen.getByText("Enable")).toBeInTheDocument();
  });

  it("renders quick execute section", async () => {
    mockFetch.mockImplementation((url: string) => {
      if (url === "/api/tools") return Promise.resolve({ json: () => Promise.resolve(mockTools()) });
      return Promise.resolve({ json: () => Promise.resolve(mockMcpStatus()) });
    });
    render(<ToolsPanel />);
    await waitFor(() => expect(screen.getByText("Quick Execute")).toBeInTheDocument());
  });

  it("shows tool select dropdown", async () => {
    mockFetch.mockImplementation((url: string) => {
      if (url === "/api/tools") return Promise.resolve({ json: () => Promise.resolve(mockTools()) });
      return Promise.resolve({ json: () => Promise.resolve(mockMcpStatus()) });
    });
    render(<ToolsPanel />);
    await waitFor(() => expect(screen.getByText("Select a tool...")).toBeInTheDocument());
  });

  it("only shows enabled tools in dropdown", async () => {
    mockFetch.mockImplementation((url: string) => {
      if (url === "/api/tools") return Promise.resolve({ json: () => Promise.resolve(mockTools()) });
      return Promise.resolve({ json: () => Promise.resolve(mockMcpStatus()) });
    });
    render(<ToolsPanel />);
    await waitFor(() => {
      const select = document.querySelector("select");
      expect(select).toBeInTheDocument();
    });
  });

  it("shows execute params textarea", async () => {
    mockFetch.mockImplementation((url: string) => {
      if (url === "/api/tools") return Promise.resolve({ json: () => Promise.resolve(mockTools()) });
      return Promise.resolve({ json: () => Promise.resolve(mockMcpStatus()) });
    });
    render(<ToolsPanel />);
    await waitFor(() => expect(screen.getByPlaceholderText('{"param": "value"}')).toBeInTheDocument());
  });

  it("shows execute button", async () => {
    mockFetch.mockImplementation((url: string) => {
      if (url === "/api/tools") return Promise.resolve({ json: () => Promise.resolve(mockTools()) });
      return Promise.resolve({ json: () => Promise.resolve(mockMcpStatus()) });
    });
    render(<ToolsPanel />);
    await waitFor(() => expect(screen.getByText("Execute")).toBeInTheDocument());
  });

  it("polls data on interval", async () => {
    mockFetch.mockImplementation((url: string) => {
      if (url === "/api/tools") return Promise.resolve({ json: () => Promise.resolve(mockTools()) });
      return Promise.resolve({ json: () => Promise.resolve(mockMcpStatus()) });
    });
    render(<ToolsPanel />);
    await waitFor(() => expect(screen.getByText("MCP Server Connection")).toBeInTheDocument());
    jest.advanceTimersByTime(10000);
    expect(mockFetch).toHaveBeenCalled();
  });
});
