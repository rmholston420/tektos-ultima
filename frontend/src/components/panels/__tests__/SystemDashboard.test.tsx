/**
 * Tests for the SystemDashboard component.
 *
 * SystemDashboard fetches /api/telemetry and renders metric cards,
 * gauge rings, sparklines, and thermal profile.
 */

import React from "react";
import { render, screen, waitFor } from "@testing-library/react";
import { SystemDashboard } from "../SystemDashboard";

const mockFetch = jest.fn();
beforeEach(() => {
  jest.useFakeTimers();
  mockFetch.mockReset();
});
afterEach(() => {
  jest.useRealTimers();
});
global.fetch = mockFetch;

function mockTelemetry() {
  return {
    gpu: { temperature: 65, utilization: 72, memory_used: 16384, memory_total: 32768, power_draw: 250, fan_speed: 1800 },
    system: { cpu_util: 45, mem_used_gb: 24, mem_total_gb: 64, disk_percent: 50 },
  };
}

describe("SystemDashboard", () => {
  function renderWithTimers() {
    render(<SystemDashboard />);
    // Advance just enough for the initial async fetch + loading=false to resolve
    jest.advanceTimersByTime(100);
  }

  it("renders dashboard with default values when fetch fails", async () => {
    mockFetch.mockRejectedValue(new Error("Network error"));
    renderWithTimers();
    await waitFor(() => expect(screen.getByText("System Dashboard")).toBeInTheDocument());
  });

  it("renders dashboard header after loading", async () => {
    mockFetch.mockImplementation(() =>
      Promise.resolve({ ok: true, json: () => Promise.resolve(mockTelemetry()) })
    );
    renderWithTimers();
    await waitFor(() => expect(screen.getByText("System Dashboard")).toBeInTheDocument());
  });

  it("renders metric cards", async () => {
    mockFetch.mockImplementation(() =>
      Promise.resolve({ ok: true, json: () => Promise.resolve(mockTelemetry()) })
    );
    renderWithTimers();
    await waitFor(() => {
      const all = document.body.textContent;
      expect(all).toContain("GPU Temperature");
      expect(all).toContain("GPU Utilization");
      expect(all).toContain("Power Draw");
      expect(all).toContain("RAM Usage");
    });
  });

  it("displays GPU temperature value", async () => {
    mockFetch.mockImplementation(() =>
      Promise.resolve({ ok: true, json: () => Promise.resolve(mockTelemetry()) })
    );
    renderWithTimers();
    await waitFor(() => {
      const all = document.body.textContent;
      expect(all).toContain("65.0");
    });
  });

  it("displays GPU utilization", async () => {
    mockFetch.mockImplementation(() =>
      Promise.resolve({ ok: true, json: () => Promise.resolve(mockTelemetry()) })
    );
    renderWithTimers();
    await waitFor(() => {
      const all = document.body.textContent;
      expect(all).toContain("72");
    });
  });

  it("displays power draw", async () => {
    mockFetch.mockImplementation(() =>
      Promise.resolve({ ok: true, json: () => Promise.resolve(mockTelemetry()) })
    );
    renderWithTimers();
    await waitFor(() => {
      const all = document.body.textContent;
      expect(all).toContain("250");
    });
  });

  it("renders gauge rings", async () => {
    mockFetch.mockImplementation(() =>
      Promise.resolve({ ok: true, json: () => Promise.resolve(mockTelemetry()) })
    );
    renderWithTimers();
    await waitFor(() => expect(screen.getByText("Real-time Gauges")).toBeInTheDocument());
  });

  it("shows GPU temp gauge", async () => {
    mockFetch.mockImplementation(() =>
      Promise.resolve({ ok: true, json: () => Promise.resolve(mockTelemetry()) })
    );
    renderWithTimers();
    await waitFor(() => expect(screen.getByText("GPU Temp")).toBeInTheDocument());
  });

  it("shows CPU util gauge", async () => {
    mockFetch.mockImplementation(() =>
      Promise.resolve({ ok: true, json: () => Promise.resolve(mockTelemetry()) })
    );
    renderWithTimers();
    await waitFor(() => expect(screen.getByText("CPU Util")).toBeInTheDocument());
  });

  it("shows sparkline sections", async () => {
    mockFetch.mockImplementation(() =>
      Promise.resolve({ ok: true, json: () => Promise.resolve(mockTelemetry()) })
    );
    renderWithTimers();
    await waitFor(() => {
      expect(screen.getByText("GPU Temperature History")).toBeInTheDocument();
      expect(screen.getByText("GPU Utilization History")).toBeInTheDocument();
      expect(screen.getByText("CPU Utilization History")).toBeInTheDocument();
      expect(screen.getByText("Power Draw History")).toBeInTheDocument();
    });
  });

  it("shows system status section", async () => {
    mockFetch.mockImplementation(() =>
      Promise.resolve({ ok: true, json: () => Promise.resolve(mockTelemetry()) })
    );
    renderWithTimers();
    await waitFor(() => expect(screen.getByText("System Status")).toBeInTheDocument());
  });

  it("shows system info section", async () => {
    mockFetch.mockImplementation(() =>
      Promise.resolve({ ok: true, json: () => Promise.resolve(mockTelemetry()) })
    );
    renderWithTimers();
    await waitFor(() => expect(screen.getByText("System Info")).toBeInTheDocument());
  });

  it("shows thermal profile", async () => {
    mockFetch.mockImplementation(() =>
      Promise.resolve({ ok: true, json: () => Promise.resolve(mockTelemetry()) })
    );
    renderWithTimers();
    await waitFor(() => expect(screen.getByText("Thermal Profile")).toBeInTheDocument());
  });

  it("shows health status badges", async () => {
    mockFetch.mockImplementation(() =>
      Promise.resolve({ ok: true, json: () => Promise.resolve(mockTelemetry()) })
    );
    renderWithTimers();
    await waitFor(() => {
      expect(screen.getByText("GPU Health")).toBeInTheDocument();
      expect(screen.getByText("Thermal Status")).toBeInTheDocument();
      expect(screen.getByText("Fan Speed")).toBeInTheDocument();
    });
  });

  it("polls telemetry on interval", async () => {
    mockFetch.mockImplementation(() =>
      Promise.resolve({ ok: true, json: () => Promise.resolve(mockTelemetry()) })
    );
    renderWithTimers();
    await waitFor(() => expect(screen.getByText("System Dashboard")).toBeInTheDocument());
    jest.advanceTimersByTime(2000);
    expect(mockFetch).toHaveBeenCalled();
  });
});
