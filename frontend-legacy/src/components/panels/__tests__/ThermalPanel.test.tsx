/**
 * Tests for ThermalPanel — loading, data display, reset, health score.
 */

import React from "react";
import { render, screen, waitFor, fireEvent } from "@testing-library/react";
import { ThermalPanel } from "../ThermalPanel";

const mockFetch = jest.fn();
global.fetch = mockFetch;

describe("ThermalPanel", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    mockFetch.mockReset();
  });

  function mockThermalData() {
    return {
      snapshot: {
        timestamp: "2024-01-01T12:00:00Z",
        gpu: { temperature: 72, power_limit: 350, clock_mhz: 1800, action: "stable", reason: "Within optimal range" },
        cpu: { temperature: 45, status: "normal", action: "" },
        regulation_count: 42,
        history: [
          { timestamp: "2024-01-01T11:59:00Z", gpu_temp: 71, cpu_temp: 44, power: 340, clock: 1790, action: "stable" },
          { timestamp: "2024-01-01T11:58:00Z", gpu_temp: 73, cpu_temp: 46, power: 360, clock: 1810, action: "throttle" },
        ],
      },
      health_score: 0.95,
    };
  }

  function setupMock(data: ReturnType<typeof mockThermalData>) {
    mockFetch.mockImplementation((url: string) => {
      if (url.includes("/api/thermal/status")) return Promise.resolve({ ok: true, json: () => Promise.resolve(data.snapshot) });
      if (url.includes("/api/thermal/health")) return Promise.resolve({ ok: true, json: () => Promise.resolve({ health_score: data.health_score }) });
      if (url.includes("/api/thermal/reset")) return Promise.resolve({ ok: true });
      return Promise.resolve({ ok: false });
    });
  }

  it("renders loading state", () => {
    mockFetch.mockImplementation(() => new Promise(() => {}));
    render(<ThermalPanel />);
    expect(screen.getByText("Loading thermal status...")).toBeInTheDocument();
  });

  it("renders header with GPU info", async () => {
    const data = mockThermalData();
    setupMock(data);
    render(<ThermalPanel />);
    await waitFor(() => expect(screen.getByText("Thermal Regulation")).toBeInTheDocument());
    await waitFor(() => expect(screen.getByText("RTX 5090")).toBeInTheDocument());
  });

  it("displays GPU temperature", async () => {
    const data = mockThermalData();
    setupMock(data);
    render(<ThermalPanel />);
    await waitFor(() => expect(screen.getByText("72.0°C")).toBeInTheDocument());
  });

  it("displays GPU power", async () => {
    const data = mockThermalData();
    setupMock(data);
    render(<ThermalPanel />);
    await waitFor(() => expect(screen.getByText("350W")).toBeInTheDocument());
  });

  it("displays GPU clock", async () => {
    const data = mockThermalData();
    setupMock(data);
    render(<ThermalPanel />);
    await waitFor(() => expect(screen.getByText("1800 MHz")).toBeInTheDocument());
  });

  it("displays GPU action", async () => {
    const data = mockThermalData();
    setupMock(data);
    render(<ThermalPanel />);
    await waitFor(() => expect(screen.getByText("stable")).toBeInTheDocument());
  });

  it("displays CPU temperature", async () => {
    const data = mockThermalData();
    setupMock(data);
    render(<ThermalPanel />);
    await waitFor(() => expect(screen.getByText("45.0°C")).toBeInTheDocument());
  });

  it("displays health score", async () => {
    const data = mockThermalData();
    setupMock(data);
    render(<ThermalPanel />);
    await waitFor(() => expect(screen.getByText("Health: 95%")).toBeInTheDocument());
  });

  it("shows green health indicator when score >= 0.9", async () => {
    const data = mockThermalData();
    data.health_score = 0.95;
    setupMock(data);
    render(<ThermalPanel />);
    await waitFor(() => expect(screen.getByText("Health: 95%")).toBeInTheDocument());
  });

  it("shows amber health indicator when score >= 0.7", async () => {
    const data = mockThermalData();
    data.health_score = 0.75;
    setupMock(data);
    render(<ThermalPanel />);
    await waitFor(() => expect(screen.getByText("Health: 75%")).toBeInTheDocument());
  });

  it("shows red health indicator when score < 0.7", async () => {
    const data = mockThermalData();
    data.health_score = 0.5;
    setupMock(data);
    render(<ThermalPanel />);
    await waitFor(() => expect(screen.getByText("Health: 50%")).toBeInTheDocument());
  });

  it("renders regulation stats", async () => {
    const data = mockThermalData();
    setupMock(data);
    render(<ThermalPanel />);
    await waitFor(() => expect(screen.getByText("Cycles")).toBeInTheDocument());
    await waitFor(() => expect(screen.getByText("42")).toBeInTheDocument());
  });

  it("renders history section", async () => {
    const data = mockThermalData();
    setupMock(data);
    render(<ThermalPanel />);
    await waitFor(() => expect(screen.getByText("Recent History")).toBeInTheDocument());
  });

  it("renders reset button", async () => {
    const data = mockThermalData();
    setupMock(data);
    render(<ThermalPanel />);
    await waitFor(() => expect(screen.getByText("Reset Optimal")).toBeInTheDocument());
  });

  it("calls reset API on button click", async () => {
    const data = mockThermalData();
    setupMock(data);
    render(<ThermalPanel />);
    await waitFor(() => expect(screen.getByText("Reset Optimal")).toBeInTheDocument());
    fireEvent.click(screen.getByText("Reset Optimal"));
    await waitFor(() => expect(mockFetch).toHaveBeenCalledWith("/api/thermal/reset", expect.objectContaining({ method: "POST" })));
  });

  it("shows error state on fetch failure", async () => {
    mockFetch.mockRejectedValueOnce(new Error("Network error"));
    const consoleSpy = jest.spyOn(console, "error").mockImplementation(() => {});
    render(<ThermalPanel />);
    await waitFor(() => expect(screen.getByText("Network error")).toBeInTheDocument());
    consoleSpy.mockRestore();
  });

  it("handles missing health score", async () => {
    const data = mockThermalData();
    data.health_score = undefined as any;
    setupMock(data);
    render(<ThermalPanel />);
    await waitFor(() => expect(screen.getByText("Thermal Regulation")).toBeInTheDocument());
    expect(screen.queryByText(/Health:/)).not.toBeInTheDocument();
  });

  it("handles null snapshot", async () => {
    mockFetch.mockImplementation((url: string) => {
      if (url.includes("/api/thermal/status")) return Promise.resolve({ ok: true, json: () => Promise.resolve(null) });
      if (url.includes("/api/thermal/health")) return Promise.resolve({ ok: true, json: () => Promise.resolve({ health_score: 0.9 }) });
      return Promise.resolve({ ok: false });
    });
    render(<ThermalPanel />);
    await waitFor(() => expect(screen.getByText("Thermal monitor not initialized")).toBeInTheDocument());
  });

  it("handles CPU with zero temperature", async () => {
    const data = mockThermalData();
    data.snapshot.cpu.temperature = 0;
    setupMock(data);
    render(<ThermalPanel />);
    await waitFor(() => expect(screen.getByText("—")).toBeInTheDocument());
  });

  it("renders CPU status", async () => {
    const data = mockThermalData();
    setupMock(data);
    render(<ThermalPanel />);
    await waitFor(() => expect(screen.getByText("normal")).toBeInTheDocument());
  });

  it("renders target temperature in header", async () => {
    const data = mockThermalData();
    setupMock(data);
    render(<ThermalPanel />);
    await waitFor(() => expect(screen.getByText("Target: 72°C")).toBeInTheDocument());
  });

  it("renders history entries with action colors", async () => {
    const data = mockThermalData();
    setupMock(data);
    render(<ThermalPanel />);
    await waitFor(() => expect(screen.getByText("Recent History")).toBeInTheDocument());
  });

  it("handles throttle action color", async () => {
    const data = mockThermalData();
    data.snapshot.gpu.action = "throttle";
    data.snapshot.gpu.temperature = 88;
    setupMock(data);
    render(<ThermalPanel />);
    await waitFor(() => expect(screen.getByText("throttle")).toBeInTheDocument());
  });

  it("handles relax action color", async () => {
    const data = mockThermalData();
    data.snapshot.gpu.action = "relax";
    data.snapshot.gpu.temperature = 60;
    setupMock(data);
    render(<ThermalPanel />);
    await waitFor(() => expect(screen.getByText("relax")).toBeInTheDocument());
  });
});
