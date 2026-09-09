/**
 * Tests for MemorySystemPanel — loading, tier cards, utilization display.
 */

import React from "react";
import { render, screen, waitFor } from "@testing-library/react";

jest.mock("@/lib/api", () => {
  const mockGetMemoryStats = jest.fn();
  return {
    api: {
      getMemoryStats: mockGetMemoryStats,
    },
    MemorySystemStats: Object,
  };
});

import { MemorySystemPanel } from "../MemorySystemPanel";
import * as api from "@/lib/api";

const mockGetMemoryStats = api.api.getMemoryStats as jest.Mock;

describe("MemorySystemPanel", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    mockGetMemoryStats.mockReset();
  });

  function mockStatsData() {
    return {
      sensory: { size: 1.2, capacity: 4 },
      longterm: { size: 45.5, capacity: 100 },
      procedural: { size: 12.3, capacity: 50 },
      working: { size: 0.5, capacity: 10 },
    };
  }

  it("renders loading state", async () => {
    mockGetMemoryStats.mockImplementation(() => new Promise(() => {}));
    render(<MemorySystemPanel />);
    expect(screen.getByText("Loading memory stats...")).toBeInTheDocument();
  });

  it("renders header", async () => {
    mockGetMemoryStats.mockResolvedValue(mockStatsData());
    render(<MemorySystemPanel />);
    await waitFor(() => expect(screen.getByText("Memory System")).toBeInTheDocument());
  });

  it("renders all four tier cards", async () => {
    mockGetMemoryStats.mockResolvedValue(mockStatsData());
    render(<MemorySystemPanel />);
    await waitFor(() => expect(screen.getByText("Sensory Memory")).toBeInTheDocument());
    await waitFor(() => expect(screen.getByText("Long-term Memory")).toBeInTheDocument());
    await waitFor(() => expect(screen.getByText("Procedural Memory")).toBeInTheDocument());
    await waitFor(() => expect(screen.getByText("Backup Store")).toBeInTheDocument());
  });

  it("renders tier storage types", async () => {
    mockGetMemoryStats.mockResolvedValue(mockStatsData());
    render(<MemorySystemPanel />);
    await waitFor(() => expect(screen.getByText("Redis")).toBeInTheDocument());
    await waitFor(() => expect(screen.getByText("PostgreSQL")).toBeInTheDocument());
    await waitFor(() => expect(screen.getByText("Neo4j")).toBeInTheDocument());
    await waitFor(() => expect(screen.getByText("SQLite")).toBeInTheDocument());
  });

  it("renders tier descriptions", async () => {
    mockGetMemoryStats.mockResolvedValue(mockStatsData());
    render(<MemorySystemPanel />);
    await waitFor(() => expect(screen.getByText(/Short-term working memory/)).toBeInTheDocument());
    await waitFor(() => expect(screen.getByText(/Persistent knowledge store/)).toBeInTheDocument());
  });

  it("renders tier icons", async () => {
    mockGetMemoryStats.mockResolvedValue(mockStatsData());
    render(<MemorySystemPanel />);
    // Check that tier icon divs exist (emoji rendering varies in jsdom)
    const iconDivs = document.querySelectorAll('.rounded-xl');
    expect(iconDivs.length).toBeGreaterThanOrEqual(1);
  });

  it("renders capacity values", async () => {
    mockGetMemoryStats.mockResolvedValue(mockStatsData());
    render(<MemorySystemPanel />);
    // Capacity <= 100 uses MB, not GB
    await waitFor(() => expect(screen.getByText(/1\.2 \/ 4 MB/)).toBeInTheDocument());
    await waitFor(() => expect(screen.getByText(/45\.5 \/ 100 MB/)).toBeInTheDocument());
  });

  it("renders utilization percentages", async () => {
    mockGetMemoryStats.mockResolvedValue(mockStatsData());
    render(<MemorySystemPanel />);
    await waitFor(() => expect(screen.getByText("30%")).toBeInTheDocument());
    await waitFor(() => expect(screen.getByText("46%")).toBeInTheDocument());
  });

  it("renders progress bars for each tier", async () => {
    mockGetMemoryStats.mockResolvedValue(mockStatsData());
    render(<MemorySystemPanel />);
    await waitFor(() => expect(screen.getByText("Memory System")).toBeInTheDocument());
    const progressBars = document.querySelectorAll('[class*="h-full rounded-full"]');
    expect(progressBars.length).toBeGreaterThan(0);
  });

  it("handles zero capacity gracefully", async () => {
    mockGetMemoryStats.mockResolvedValue({
      sensory: { size: 0, capacity: 0 },
      longterm: { size: 0, capacity: 0 },
      procedural: { size: 0, capacity: 0 },
      working: { size: 0, capacity: 0 },
    });
    render(<MemorySystemPanel />);
    await waitFor(() => expect(screen.getByText("Memory System")).toBeInTheDocument());
  });

  it("handles null stats", async () => {
    mockGetMemoryStats.mockResolvedValue(null);
    render(<MemorySystemPanel />);
    expect(screen.getByText("Loading memory stats...")).toBeInTheDocument();
  });

  it("handles API error gracefully", async () => {
    mockGetMemoryStats.mockRejectedValue(new Error("Network error"));
    render(<MemorySystemPanel />);
    expect(screen.getByText("Loading memory stats...")).toBeInTheDocument();
  });

  it("renders tier 3 description", async () => {
    mockGetMemoryStats.mockResolvedValue(mockStatsData());
    render(<MemorySystemPanel />);
    await waitFor(() => expect(screen.getByText("Knowledge graphs, relationships, reasoning patterns")).toBeInTheDocument());
  });

  it("renders tier 4 description", async () => {
    mockGetMemoryStats.mockResolvedValue(mockStatsData());
    render(<MemorySystemPanel />);
    await waitFor(() => expect(screen.getByText("Redundant backup, disaster recovery")).toBeInTheDocument());
  });

  it("renders 100% utilization when full", async () => {
    mockGetMemoryStats.mockResolvedValue({
      sensory: { size: 4, capacity: 4 },
      longterm: { size: 100, capacity: 100 },
      procedural: { size: 50, capacity: 50 },
      working: { size: 10, capacity: 10 },
    });
    render(<MemorySystemPanel />);
    await waitFor(() => expect(screen.getByText("100%")).toBeInTheDocument());
  });

  it("renders 0% utilization when empty", async () => {
    mockGetMemoryStats.mockResolvedValue({
      sensory: { size: 0, capacity: 4 },
      longterm: { size: 0, capacity: 100 },
      procedural: { size: 0, capacity: 50 },
      working: { size: 0, capacity: 10 },
    });
    render(<MemorySystemPanel />);
    await waitFor(() => expect(screen.getByText("0%")).toBeInTheDocument());
  });
});
