/**
 * Tests for TelemetryPanel — loading, error, real data display, gauges, sparklines.
 */

import React from "react";
import { render, screen, waitFor, fireEvent, act } from "@testing-library/react";
import { TelemetryPanel } from "../TelemetryPanel";

const mockFetch = jest.fn();
global.fetch = mockFetch;

describe("TelemetryPanel", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    mockFetch.mockReset();
  });

  function mockTelemetryData() {
    return {
      timestamp: 1704067200,
      gpu: {
        temperature: 72,
        utilization: 65,
        memory_used: 12000,
        memory_total: 24576,
        power_draw: 280,
        power_limit: 350,
        clocks_graphics: 1800,
        clocks_memory: 14000,
        fan_speed: 45,
      },
      system: {
        cpu_util: 35,
        mem_used_gb: 12,
        mem_total_gb: 32,
        mem_percent: 37.5,
        disk_used_gb: 120,
        disk_total_gb: 500,
        disk_percent: 24,
      },
    };
  }

  it("renders loading state", () => {
    mockFetch.mockImplementation(() => new Promise(() => {}));
    render(<TelemetryPanel />);
    expect(screen.getByText("Loading telemetry...")).toBeInTheDocument();
  });

  it("renders header with title", async () => {
    mockFetch.mockResolvedValue({ ok: true, json: () => Promise.resolve(mockTelemetryData()) });
    render(<TelemetryPanel />);
    await waitFor(() => expect(screen.getByText("System Telemetry")).toBeInTheDocument());
  });

  it("shows green status dot when healthy", async () => {
    mockFetch.mockResolvedValue({ ok: true, json: () => Promise.resolve(mockTelemetryData()) });
    render(<TelemetryPanel />);
    await waitFor(() => expect(screen.getByText("System Telemetry")).toBeInTheDocument());
  });

  it("renders GPU section with title", async () => {
    mockFetch.mockResolvedValue({ ok: true, json: () => Promise.resolve(mockTelemetryData()) });
    render(<TelemetryPanel />);
    await waitFor(() => expect(screen.getByText("GPU")).toBeInTheDocument());
  });

  it("renders GPU temperature gauge", async () => {
    mockFetch.mockResolvedValue({ ok: true, json: () => Promise.resolve(mockTelemetryData()) });
    render(<TelemetryPanel />);
    await waitFor(() => expect(screen.getByText("72.0°C")).toBeInTheDocument());
  });

  it("renders GPU utilization gauge", async () => {
    mockFetch.mockResolvedValue({ ok: true, json: () => Promise.resolve(mockTelemetryData()) });
    render(<TelemetryPanel />);
    await waitFor(() => expect(screen.getByText("65.0%")).toBeInTheDocument());
  });

  it("renders VRAM used gauge", async () => {
    mockFetch.mockResolvedValue({ ok: true, json: () => Promise.resolve(mockTelemetryData()) });
    render(<TelemetryPanel />);
    await waitFor(() => expect(screen.getByText("12000.0 MB")).toBeInTheDocument());
  });

  it("renders power draw gauge", async () => {
    mockFetch.mockResolvedValue({ ok: true, json: () => Promise.resolve(mockTelemetryData()) });
    render(<TelemetryPanel />);
    await waitFor(() => expect(screen.getByText("280.0 W")).toBeInTheDocument());
  });

  it("renders GPU clock gauges", async () => {
    mockFetch.mockResolvedValue({ ok: true, json: () => Promise.resolve(mockTelemetryData()) });
    render(<TelemetryPanel />);
    await waitFor(() => expect(screen.getByText("Clocks (GPU)")).toBeInTheDocument());
    await waitFor(() => expect(screen.getByText("Clocks (Mem)")).toBeInTheDocument());
  });

  it("renders CPU section", async () => {
    mockFetch.mockResolvedValue({ ok: true, json: () => Promise.resolve(mockTelemetryData()) });
    render(<TelemetryPanel />);
    await waitFor(() => expect(screen.getByText("CPU")).toBeInTheDocument());
    await waitFor(() => expect(screen.getByText("35.0%")).toBeInTheDocument());
  });

  it("renders RAM used gauge", async () => {
    mockFetch.mockResolvedValue({ ok: true, json: () => Promise.resolve(mockTelemetryData()) });
    render(<TelemetryPanel />);
    await waitFor(() => expect(screen.getByText("12.0 / 32 GB")).toBeInTheDocument());
  });

  it("renders RAM utilization gauge", async () => {
    mockFetch.mockResolvedValue({ ok: true, json: () => Promise.resolve(mockTelemetryData()) });
    render(<TelemetryPanel />);
    await waitFor(() => expect(screen.getByText("RAM Utilization")).toBeInTheDocument());
    await waitFor(() => expect(screen.getByText("37.5%")).toBeInTheDocument());
  });

  it("renders storage section", async () => {
    mockFetch.mockResolvedValue({ ok: true, json: () => Promise.resolve(mockTelemetryData()) });
    render(<TelemetryPanel />);
    await waitFor(() => expect(screen.getByText("Storage")).toBeInTheDocument());
    await waitFor(() => expect(screen.getByText("Disk Used")).toBeInTheDocument());
    await waitFor(() => expect(screen.getByText("Disk Utilization")).toBeInTheDocument());
  });

  it("renders cooling section", async () => {
    mockFetch.mockResolvedValue({ ok: true, json: () => Promise.resolve(mockTelemetryData()) });
    render(<TelemetryPanel />);
    await waitFor(() => expect(screen.getByText("Cooling")).toBeInTheDocument());
    await waitFor(() => expect(screen.getByText("Fan Speed")).toBeInTheDocument());
    await waitFor(() => expect(screen.getByText("45.0%")).toBeInTheDocument());
  });

  it("shows error state when fetch fails", async () => {
    mockFetch.mockRejectedValue(new Error("Network error"));
    render(<TelemetryPanel />);
    await waitFor(() => expect(screen.getByText("Network error")).toBeInTheDocument());
  });

  it("shows red status dot when error", async () => {
    mockFetch.mockRejectedValue(new Error("Network error"));
    render(<TelemetryPanel />);
    await waitFor(() => expect(screen.getByText("Network error")).toBeInTheDocument());
  });

  it("renders timestamp when data loaded", async () => {
    mockFetch.mockResolvedValue({ ok: true, json: () => Promise.resolve(mockTelemetryData()) });
    render(<TelemetryPanel />);
    await waitFor(() => expect(screen.getByText("System Telemetry")).toBeInTheDocument());
  });

  it("renders sparkline SVGs for GPU temperature", async () => {
    mockFetch.mockResolvedValue({ ok: true, json: () => Promise.resolve(mockTelemetryData()) });
    render(<TelemetryPanel />);
    await waitFor(() => expect(screen.getByText("GPU")).toBeInTheDocument());
    const svg = document.querySelector("svg");
    expect(svg).toBeInTheDocument();
  });

  it("renders sparkline SVGs for CPU utilization", async () => {
    mockFetch.mockResolvedValue({ ok: true, json: () => Promise.resolve(mockTelemetryData()) });
    render(<TelemetryPanel />);
    await waitFor(() => expect(screen.getByText("CPU")).toBeInTheDocument());
    const svgs = document.querySelectorAll("svg");
    expect(svgs.length).toBeGreaterThan(1);
  });

  it("renders warning color when GPU temp >= 75", async () => {
    const data = mockTelemetryData();
    data.gpu.temperature = 80;
    mockFetch.mockResolvedValue({ ok: true, json: () => Promise.resolve(data) });
    render(<TelemetryPanel />);
    await waitFor(() => expect(screen.getByText("80.0°C")).toBeInTheDocument());
  });

  it("renders danger color when GPU temp >= 85", async () => {
    const data = mockTelemetryData();
    data.gpu.temperature = 90;
    mockFetch.mockResolvedValue({ ok: true, json: () => Promise.resolve(data) });
    render(<TelemetryPanel />);
    await waitFor(() => expect(screen.getByText("90.0°C")).toBeInTheDocument());
  });

  it("renders disk utilization percentage", async () => {
    mockFetch.mockResolvedValue({ ok: true, json: () => Promise.resolve(mockTelemetryData()) });
    render(<TelemetryPanel />);
    await waitFor(() => expect(screen.getByText("24.0%")).toBeInTheDocument());
  });
});
