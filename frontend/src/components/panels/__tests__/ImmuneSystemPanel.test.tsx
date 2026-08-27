/**
 * Tests for ImmuneSystemPanel — health banner, threat cards, tabs, filtering.
 */

import React from "react";
import { render, screen, waitFor, fireEvent } from "@testing-library/react";
import { ImmuneSystemPanel } from "../ImmuneSystemPanel";

const mockFetch = jest.fn();
global.fetch = mockFetch;

describe("ImmuneSystemPanel", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    mockFetch.mockReset();
  });

  function mockImmuneData() {
    return {
      health: {
        overall: 0.85, status: "warning",
        components: { nervous_system: 0.9, metabolism: 0.7, memory: 0.85 },
        active_threats: 2, resolved_threats: 5,
        uptime_seconds: 3600, timestamp: 1704067200,
      },
      threats: [
        { category: "memory_leak", severity: "HIGH", description: "Memory usage exceeding threshold", timestamp: 1704067200, source: "metabolism", evidence: {}, affected_components: ["memory"], recommended_action: "Clear cache", resolved: false, resolution: "" },
        { category: "cpu_spike", severity: "MEDIUM", description: "CPU utilization spike detected", timestamp: 1704067100, source: "nervous_system", evidence: {}, affected_components: ["nervous_system"], recommended_action: "Throttle", resolved: false, resolution: "" },
        { category: "disk_full", severity: "CRITICAL", description: "Disk space critical", timestamp: 1704066000, source: "metabolism", evidence: {}, affected_components: ["metabolism"], recommended_action: "Clean up", resolved: true, resolution: "Cleared 10GB" },
      ],
      memory: { total_threats_seen: 15, unique_threats: 8, categories: { memory_leak: 5, cpu_spike: 4, disk_full: 6 }, last_updated: "2024-01-01" },
      responses: [
        { threat: { description: "Memory leak" }, action: "cache_clear", timestamp: 1704067200, success: true, details: "Cleared 500MB" },
        { threat: { description: "CPU spike" }, action: "throttle", timestamp: 1704067100, success: false, details: "Throttle failed" },
      ],
      detectors: [
        { name: "memory_detector", status: "active", threats_detected: 5 },
        { name: "cpu_detector", status: "active", threats_detected: 3 },
        { name: "disk_detector", status: "inactive", threats_detected: 0 },
      ],
    };
  }

  function setupMock(data: ReturnType<typeof mockImmuneData>) {
    mockFetch.mockImplementation((url: string) => {
      if (url.includes("/api/immune/health")) return Promise.resolve({ ok: true, json: () => Promise.resolve(data.health) });
      if (url.includes("/api/immune/threats")) return Promise.resolve({ ok: true, json: () => Promise.resolve(data.threats) });
      if (url.includes("/api/immune/memory")) return Promise.resolve({ ok: true, json: () => Promise.resolve(data.memory) });
      if (url.includes("/api/immune/responses")) return Promise.resolve({ ok: true, json: () => Promise.resolve(data.responses) });
      if (url.includes("/api/immune/detectors")) return Promise.resolve({ ok: true, json: () => Promise.resolve(data.detectors) });
      return Promise.resolve({ ok: false });
    });
  }

  it("renders loading state", () => {
    mockFetch.mockImplementation(() => new Promise(() => {}));
    render(<ImmuneSystemPanel />);
    expect(screen.getByText("Loading immune system...")).toBeInTheDocument();
  });

  it("renders health banner with status", async () => {
    const data = mockImmuneData();
    setupMock(data);
    render(<ImmuneSystemPanel />);
    await waitFor(() => expect(screen.getByText("System Health: warning")).toBeInTheDocument());
  });

  it("renders health score", async () => {
    const data = mockImmuneData();
    setupMock(data);
    render(<ImmuneSystemPanel />);
    await waitFor(() => expect(screen.getByText("Score: 85.00%")).toBeInTheDocument());
  });

  it("renders uptime", async () => {
    const data = mockImmuneData();
    setupMock(data);
    render(<ImmuneSystemPanel />);
    await waitFor(() => expect(screen.getByText("Uptime: 1h 0m")).toBeInTheDocument());
  });

  it("renders active and resolved threat counts", async () => {
    const data = mockImmuneData();
    setupMock(data);
    render(<ImmuneSystemPanel />);
    await waitFor(() => expect(screen.getByText("2 active")).toBeInTheDocument());
    await waitFor(() => expect(screen.getByText("5 resolved")).toBeInTheDocument());
  });

  it("renders component health bars", async () => {
    const data = mockImmuneData();
    setupMock(data);
    render(<ImmuneSystemPanel />);
    await waitFor(() => expect(screen.getByText("nervous system")).toBeInTheDocument());
    await waitFor(() => expect(screen.getByText("metabolism")).toBeInTheDocument());
  });

  it("renders detector status grid", async () => {
    const data = mockImmuneData();
    setupMock(data);
    render(<ImmuneSystemPanel />);
    await waitFor(() => expect(screen.getByText("Active Detectors")).toBeInTheDocument());
    await waitFor(() => expect(screen.getByText("memory detector")).toBeInTheDocument());
    await waitFor(() => expect(screen.getByText("cpu detector")).toBeInTheDocument());
  });

  it("renders threat cards with severity", async () => {
    const data = mockImmuneData();
    setupMock(data);
    render(<ImmuneSystemPanel />);
    await waitFor(() => expect(screen.getByText(/Threats/)).toBeInTheDocument());
    await waitFor(() => expect(screen.getByText("HIGH")).toBeInTheDocument());
    await waitFor(() => expect(screen.getByText("MEDIUM")).toBeInTheDocument());
  });

  it("renders threat description and recommended action", async () => {
    const data = mockImmuneData();
    setupMock(data);
    render(<ImmuneSystemPanel />);
    await waitFor(() => expect(screen.getByText("Memory usage exceeding threshold")).toBeInTheDocument());
    await waitFor(() => expect(screen.getByText(/Clear cache/)).toBeInTheDocument());
  });

  it("renders affected components on threat cards", async () => {
    const data = mockImmuneData();
    setupMock(data);
    render(<ImmuneSystemPanel />);
    await waitFor(() => expect(screen.getByText("memory")).toBeInTheDocument());
  });

  it("renders memory tab with stats", async () => {
    const data = mockImmuneData();
    setupMock(data);
    render(<ImmuneSystemPanel />);
    await waitFor(() => expect(screen.getByText(/Memory/)).toBeInTheDocument());
    const memoryTab = screen.getByText(/Memory/);
    fireEvent.click(memoryTab);
    await waitFor(() => expect(screen.getByText("Total Seen")).toBeInTheDocument());
    await waitFor(() => expect(screen.getByText("15")).toBeInTheDocument());
    await waitFor(() => expect(screen.getByText("Unique Types")).toBeInTheDocument());
  });

  it("renders threat category breakdown", async () => {
    const data = mockImmuneData();
    setupMock(data);
    render(<ImmuneSystemPanel />);
    await waitFor(() => expect(screen.getByText(/Memory/)).toBeInTheDocument());
    const memoryTab = screen.getByText(/Memory/);
    fireEvent.click(memoryTab);
    await waitFor(() => expect(screen.getByText("Threat Categories")).toBeInTheDocument());
  });

  it("renders responses tab", async () => {
    const data = mockImmuneData();
    setupMock(data);
    render(<ImmuneSystemPanel />);
    await waitFor(() => expect(screen.getByText(/Responses/)).toBeInTheDocument());
    const responsesTab = screen.getByText(/Responses/);
    fireEvent.click(responsesTab);
    await waitFor(() => expect(screen.getByText(/cache_clear/)).toBeInTheDocument());
    await waitFor(() => expect(screen.getByText(/throttle/)).toBeInTheDocument());
  });

  it("shows resolved threat badge", async () => {
    const data = mockImmuneData();
    setupMock(data);
    render(<ImmuneSystemPanel />);
    await waitFor(() => expect(screen.getByText("Show 1 resolved threats")).toBeInTheDocument());
  });

  it("toggles resolved threats visibility", async () => {
    const data = mockImmuneData();
    setupMock(data);
    render(<ImmuneSystemPanel />);
    await waitFor(() => expect(screen.getByText("Show 1 resolved threats")).toBeInTheDocument());
    fireEvent.click(screen.getByText("Show 1 resolved threats"));
    await waitFor(() => expect(screen.getByText("Hide resolved")).toBeInTheDocument());
  });

  it("shows no active threats message when empty", async () => {
    const data = mockImmuneData();
    data.threats = [];
    data.health.active_threats = 0;
    setupMock(data);
    render(<ImmuneSystemPanel />);
    await waitFor(() => expect(screen.getByText(/No active threats/)).toBeInTheDocument());
  });

  it("shows no responses message when empty", async () => {
    const data = mockImmuneData();
    data.responses = [];
    setupMock(data);
    render(<ImmuneSystemPanel />);
    await waitFor(() => expect(screen.getByText(/Responses/)).toBeInTheDocument());
    const responsesTab = screen.getByText(/Responses/);
    fireEvent.click(responsesTab);
    await waitFor(() => expect(screen.getByText("No responses recorded yet")).toBeInTheDocument());
  });

  it("handles fetch error gracefully", async () => {
    mockFetch.mockRejectedValueOnce(new Error("Network error"));
    const consoleSpy = jest.spyOn(console, "error").mockImplementation(() => {});
    render(<ImmuneSystemPanel />);
    await waitFor(() => expect(screen.queryByText("Loading immune system...")).not.toBeInTheDocument());
    consoleSpy.mockRestore();
  });

  it("renders detector status indicators", async () => {
    const data = mockImmuneData();
    setupMock(data);
    render(<ImmuneSystemPanel />);
    await waitFor(() => expect(screen.getByText("memory detector")).toBeInTheDocument());
    await waitFor(() => expect(screen.getByText("3 threats")).toBeInTheDocument());
  });

  it("renders response success/failure indicators", async () => {
    const data = mockImmuneData();
    setupMock(data);
    render(<ImmuneSystemPanel />);
    await waitFor(() => expect(screen.getByText(/Responses/)).toBeInTheDocument());
    const responsesTab = screen.getByText(/Responses/);
    fireEvent.click(responsesTab);
    await waitFor(() => expect(screen.getByText("✓ cache_clear")).toBeInTheDocument());
    await waitFor(() => expect(screen.getByText("✗ throttle")).toBeInTheDocument());
  });

  it("renders healthy status banner", async () => {
    const data = mockImmuneData();
    data.health.status = "healthy";
    data.health.overall = 0.98;
    setupMock(data);
    render(<ImmuneSystemPanel />);
    await waitFor(() => expect(screen.getByText("System Health: healthy")).toBeInTheDocument());
  });

  it("renders critical status banner", async () => {
    const data = mockImmuneData();
    data.health.status = "critical";
    data.health.overall = 0.3;
    setupMock(data);
    render(<ImmuneSystemPanel />);
    await waitFor(() => expect(screen.getByText("System Health: critical")).toBeInTheDocument());
  });
});
