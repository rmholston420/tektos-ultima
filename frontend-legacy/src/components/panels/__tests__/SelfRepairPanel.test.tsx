/**
 * Tests for SelfRepairPanel — status, history, trigger form.
 */

import React from "react";
import { render, screen, waitFor, fireEvent } from "@testing-library/react";
import { SelfRepairPanel } from "../SelfRepairPanel";

const mockFetch = jest.fn();
global.fetch = mockFetch;

describe("SelfRepairPanel", () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  function mockRepairData() {
    return {
      status: {
        running: true, uptime_seconds: 7200, total_repairs: 25,
        completed_repairs: 20, failed_repairs: 3, degraded_repairs: 2,
        strategies_registered: 5, workflows_registered: 3,
        health_trend: "improving",
        latest_health: { cpu_temp: 72, gpu_temp: 68, memory_usage: 0.75 },
        effectiveness: { success_rate: 0.85, avg_time_seconds: 45 },
      },
      history: [
        {
          record_id: "rep-001", threat_category: "memory_leak", threat_severity: "2",
          description: "Memory leak in session store", status: "COMPLETED",
          strategy_used: "cache_clear", verification_passed: true,
          repair_actions: ["Cleared cache", "Restarted worker"],
          time_to_diagnose_seconds: 10, time_to_repair_seconds: 30, time_to_verify_seconds: 5,
          total_time_seconds: 45, completed_at: 1704067200,
        },
        {
          record_id: "rep-002", threat_category: "cpu_spike", threat_severity: "3",
          description: "CPU spike during batch processing", status: "FAILED",
          verification_passed: false, verification_details: "Timeout",
          repair_actions: ["Throttled workers"],
          error: "Repair exceeded time limit",
          total_time_seconds: 120,
        },
      ],
    };
  }

  function setupMock(data: ReturnType<typeof mockRepairData>) {
    mockFetch.mockImplementation((url: string, opts?: any) => {
      if (url.includes("/api/self_repair/status")) return Promise.resolve({ ok: true, json: () => Promise.resolve(data.status) });
      if (url.includes("/api/self_repair/history")) return Promise.resolve({ ok: true, json: () => Promise.resolve({ history: data.history }) });
      if (url.includes("/api/self_repair/repair")) return Promise.resolve({ ok: true, json: () => Promise.resolve({ success: true }) });
      return Promise.resolve({ ok: false });
    });
  }

  it("renders loading state", () => {
    mockFetch.mockImplementation(() => new Promise(() => {}));
    render(<SelfRepairPanel />);
    expect(screen.getByText("Loading self-repair status...")).toBeInTheDocument();
  });

  it("renders header with running indicator", async () => {
    const data = mockRepairData();
    setupMock(data);
    render(<SelfRepairPanel />);
    await waitFor(() => expect(screen.getByText("Self-Repair Engine")).toBeInTheDocument());
    await waitFor(() => expect(screen.getByText("Running")).toBeInTheDocument());
  });

  it("renders uptime", async () => {
    const data = mockRepairData();
    setupMock(data);
    render(<SelfRepairPanel />);
    await waitFor(() => expect(screen.getByText("Uptime")).toBeInTheDocument());
  });

  it("renders strategies count", async () => {
    const data = mockRepairData();
    setupMock(data);
    render(<SelfRepairPanel />);
    await waitFor(() => expect(screen.getByText("Strategies")).toBeInTheDocument());
    await waitFor(() => expect(screen.getByText("5")).toBeInTheDocument());
  });

  it("renders workflows count", async () => {
    const data = mockRepairData();
    setupMock(data);
    render(<SelfRepairPanel />);
    await waitFor(() => expect(screen.getByText("Workflows")).toBeInTheDocument());
    // workflows_registered is 3, but total_repairs is also 25 — use a unique value
    await waitFor(() => expect(screen.getByText("3")).toBeInTheDocument());
  });

  it("renders health trend", async () => {
    const data = mockRepairData();
    setupMock(data);
    render(<SelfRepairPanel />);
    await waitFor(() => expect(screen.getByText("Health Trend")).toBeInTheDocument());
    await waitFor(() => expect(screen.getByText("improving")).toBeInTheDocument());
  });

  it("renders repair summary counts", async () => {
    const data = mockRepairData();
    setupMock(data);
    render(<SelfRepairPanel />);
    await waitFor(() => expect(screen.getByText("Repair Summary")).toBeInTheDocument());
    await waitFor(() => expect(screen.getByText("Total")).toBeInTheDocument());
    await waitFor(() => expect(screen.getByText("25")).toBeInTheDocument());
    await waitFor(() => expect(screen.getByText("Completed")).toBeInTheDocument());
    await waitFor(() => expect(screen.getByText("20")).toBeInTheDocument());
    await waitFor(() => expect(screen.getByText("Failed")).toBeInTheDocument());
  });

  it("renders degraded repairs count", async () => {
    const data = mockRepairData();
    setupMock(data);
    render(<SelfRepairPanel />);
    await waitFor(() => expect(screen.getByText("Degraded Repairs")).toBeInTheDocument());
    await waitFor(() => expect(screen.getByText("2")).toBeInTheDocument());
  });

  it("renders latest health check", async () => {
    const data = mockRepairData();
    setupMock(data);
    render(<SelfRepairPanel />);
    await waitFor(() => expect(screen.getByText("Latest Health Check")).toBeInTheDocument());
  });

  it("renders effectiveness tracking", async () => {
    const data = mockRepairData();
    setupMock(data);
    render(<SelfRepairPanel />);
    await waitFor(() => expect(screen.getByText("Effectiveness Tracking")).toBeInTheDocument());
  });

  it("renders history tab with records", async () => {
    const data = mockRepairData();
    setupMock(data);
    render(<SelfRepairPanel />);
    await waitFor(() => expect(screen.getByText("Self-Repair Engine")).toBeInTheDocument());
    const histTab = screen.getByText("History");
    fireEvent.click(histTab);
    await waitFor(() => expect(screen.getByText("rep-001")).toBeInTheDocument());
    await waitFor(() => expect(screen.getByText("COMPLETED")).toBeInTheDocument());
  });

  it("renders history with severity labels", async () => {
    const data = mockRepairData();
    setupMock(data);
    render(<SelfRepairPanel />);
    await waitFor(() => expect(screen.getByText("Self-Repair Engine")).toBeInTheDocument());
    const histTab = screen.getByText("History");
    fireEvent.click(histTab);
    await waitFor(() => expect(screen.getByText("HIGH")).toBeInTheDocument());
  });

  it("renders repair strategy", async () => {
    const data = mockRepairData();
    setupMock(data);
    render(<SelfRepairPanel />);
    await waitFor(() => expect(screen.getByText("Self-Repair Engine")).toBeInTheDocument());
    const histTab = screen.getByText("History");
    fireEvent.click(histTab);
    await waitFor(() => expect(screen.getByText("Strategy:")).toBeInTheDocument());
    await waitFor(() => expect(screen.getByText("cache_clear")).toBeInTheDocument());
  });

  it("renders repair actions list", async () => {
    const data = mockRepairData();
    setupMock(data);
    render(<SelfRepairPanel />);
    await waitFor(() => expect(screen.getByText("Self-Repair Engine")).toBeInTheDocument());
    const histTab = screen.getByText("History");
    fireEvent.click(histTab);
    await waitFor(() => expect(screen.getByText("Actions:")).toBeInTheDocument());
    await waitFor(() => expect(screen.getByText("Cleared cache")).toBeInTheDocument());
  });

  it("renders verification status", async () => {
    const data = mockRepairData();
    setupMock(data);
    render(<SelfRepairPanel />);
    await waitFor(() => expect(screen.getByText("Self-Repair Engine")).toBeInTheDocument());
    const histTab = screen.getByText("History");
    fireEvent.click(histTab);
    await waitFor(() => expect(screen.getByText("Verify:")).toBeInTheDocument());
    await waitFor(() => expect(screen.getByText("Passed")).toBeInTheDocument());
  });

  it("renders error on failed repair", async () => {
    const data = mockRepairData();
    setupMock(data);
    render(<SelfRepairPanel />);
    await waitFor(() => expect(screen.getByText("Self-Repair Engine")).toBeInTheDocument());
    const histTab = screen.getByText("History");
    fireEvent.click(histTab);
    await waitFor(() => expect(screen.getByText("Error: Repair exceeded time limit")).toBeInTheDocument());
  });

  it("renders trigger tab with form", async () => {
    const data = mockRepairData();
    setupMock(data);
    render(<SelfRepairPanel />);
    await waitFor(() => expect(screen.getByText("Self-Repair Engine")).toBeInTheDocument());
    const triggerTab = screen.getByText("Trigger");
    fireEvent.click(triggerTab);
    await waitFor(() => expect(screen.getByText("Manual Repair Trigger")).toBeInTheDocument());
    await waitFor(() => expect(screen.getByText("Threat Category")).toBeInTheDocument());
    await waitFor(() => expect(screen.getByText("Severity (0-3)")).toBeInTheDocument());
  });

  it("renders trigger form with default values", async () => {
    const data = mockRepairData();
    setupMock(data);
    render(<SelfRepairPanel />);
    await waitFor(() => expect(screen.getByText("Self-Repair Engine")).toBeInTheDocument());
    const triggerTab = screen.getByText("Trigger");
    fireEvent.click(triggerTab);
    await waitFor(() => expect(screen.getByText("Trigger Repair")).toBeInTheDocument());
  });

  it("calls repair API on trigger", async () => {
    const data = mockRepairData();
    setupMock(data);
    render(<SelfRepairPanel />);
    await waitFor(() => expect(screen.getByText("Self-Repair Engine")).toBeInTheDocument());
    const triggerTab = screen.getByText("Trigger");
    fireEvent.click(triggerTab);
    fireEvent.click(screen.getByText("Trigger Repair"));
    await waitFor(() => expect(mockFetch).toHaveBeenCalledWith("/api/self_repair/repair", expect.any(Object)));
  });

  it("shows trigger result", async () => {
    const data = mockRepairData();
    setupMock(data);
    render(<SelfRepairPanel />);
    await waitFor(() => expect(screen.getByText("Self-Repair Engine")).toBeInTheDocument());
    const triggerTab = screen.getByText("Trigger");
    fireEvent.click(triggerTab);
    fireEvent.click(screen.getByText("Trigger Repair"));
    await waitFor(() => expect(screen.getByText("Result")).toBeInTheDocument());
  });

  it("shows no history message when empty", async () => {
    const data = mockRepairData();
    data.history = [];
    setupMock(data);
    render(<SelfRepairPanel />);
    await waitFor(() => expect(screen.getByText("Self-Repair Engine")).toBeInTheDocument());
    const histTab = screen.getByText("History");
    fireEvent.click(histTab);
    await waitFor(() => expect(screen.getByText("No repair history yet")).toBeInTheDocument());
  });

  it("handles fetch error gracefully", async () => {
    mockFetch.mockRejectedValueOnce(new Error("Network error"));
    const consoleSpy = jest.spyOn(console, "error").mockImplementation(() => {});
    render(<SelfRepairPanel />);
    await waitFor(() => expect(screen.getByText("Network error")).toBeInTheDocument());
    consoleSpy.mockRestore();
  });

  it("handles null status", async () => {
    mockFetch.mockImplementation((url: string) => {
      if (url.includes("/api/self_repair/status")) return Promise.resolve({ ok: true, json: () => Promise.resolve(null) });
      if (url.includes("/api/self_repair/history")) return Promise.resolve({ ok: true, json: () => Promise.resolve({ history: [] }) });
      return Promise.resolve({ ok: false });
    });
    render(<SelfRepairPanel />);
    await waitFor(() => expect(screen.getByText("Self-repair engine not initialized")).toBeInTheDocument());
  });

  it("shows stopped indicator when not running", async () => {
    const data = mockRepairData();
    data.status.running = false;
    setupMock(data);
    render(<SelfRepairPanel />);
    await waitFor(() => expect(screen.getByText("Stopped")).toBeInTheDocument());
  });

  it("renders severity labels correctly", async () => {
    const data = mockRepairData();
    setupMock(data);
    render(<SelfRepairPanel />);
    await waitFor(() => expect(screen.getByText("Self-Repair Engine")).toBeInTheDocument());
    const histTab = screen.getByText("History");
    fireEvent.click(histTab);
    await waitFor(() => expect(screen.getByText("CRITICAL")).toBeInTheDocument());
  });

  it("renders degraded repair indicator", async () => {
    const data = mockRepairData();
    setupMock(data);
    render(<SelfRepairPanel />);
    await waitFor(() => expect(screen.getByText("Degraded Repairs")).toBeInTheDocument());
  });

  it("renders trigger form with context textarea", async () => {
    const data = mockRepairData();
    setupMock(data);
    render(<SelfRepairPanel />);
    await waitFor(() => expect(screen.getByText("Self-Repair Engine")).toBeInTheDocument());
    const triggerTab = screen.getByText("Trigger");
    fireEvent.click(triggerTab);
    await waitFor(() => expect(screen.getByText("Context (JSON, optional)")).toBeInTheDocument());
  });

  it("renders trigger form with severity select", async () => {
    const data = mockRepairData();
    setupMock(data);
    render(<SelfRepairPanel />);
    await waitFor(() => expect(screen.getByText("Self-Repair Engine")).toBeInTheDocument());
    const triggerTab = screen.getByText("Trigger");
    fireEvent.click(triggerTab);
    await waitFor(() => expect(screen.getByText("0 - LOW")).toBeInTheDocument());
    await waitFor(() => expect(screen.getByText("3 - CRITICAL")).toBeInTheDocument());
  });
});
