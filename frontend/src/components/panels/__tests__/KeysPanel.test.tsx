/**
 * Tests for KeysPanel — loading, stats, filtering, status display.
 */

import React from "react";
import { render, screen, waitFor, fireEvent } from "@testing-library/react";
import { KeysPanel } from "../KeysPanel";

const mockFetch = jest.fn();
global.fetch = mockFetch;

describe("KeysPanel", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    mockFetch.mockReset();
  });

  function mockKeysData() {
    return {
      keys: [
        {
          id: "k1",
          name: "OpenAI API",
          provider: "OpenAI",
          status: "active",
          created: "2024-01-01",
          expires: "2025-01-01",
          lastUsed: "2024-06-01",
          usageCount: 1500,
          masked: "sk-••••••••••••4",
        },
        {
          id: "k2",
          name: "GitHub Token",
          provider: "GitHub",
          status: "active",
          created: "2024-02-01",
          expires: "2025-02-01",
          lastUsed: "2024-06-02",
          usageCount: 300,
          masked: "ghp-••••••••••••••••",
        },
        {
          id: "k3",
          name: "Old Key",
          provider: "SearXNG",
          status: "expired",
          created: "2023-01-01",
          expires: "2024-01-01",
          lastUsed: "2023-12-01",
          usageCount: 500,
          masked: "••••••••••••3",
        },
        {
          id: "k4",
          name: "Revoked Key",
          provider: "Tavily",
          status: "revoked",
          created: "2023-06-01",
          expires: "2024-06-01",
          lastUsed: "2024-05-01",
          usageCount: 100,
          masked: "tv-••••••••••••4",
        },
      ],
    };
  }

  it("renders loading spinner", () => {
    mockFetch.mockImplementation(() => new Promise(() => {}));
    render(<KeysPanel />);
    expect(document.querySelector(".animate-spin")).toBeInTheDocument();
  });

  it("renders stats cards", async () => {
    mockFetch.mockResolvedValue({ json: () => Promise.resolve(mockKeysData()) });
    render(<KeysPanel />);
    await waitFor(() => expect(screen.getByText("Total Keys")).toBeInTheDocument());
    await waitFor(() => expect(screen.getByText("Total API Calls")).toBeInTheDocument());
  });

  it("renders correct total count", async () => {
    mockFetch.mockResolvedValue({ json: () => Promise.resolve(mockKeysData()) });
    render(<KeysPanel />);
    await waitFor(() => expect(screen.getByText("4")).toBeInTheDocument());
  });

  it("renders correct active count", async () => {
    mockFetch.mockResolvedValue({ json: () => Promise.resolve(mockKeysData()) });
    render(<KeysPanel />);
    await waitFor(() => expect(screen.getByText("2")).toBeInTheDocument());
  });

  it("renders total API calls", async () => {
    mockFetch.mockResolvedValue({ json: () => Promise.resolve(mockKeysData()) });
    render(<KeysPanel />);
    await waitFor(() => expect(screen.getByText("2,400")).toBeInTheDocument());
  });

  it("renders filter buttons", async () => {
    mockFetch.mockResolvedValue({ json: () => Promise.resolve(mockKeysData()) });
    render(<KeysPanel />);
    await waitFor(() => expect(screen.getByText("All")).toBeInTheDocument());
    await waitFor(() => expect(screen.getByText("Expired")).toBeInTheDocument());
    await waitFor(() => expect(screen.getByText("Revoked")).toBeInTheDocument());
  });

  it("renders all key names", async () => {
    mockFetch.mockResolvedValue({ json: () => Promise.resolve(mockKeysData()) });
    render(<KeysPanel />);
    await waitFor(() => expect(screen.getByText("OpenAI API")).toBeInTheDocument());
    await waitFor(() => expect(screen.getByText("GitHub Token")).toBeInTheDocument());
    await waitFor(() => expect(screen.getByText("Old Key")).toBeInTheDocument());
    await waitFor(() => expect(screen.getByText("Revoked Key")).toBeInTheDocument());
  });

  it("renders provider names", async () => {
    mockFetch.mockResolvedValue({ json: () => Promise.resolve(mockKeysData()) });
    render(<KeysPanel />);
    await waitFor(() => expect(screen.getByText("OpenAI")).toBeInTheDocument());
    await waitFor(() => expect(screen.getByText("GitHub")).toBeInTheDocument());
  });

  it("renders status badges", async () => {
    mockFetch.mockResolvedValue({ json: () => Promise.resolve(mockKeysData()) });
    render(<KeysPanel />);
    await waitFor(() => expect(screen.getByText("active")).toBeInTheDocument());
    await waitFor(() => expect(screen.getByText("expired")).toBeInTheDocument());
    await waitFor(() => expect(screen.getByText("revoked")).toBeInTheDocument());
  });

  it("renders masked key values", async () => {
    mockFetch.mockResolvedValue({ json: () => Promise.resolve(mockKeysData()) });
    render(<KeysPanel />);
    await waitFor(() => expect(screen.getByText("sk-••••••••••••4")).toBeInTheDocument());
  });

  it("renders usage count and expiry", async () => {
    mockFetch.mockResolvedValue({ json: () => Promise.resolve(mockKeysData()) });
    render(<KeysPanel />);
    await waitFor(() => expect(screen.getByText("1,500 calls • expires 2025-01-01")).toBeInTheDocument());
  });

  it("filters by active status", async () => {
    mockFetch.mockResolvedValue({ json: () => Promise.resolve(mockKeysData()) });
    render(<KeysPanel />);
    await waitFor(() => expect(screen.getByText("OpenAI API")).toBeInTheDocument());
    // Click the filter button by its role and aria-label context
    const filterButtons = document.querySelectorAll('button');
    const activeBtn = Array.from(filterButtons).find(b => b.textContent?.trim() === "Active");
    if (activeBtn) fireEvent.click(activeBtn);
    await waitFor(() => expect(screen.getByText("OpenAI API")).toBeInTheDocument());
    await waitFor(() => expect(screen.getByText("GitHub Token")).toBeInTheDocument());
    expect(screen.queryByText("Old Key")).not.toBeInTheDocument();
    expect(screen.queryByText("Revoked Key")).not.toBeInTheDocument();
  });

  it("filters by expired status", async () => {
    mockFetch.mockResolvedValue({ json: () => Promise.resolve(mockKeysData()) });
    render(<KeysPanel />);
    await waitFor(() => expect(screen.getByText("Expired")).toBeInTheDocument());
    fireEvent.click(screen.getByText("Expired"));
    await waitFor(() => expect(screen.getByText("Old Key")).toBeInTheDocument());
    expect(screen.queryByText("OpenAI API")).not.toBeInTheDocument();
  });

  it("filters by revoked status", async () => {
    mockFetch.mockResolvedValue({ json: () => Promise.resolve(mockKeysData()) });
    render(<KeysPanel />);
    await waitFor(() => expect(screen.getByText("Revoked")).toBeInTheDocument());
    fireEvent.click(screen.getByText("Revoked"));
    await waitFor(() => expect(screen.getByText("Revoked Key")).toBeInTheDocument());
    expect(screen.queryByText("OpenAI API")).not.toBeInTheDocument();
  });

  it("shows empty state when no keys match filter", async () => {
    mockFetch.mockResolvedValue({ json: () => Promise.resolve(mockKeysData()) });
    render(<KeysPanel />);
    await waitFor(() => expect(screen.getByText("Revoked")).toBeInTheDocument());
    fireEvent.click(screen.getByText("Revoked"));
    // Click the filter button by its role and aria-label context
    const filterButtons = document.querySelectorAll('button');
    const activeBtn = Array.from(filterButtons).find(b => b.textContent?.trim() === "Active");
    if (activeBtn) fireEvent.click(activeBtn);
    await waitFor(() => expect(screen.getByText("No keys found")).toBeInTheDocument());
  });

  it("handles empty keys array", async () => {
    mockFetch.mockResolvedValue({ json: () => Promise.resolve({ keys: [] }) });
    render(<KeysPanel />);
    await waitFor(() => expect(screen.getByText("0")).toBeInTheDocument());
    await waitFor(() => expect(screen.getByText("No keys found")).toBeInTheDocument());
  });

  it("handles fetch error", async () => {
    mockFetch.mockRejectedValue(new Error("Network error"));
    render(<KeysPanel />);
    await waitFor(() => expect(screen.getByText("Total Keys")).toBeInTheDocument());
    await waitFor(() => expect(screen.getByText("No keys found")).toBeInTheDocument());
  });

  it("renders zero usage count", async () => {
    const data = mockKeysData();
    data.keys[0].usageCount = 0;
    mockFetch.mockResolvedValue({ json: () => Promise.resolve(data) });
    render(<KeysPanel />);
    await waitFor(() => expect(screen.getByText("0")).toBeInTheDocument());
  });
});
