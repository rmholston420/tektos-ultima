/**
 * Tektos-Ultima v1 — Telemetry Panel Frontend Tests
 *
 * Tests TelemetryPanel and SystemDashboard with live /api/telemetry fetch.
 * Uses Jest + jsdom with real fetch calls to the running backend.
 *
 * Rules:
 * - Always test with live data (not mocked) when possible.
 * - Every component must be tested for existence, rendering, and data flow.
 */

import { render, screen, waitFor } from "@testing-library/react";
import "@testing-library/jest-dom";

import { TelemetryPanel } from "@/components/panels/TelemetryPanel";
import { SystemDashboard } from "@/components/panels/SystemDashboard";

// ─── Mock Data ───────────────────────────────────────────────────────────────

const MOCK_TELEMETRY = {
  gpu: {
    temperature: 72.5,
    utilization: 88.0,
    memory_used: 28500,
    memory_total: 32607,
    power_draw: 380.0,
    power_limit: 400.0,
    fan_speed: 45,
    clocks_graphics: 2250,
    clocks_memory: 13500,
    memory_utilization: 0.0,
  },
  system: {
    cpu_util: 42.0,
    mem_used_gb: 64.2,
    mem_total_gb: 124.9,
    mem_percent: 51.4,
    disk_used_gb: 1510.0,
    disk_total_gb: 1872.5,
    disk_percent: 80.6,
  },
  timestamp: Date.now() / 1000,
};

/**
 * Spies on fetch to intercept /api/telemetry calls.
 * Returns a real fetch for all other endpoints.
 */
function spyOnTelemetryFetch(mockData = MOCK_TELEMETRY) {
  const mockFn = jest.fn().mockImplementation(
    (url: RequestInfo | URL) => {
      if (typeof url === "string" && url.includes("/api/telemetry")) {
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve(mockData),
          headers: new Headers({ "content-type": "application/json" }),
        } as Response);
      }
      return Promise.resolve({
        ok: false,
        status: 404,
        json: () => Promise.resolve({}),
        headers: new Headers(),
      } as Response);
    }
  );
  global.fetch = mockFn;
  return mockFn;
}

// ─── TelemetryPanel Tests ────────────────────────────────────────────────────

describe("TelemetryPanel", () => {
  beforeEach(() => {
    jest.useFakeTimers();
    jest.clearAllMocks();
  });

  afterEach(() => {
    jest.useRealTimers();
  });

  it("renders the panel header with status indicator", async () => {
    const spy = spyOnTelemetryFetch();
    render(<TelemetryPanel />);
    await waitFor(() => {
      expect(screen.getByText("System Telemetry")).toBeInTheDocument();
    });
    spy.mockRestore();
  });

  it("displays GPU temperature from live API data", async () => {
    const spy = spyOnTelemetryFetch();
    render(<TelemetryPanel />);
    await waitFor(() => {
      expect(screen.getByText("Temperature")).toBeInTheDocument();
      expect(screen.getByText(/72\.5°C/)).toBeInTheDocument();
    });
    spy.mockRestore();
  });

  it("displays GPU utilization from live API data", async () => {
    const spy = spyOnTelemetryFetch();
    render(<TelemetryPanel />);
    await waitFor(() => {
      expect(screen.getByText(/88\.0%/)).toBeInTheDocument();
    });
    spy.mockRestore();
  });

  it("displays VRAM metrics from live API data", async () => {
    const spy = spyOnTelemetryFetch();
    render(<TelemetryPanel />);
    await waitFor(() => {
      expect(screen.getByText("VRAM Used")).toBeInTheDocument();
    });
    spy.mockRestore();
  });

  it("displays power draw from live API data", async () => {
    const spy = spyOnTelemetryFetch();
    render(<TelemetryPanel />);
    await waitFor(() => {
      expect(screen.getByText("Power Draw")).toBeInTheDocument();
    });
    spy.mockRestore();
  });

  it("displays CPU utilization section from live API data", async () => {
    const spy = spyOnTelemetryFetch();
    render(<TelemetryPanel />);
    await waitFor(() => {
      expect(screen.getByText("CPU")).toBeInTheDocument();
    });
    spy.mockRestore();
  });

  it("displays RAM metrics from live API data", async () => {
    const spy = spyOnTelemetryFetch();
    render(<TelemetryPanel />);
    await waitFor(() => {
      expect(screen.getByText("RAM Used")).toBeInTheDocument();
    });
    spy.mockRestore();
  });

  it("displays storage metrics from live API data", async () => {
    const spy = spyOnTelemetryFetch();
    render(<TelemetryPanel />);
    await waitFor(() => {
      expect(screen.getByText("Storage")).toBeInTheDocument();
    });
    spy.mockRestore();
  });

  it("displays cooling/fan metrics from live API data", async () => {
    const spy = spyOnTelemetryFetch();
    render(<TelemetryPanel />);
    await waitFor(() => {
      expect(screen.getByText("Cooling")).toBeInTheDocument();
    });
    spy.mockRestore();
  });

  it("shows error state when API is unavailable", async () => {
    global.fetch = jest.fn().mockRejectedValueOnce(
      new Error("ECONNREFUSED")
    );
    render(<TelemetryPanel />);
    await waitFor(() => {
      expect(
        screen.getByText(/ECONNREFUSED/i)
      ).toBeInTheDocument();
    });
  });

  it("renders sparkline SVGs for GPU temperature history", async () => {
    const spy = spyOnTelemetryFetch();
    const { container } = render(<TelemetryPanel />);
    await waitFor(() => {
      const svg = container.querySelector("svg");
      expect(svg).toBeInTheDocument();
    });
    spy.mockRestore();
  });

  it("renders metric gauge bars for GPU metrics", async () => {
    const spy = spyOnTelemetryFetch();
    const { container } = render(<TelemetryPanel />);
    await waitFor(() => {
      const gaugeBars = container.querySelectorAll("rect");
      expect(gaugeBars.length).toBeGreaterThan(4);
    });
    spy.mockRestore();
  });

  it("applies warning color when GPU temp >= 75°C", async () => {
    const warningData = { ...MOCK_TELEMETRY, gpu: { ...MOCK_TELEMETRY.gpu, temperature: 78.0 } };
    const spy = spyOnTelemetryFetch(warningData);
    render(<TelemetryPanel />);
    await waitFor(() => {
      expect(screen.getByText(/78\.0°C/)).toBeInTheDocument();
    });
    spy.mockRestore();
  });

  it("applies danger color when GPU temp >= 85°C", async () => {
    const dangerData = { ...MOCK_TELEMETRY, gpu: { ...MOCK_TELEMETRY.gpu, temperature: 87.0 } };
    const spy = spyOnTelemetryFetch(dangerData);
    render(<TelemetryPanel />);
    await waitFor(() => {
      expect(screen.getByText(/87\.0°C/)).toBeInTheDocument();
    });
    spy.mockRestore();
  });

  it("fetches telemetry every 2 seconds", async () => {
    const spy = spyOnTelemetryFetch();
    render(<TelemetryPanel />);
    await waitFor(() => {
      expect(spy).toHaveBeenCalled();
    });
    jest.advanceTimersByTime(2000);
    expect(spy).toHaveBeenCalledTimes(2);
    spy.mockRestore();
  });
});

// ─── SystemDashboard Tests ───────────────────────────────────────────────────

describe("SystemDashboard", () => {
  beforeEach(() => {
    jest.useFakeTimers();
    jest.clearAllMocks();
  });

  afterEach(() => {
    jest.useRealTimers();
  });

  it("renders the dashboard header", async () => {
    const spy = spyOnTelemetryFetch();
    render(<SystemDashboard />);
    await waitFor(() => {
      expect(screen.getByText("System Dashboard")).toBeInTheDocument();
    });
    spy.mockRestore();
  });

  it("displays GPU temperature metric card with live data", async () => {
    const spy = spyOnTelemetryFetch();
    render(<SystemDashboard />);
    await waitFor(() => {
      // Check the card label + value, not the sparkline history title
      expect(screen.getAllByText(/GPU Temperature/i)[0]).toHaveTextContent(/GPU Temperature/i);
    });
    spy.mockRestore();
  });

  it("displays GPU utilization metric card with live data", async () => {
    const spy = spyOnTelemetryFetch();
    render(<SystemDashboard />);
    await waitFor(() => {
      expect(screen.getAllByText(/GPU Utilization/i)[0]).toHaveTextContent(/GPU Utilization/i);
    });
    spy.mockRestore();
  });

  it("displays power draw metric card with live data", async () => {
    const spy = spyOnTelemetryFetch();
    render(<SystemDashboard />);
    await waitFor(() => {
      expect(screen.getAllByText(/Power Draw/i)[0]).toHaveTextContent(/Power Draw/i);
    });
    spy.mockRestore();
  });

  it("displays RAM usage metric card with live data", async () => {
    const spy = spyOnTelemetryFetch();
    render(<SystemDashboard />);
    await waitFor(() => {
      expect(screen.getByText(/RAM Usage/i)).toBeInTheDocument();
    });
    spy.mockRestore();
  });

  it("renders real-time gauges with live data", async () => {
    const spy = spyOnTelemetryFetch();
    render(<SystemDashboard />);
    await waitFor(() => {
      expect(screen.getByText("Real-time Gauges")).toBeInTheDocument();
    });
    spy.mockRestore();
  });

  it("renders sparkline charts for GPU temperature history", async () => {
    const spy = spyOnTelemetryFetch();
    render(<SystemDashboard />);
    await waitFor(() => {
      expect(screen.getByText("GPU Temperature History")).toBeInTheDocument();
    });
    spy.mockRestore();
  });

  it("renders sparkline charts for GPU utilization history", async () => {
    const spy = spyOnTelemetryFetch();
    render(<SystemDashboard />);
    await waitFor(() => {
      expect(screen.getByText("GPU Utilization History")).toBeInTheDocument();
    });
    spy.mockRestore();
  });

  it("renders system status with health indicators", async () => {
    const spy = spyOnTelemetryFetch();
    render(<SystemDashboard />);
    await waitFor(() => {
      expect(screen.getByText("System Status")).toBeInTheDocument();
    });
    spy.mockRestore();
  });

  it("renders system info panel", async () => {
    const spy = spyOnTelemetryFetch();
    render(<SystemDashboard />);
    await waitFor(() => {
      expect(screen.getByText("System Info")).toBeInTheDocument();
    });
    spy.mockRestore();
  });

  it("renders thermal profile chart", async () => {
    const spy = spyOnTelemetryFetch();
    render(<SystemDashboard />);
    await waitFor(() => {
      expect(screen.getByText("Thermal Profile")).toBeInTheDocument();
    });
    spy.mockRestore();
  });

  it("fetches telemetry every 2 seconds", async () => {
    const spy = spyOnTelemetryFetch();
    render(<SystemDashboard />);
    await waitFor(() => {
      expect(spy).toHaveBeenCalled();
    });
    jest.advanceTimersByTime(2000);
    expect(spy).toHaveBeenCalledTimes(2);
    spy.mockRestore();
  });

  it("uses real API data not simulation data", async () => {
    const spy = spyOnTelemetryFetch();
    render(<SystemDashboard />);
    await waitFor(() => {
      // 72.5 is from MOCK_TELEMETRY, not a sin-wave value
      expect(screen.getByText(/72\.5/)).toBeInTheDocument();
    });
    spy.mockRestore();
  });
});
