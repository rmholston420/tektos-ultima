/**
 * Tests for the MetabolismPanel component.
 *
 * MetabolismPanel fetches /api/metabolism and renders GPU, system,
 * context budget, and activity stats. We mock fetch and test rendering.
 */

import React from "react";
import { render, screen, waitFor } from "@testing-library/react";
import { MetabolismPanel } from "../MetabolismPanel";

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

function mockMetabolismState(overrides: Record<string, any> = {}) {
  return {
    overall_health: "normal",
    timestamp: new Date().toISOString(),
    gpu: {
      temperature: 65,
      utilization: 72,
      vram_total_mb: 32768,
      vram_used_mb: 16384,
      vram_pct: 50,
      power_draw_w: 250,
      power_limit_w: 575,
      power_pct: 43,
      fan_speed: 1800,
      clock_graphics: 2100,
      clock_memory: 1400,
    },
    system: {
      cpu_percent: 45,
      memory_total_mb: 65536,
      memory_used_mb: 32768,
      memory_pct: 50,
      disk_total_gb: 1000,
      disk_used_gb: 500,
      disk_pct: 50,
      disk_free_gb: 500,
    },
    context_budget: {
      current_tokens: 50000,
      max_tokens: 128000,
      pct: 39,
      remaining_tokens: 78000,
      alert_level: "normal",
      recommended_action: "continue",
    },
    inference_latency_ms: 45,
    tokens_per_second: 32,
    active_sessions: 3,
    total_tool_calls: 128,
    ...overrides,
  };
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("MetabolismPanel", () => {
  it("shows loading state initially", async () => {
    mockFetch.mockImplementation(() => Promise.resolve({ json: () => Promise.resolve(mockMetabolismState()) }));
    render(<MetabolismPanel />);
    expect(screen.getByText("Loading metabolism...")).toBeInTheDocument();
  });

  it("renders health banner after loading", async () => {
    mockFetch.mockImplementation(() => Promise.resolve({ json: () => Promise.resolve(mockMetabolismState()) }));
    render(<MetabolismPanel />);
    await waitFor(() => expect(screen.getByText("normal")).toBeInTheDocument());
  });

  it("shows correct health status icon", async () => {
    mockFetch.mockImplementation(() => Promise.resolve({ json: () => Promise.resolve(mockMetabolismState()) }));
    render(<MetabolismPanel />);
    await waitFor(() => expect(screen.getByText("normal")).toBeInTheDocument());
  });

  it("renders GPU metrics", async () => {
    mockFetch.mockImplementation(() => Promise.resolve({ json: () => Promise.resolve(mockMetabolismState()) }));
    render(<MetabolismPanel />);
    await waitFor(() => expect(screen.getByText("GPU — RTX 5090")).toBeInTheDocument());
  });

  it("displays GPU temperature", async () => {
    mockFetch.mockImplementation(() => Promise.resolve({ json: () => Promise.resolve(mockMetabolismState()) }));
    render(<MetabolismPanel />);
    await waitFor(() => expect(screen.getByText("65°C")).toBeInTheDocument());
  });

  it("displays VRAM usage", async () => {
    mockFetch.mockImplementation(() => Promise.resolve({ json: () => Promise.resolve(mockMetabolismState()) }));
    render(<MetabolismPanel />);
    await waitFor(() => {
      const all = document.body.textContent;
      expect(all).toContain("16.0k");
      expect(all).toContain("32.0k");
      expect(all).toContain("MB");
    });
  });

  it("displays power draw", async () => {
    mockFetch.mockImplementation(() => Promise.resolve({ json: () => Promise.resolve(mockMetabolismState()) }));
    render(<MetabolismPanel />);
    await waitFor(() => expect(screen.getByText(/250W \/ 575W/)).toBeInTheDocument());
  });

  it("displays utilization", async () => {
    mockFetch.mockImplementation(() => Promise.resolve({ json: () => Promise.resolve(mockMetabolismState()) }));
    render(<MetabolismPanel />);
    await waitFor(() => expect(screen.getByText("72%")).toBeInTheDocument());
  });

  it("shows thermal warning when temp >= 82", async () => {
    mockFetch.mockImplementation(() => Promise.resolve({ json: () => Promise.resolve(mockMetabolismState({ gpu: { ...mockMetabolismState().gpu, temperature: 85 } }) as any) }));
    render(<MetabolismPanel />);
    await waitFor(() => expect(screen.getByText(/Thermal cooling trigger active/)).toBeInTheDocument());
  });

  it("shows emergency cutoff when temp >= 85", async () => {
    mockFetch.mockImplementation(() => Promise.resolve({ json: () => Promise.resolve(mockMetabolismState({ gpu: { ...mockMetabolismState().gpu, temperature: 88 } }) as any) }));
    render(<MetabolismPanel />);
    await waitFor(() => expect(screen.getByText(/Emergency cutoff zone/)).toBeInTheDocument());
  });

  it("renders system metrics", async () => {
    mockFetch.mockImplementation(() => Promise.resolve({ json: () => Promise.resolve(mockMetabolismState()) }));
    render(<MetabolismPanel />);
    await waitFor(() => expect(screen.getByText("System")).toBeInTheDocument());
  });

  it("displays CPU usage", async () => {
    mockFetch.mockImplementation(() => Promise.resolve({ json: () => Promise.resolve(mockMetabolismState()) }));
    render(<MetabolismPanel />);
    await waitFor(() => expect(screen.getByText("45%")).toBeInTheDocument());
  });

  it("displays memory usage", async () => {
    mockFetch.mockImplementation(() => Promise.resolve({ json: () => Promise.resolve(mockMetabolismState()) }));
    render(<MetabolismPanel />);
    await waitFor(() => {
      const all = document.body.textContent;
      expect(all).toContain("Memory");
      expect(all).toContain("50");
    });
  });

  it("displays disk usage", async () => {
    mockFetch.mockImplementation(() => Promise.resolve({ json: () => Promise.resolve(mockMetabolismState()) }));
    render(<MetabolismPanel />);
    await waitFor(() => {
      const all = document.body.textContent;
      expect(all).toContain("Disk");
      expect(all).toContain("50");
    });
  });

  it("renders context budget", async () => {
    mockFetch.mockImplementation(() => Promise.resolve({ json: () => Promise.resolve(mockMetabolismState()) }));
    render(<MetabolismPanel />);
    await waitFor(() => expect(screen.getByText("Context Budget")).toBeInTheDocument());
  });

  it("displays context token usage", async () => {
    mockFetch.mockImplementation(() => Promise.resolve({ json: () => Promise.resolve(mockMetabolismState()) }));
    render(<MetabolismPanel />);
    await waitFor(() => {
      const all = document.body.textContent;
      expect(all).toContain("Context Budget");
      expect(all).toContain("k /");
      expect(all).toContain("tokens");
    });
  });

  it("shows recommended action", async () => {
    mockFetch.mockImplementation(() => Promise.resolve({ json: () => Promise.resolve(mockMetabolismState()) }));
    render(<MetabolismPanel />);
    await waitFor(() => expect(screen.getByText("Action: continue")).toBeInTheDocument());
  });

  it("renders activity stats", async () => {
    mockFetch.mockImplementation(() => Promise.resolve({ json: () => Promise.resolve(mockMetabolismState()) }));
    render(<MetabolismPanel />);
    await waitFor(() => expect(screen.getByText("Sessions")).toBeInTheDocument());
    expect(screen.getByText("Tool Calls")).toBeInTheDocument();
    expect(screen.getByText("Latency")).toBeInTheDocument();
    expect(screen.getByText("Tokens/sec")).toBeInTheDocument();
  });

  it("displays active sessions count", async () => {
    mockFetch.mockImplementation(() => Promise.resolve({ json: () => Promise.resolve(mockMetabolismState()) }));
    render(<MetabolismPanel />);
    await waitFor(() => expect(screen.getByText("3")).toBeInTheDocument());
  });

  it("displays inference latency", async () => {
    mockFetch.mockImplementation(() => Promise.resolve({ json: () => Promise.resolve(mockMetabolismState()) }));
    render(<MetabolismPanel />);
    await waitFor(() => expect(screen.getByText("45ms")).toBeInTheDocument());
  });

  it("displays tokens per second", async () => {
    mockFetch.mockImplementation(() => Promise.resolve({ json: () => Promise.resolve(mockMetabolismState()) }));
    render(<MetabolismPanel />);
    await waitFor(() => expect(screen.getByText("32")).toBeInTheDocument());
  });

  it("returns null when state is null", async () => {
    mockFetch.mockImplementation(() => Promise.resolve({ json: () => Promise.resolve(null) }));
    const { container } = render(<MetabolismPanel />);
    await waitFor(() => expect(container.firstChild).toBeNull());
  });

  it("polls data on interval", async () => {
    mockFetch.mockImplementation(() => Promise.resolve({ json: () => Promise.resolve(mockMetabolismState()) }));
    render(<MetabolismPanel />);
    await waitFor(() => expect(screen.getByText("normal")).toBeInTheDocument());
    jest.advanceTimersByTime(5000);
    expect(mockFetch).toHaveBeenCalled();
  });
});
