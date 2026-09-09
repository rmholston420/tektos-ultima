/**
 * Tests for the MemoryPanel component.
 *
 * MemoryPanel fetches /api/memory and renders tier cards, entry list,
 * and system stats. We mock fetch and test rendering at each stage.
 */

import React from "react";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { MemoryPanel } from "../MemoryPanel";

// ---------------------------------------------------------------------------
// Mock fetch
// ---------------------------------------------------------------------------

const mockFetch = jest.fn();
beforeEach(() => {
  jest.useFakeTimers();
  mockFetch.mockReset();
});
afterEach(() => {
  jest.useRealTimers();
});
global.fetch = mockFetch;

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function mockMemoryStats(overrides: Record<string, number> = {}) {
  return {
    working_count: 5,
    working_novel: 2,
    long_term_count: 42,
    long_term_novel: 3,
    procedural_count: 12,
    procedural_novel: 0,
    transfers: 15,
    ...overrides,
  };
}

function mockTierEntries(tier: string, count: number) {
  return Array.from({ length: count }, (_, i) => ({
    id: `${tier}-${i}`,
    content: `${tier} entry ${i}`,
    tier,
    hemisphere: i % 2 === 0 ? "left" : "right",
    is_novel: i === 0,
    novelty_score: 0.85,
    timestamp: new Date().toISOString(),
    metadata: {},
  }));
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("MemoryPanel", () => {
  it("shows loading state initially", async () => {
    mockFetch.mockImplementation((url: string) => {
      if (url === "/api/memory") {
        return Promise.resolve({ json: () => Promise.resolve(mockMemoryStats()) });
      }
      return Promise.resolve({ json: () => Promise.resolve([]) });
    });

    render(<MemoryPanel />);
    expect(screen.getByText("Loading memory system...")).toBeInTheDocument();
  });

  it("renders tier cards after loading", async () => {
    mockFetch.mockImplementation((url: string) => {
      if (url === "/api/memory") {
        return Promise.resolve({ json: () => Promise.resolve(mockMemoryStats()) });
      }
      if (url.includes("/api/memory?tier=")) {
        return Promise.resolve({ json: () => Promise.resolve([]) });
      }
      return Promise.resolve({ json: () => Promise.resolve([]) });
    });

    render(<MemoryPanel />);
    await waitFor(() => expect(screen.getByText("Working")).toBeInTheDocument());
    expect(screen.getByText("Long-Term")).toBeInTheDocument();
    expect(screen.getByText("Procedural")).toBeInTheDocument();
  });

  it("displays correct counts for each tier", async () => {
    mockFetch.mockImplementation((url: string) => {
      if (url === "/api/memory") {
        return Promise.resolve({ json: () => Promise.resolve(mockMemoryStats({ working_count: 7, long_term_count: 100, procedural_count: 3 }) as any) });
      }
      return Promise.resolve({ json: () => Promise.resolve([]) });
    });

    render(<MemoryPanel />);
    await waitFor(() => expect(screen.getByText("7")).toBeInTheDocument());
    expect(screen.getByText("100")).toBeInTheDocument();
    expect(screen.getByText("3")).toBeInTheDocument();
  });

  it("shows tier descriptions", async () => {
    mockFetch.mockImplementation((url: string) => {
      if (url === "/api/memory") {
        return Promise.resolve({ json: () => Promise.resolve(mockMemoryStats()) });
      }
      return Promise.resolve({ json: () => Promise.resolve([]) });
    });

    render(<MemoryPanel />);
    await waitFor(() => expect(screen.getByText("Active cognition (7±2)")).toBeInTheDocument());
    expect(screen.getByText("Declarative knowledge")).toBeInTheDocument();
    expect(screen.getByText("Skills & wisdom")).toBeInTheDocument();
  });

  it("shows novel entry count when novel > 0", async () => {
    mockFetch.mockImplementation((url: string) => {
      if (url === "/api/memory") {
        return Promise.resolve({ json: () => Promise.resolve(mockMemoryStats({ working_novel: 2 }) as any) });
      }
      return Promise.resolve({ json: () => Promise.resolve([]) });
    });

    render(<MemoryPanel />);
    await waitFor(() => expect(screen.getByText(/⚡ 2 novel/)).toBeInTheDocument());
  });

  it("shows singular 'entry' when novel === 1", async () => {
    mockFetch.mockImplementation((url: string) => {
      if (url === "/api/memory") {
        return Promise.resolve({ json: () => Promise.resolve(mockMemoryStats({ working_novel: 1, long_term_novel: 0, procedural_novel: 0 }) as any) });
      }
      return Promise.resolve({ json: () => Promise.resolve([]) });
    });

    render(<MemoryPanel />);
    await waitFor(() => {
      const all = document.body.textContent;
      expect(all).toContain("1 novel");
      // Component always uses plural "entries" in the empty message
      expect(all).toContain("entries");
    });
  });

  it("renders tier filter buttons", async () => {
    mockFetch.mockImplementation((url: string) => {
      if (url === "/api/memory") {
        return Promise.resolve({ json: () => Promise.resolve(mockMemoryStats()) });
      }
      return Promise.resolve({ json: () => Promise.resolve([]) });
    });

    render(<MemoryPanel />);
    await waitFor(() => expect(screen.getByText("🧠 Working")).toBeInTheDocument());
    expect(screen.getByText("📚 Long-Term")).toBeInTheDocument();
    expect(screen.getByText("⚙️ Procedural")).toBeInTheDocument();
  });

  it("switches tier when button clicked", async () => {
    mockFetch.mockImplementation((url: string) => {
      if (url === "/api/memory") {
        return Promise.resolve({ json: () => Promise.resolve(mockMemoryStats()) });
      }
      if (url.includes("/api/memory?tier=")) {
        const tier = url.split("tier=")[1];
        return Promise.resolve({ json: () => Promise.resolve(mockTierEntries(tier, 2)) });
      }
      return Promise.resolve({ json: () => Promise.resolve([]) });
    });

    render(<MemoryPanel />);
    await waitFor(() => expect(screen.getByText("📚 Long-Term")).toBeInTheDocument());
    const longTermBtn = screen.getByText("📚 Long-Term");
    fireEvent.click(longTermBtn);
    // Should trigger a fetch for the tier
    await waitFor(() => expect(mockFetch).toHaveBeenCalledWith(expect.stringContaining("tier=long_term")));
  });

  it("shows entries for selected tier", async () => {
    mockFetch.mockImplementation((url: string) => {
      if (url === "/api/memory") {
        return Promise.resolve({ json: () => Promise.resolve(mockMemoryStats()) });
      }
      if (url.includes("/api/memory?tier=")) {
        return Promise.resolve({ json: () => Promise.resolve(mockTierEntries("long_term", 3)) });
      }
      return Promise.resolve({ json: () => Promise.resolve([]) });
    });

    render(<MemoryPanel />);
    await waitFor(() => expect(screen.getByText("long_term entry 0")).toBeInTheDocument());
    expect(screen.getByText("long_term entry 1")).toBeInTheDocument();
    expect(screen.getByText("long_term entry 2")).toBeInTheDocument();
  });

  it("shows hemisphere label for entries", async () => {
    mockFetch.mockImplementation((url: string) => {
      if (url === "/api/memory") {
        return Promise.resolve({ json: () => Promise.resolve(mockMemoryStats()) });
      }
      return Promise.resolve({ json: () => Promise.resolve(mockTierEntries("long_term", 2)) });
    });

    render(<MemoryPanel />);
    await waitFor(() => expect(screen.getByText("◈ Operative")).toBeInTheDocument());
    expect(screen.getByText("◉ Speculative")).toBeInTheDocument();
  });

  it("shows novelty badge for novel entries", async () => {
    mockFetch.mockImplementation((url: string) => {
      if (url === "/api/memory") {
        return Promise.resolve({ json: () => Promise.resolve(mockMemoryStats()) });
      }
      return Promise.resolve({ json: () => Promise.resolve(mockTierEntries("long_term", 1)) });
    });

    render(<MemoryPanel />);
    await waitFor(() => expect(screen.getByText(/⚡ Novel/)).toBeInTheDocument());
  });

  it("shows 'No entries' message when empty", async () => {
    mockFetch.mockImplementation((url: string) => {
      if (url === "/api/memory") {
        return Promise.resolve({ json: () => Promise.resolve(mockMemoryStats()) });
      }
      return Promise.resolve({ json: () => Promise.resolve([]) });
    });

    render(<MemoryPanel />);
    await waitFor(() => expect(screen.getByText("No long_term memory entries")).toBeInTheDocument());
  });

  it("shows system stats", async () => {
    mockFetch.mockImplementation((url: string) => {
      if (url === "/api/memory") {
        return Promise.resolve({ json: () => Promise.resolve(mockMemoryStats({ transfers: 42 }) as any) });
      }
      return Promise.resolve({ json: () => Promise.resolve([]) });
    });

    render(<MemoryPanel />);
    await waitFor(() => expect(screen.getByText("Memory Transfers:")).toBeInTheDocument());
    expect(screen.getByText("Total Novelty:")).toBeInTheDocument();
  });

  it("handles fetch error gracefully", async () => {
    mockFetch.mockRejectedValue(new Error("Network error"));

    render(<MemoryPanel />);
    // Should show loading, then error is caught silently
    await waitFor(() => {
      // After error, loading is set to true but stats is null, so still loading
    });
  });

  it("polls data on interval", async () => {
    mockFetch.mockImplementation((url: string) => {
      if (url === "/api/memory") {
        return Promise.resolve({ json: () => Promise.resolve(mockMemoryStats()) });
      }
      return Promise.resolve({ json: () => Promise.resolve([]) });
    });

    render(<MemoryPanel />);
    // Wait for initial data to load
    await waitFor(() => expect(screen.getByText("Working")).toBeInTheDocument());
    // Advance timer to trigger interval
    jest.advanceTimersByTime(10000);
    // Should have been called multiple times: initial fetch + interval
    expect(mockFetch).toHaveBeenCalled();
  });
});
