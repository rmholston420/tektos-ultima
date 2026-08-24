/**
 * Tests for the NervousSystemPanel component.
 *
 * NervousSystemPanel fetches /api/health, /api/sessions and renders
 * event bus stats, state machine stats, VSM layer subscriptions,
 * recent state changes, and active sessions.
 */

import React from "react";
import { render, screen, waitFor } from "@testing-library/react";
import { NervousSystemPanel } from "../NervousSystemPanel";

const mockFetch = jest.fn();
beforeEach(() => {
  mockFetch.mockReset();
  window.WebSocket = jest.fn().mockImplementation(() => ({
    onmessage: null,
    onerror: null,
    close: () => {},
  })) as unknown as typeof WebSocket;
});
global.fetch = mockFetch;

function mockHealthData(overrides: Record<string, any> = {}) {
  return {
    ok: true,
    protocol_version: "1.0",
    llm_url: "http://localhost:8090",
    llm_model: "Qwen3.6-35B-A3B",
    active_sessions: 3,
    event_bus: {
      published: 1234,
      dropped: 2,
      subscriptions: 5,
      event_types_subscribed: ["tool.*", "assistant.*", "session.*", "resource.*", "loop_safety.*"],
    },
    state_machine: {
      total_sessions: 10,
      state_distribution: { ready: 5, running: 3, idle: 2 },
      transitions_completed: 45,
      invalid_attempts: 0,
    },
    ...overrides,
  };
}

function mockSessions(count: number) {
  return Array.from({ length: count }, (_, i) => ({
    id: `sess-${i}`,
    title: `Session ${i}`,
    status: i === 0 ? "running" : i === 1 ? "failed" : "ready",
    model: "Qwen3.6-35B-A3B",
    updated_at: Date.now(),
  }));
}

describe("NervousSystemPanel", () => {
  it("shows header", async () => {
    mockFetch.mockImplementation((url: string) => {
      if (url === "/api/health") return Promise.resolve({ ok: true, json: () => Promise.resolve(mockHealthData()) });
      if (url === "/api/sessions") return Promise.resolve({ json: () => Promise.resolve(mockSessions(2)) });
      return Promise.resolve({ json: () => Promise.resolve({}) });
    });
    render(<NervousSystemPanel />);
    await waitFor(() => expect(screen.getByText("Nervous System")).toBeInTheDocument());
  });

  it("shows live status when no error", async () => {
    mockFetch.mockImplementation((url: string) => {
      if (url === "/api/health") return Promise.resolve({ ok: true, json: () => Promise.resolve(mockHealthData()) });
      return Promise.resolve({ json: () => Promise.resolve(mockSessions(0)) });
    });
    render(<NervousSystemPanel />);
    await waitFor(() => expect(screen.getByText("● Live")).toBeInTheDocument());
  });

  it("shows error status when fetch fails", async () => {
    mockFetch.mockImplementation((url: string) => {
      if (url === "/api/health") return Promise.resolve({ ok: false, json: () => Promise.resolve({}) });
      return Promise.resolve({ json: () => Promise.resolve({}) });
    });
    render(<NervousSystemPanel />);
    await waitFor(() => expect(screen.getByText(/⚠/)).toBeInTheDocument());
  });

  it("shows event bus stats", async () => {
    mockFetch.mockImplementation((url: string) => {
      if (url === "/api/health") return Promise.resolve({ ok: true, json: () => Promise.resolve(mockHealthData()) });
      return Promise.resolve({ json: () => Promise.resolve(mockSessions(0)) });
    });
    render(<NervousSystemPanel />);
    await waitFor(() => {
      const all = document.body.textContent;
      expect(all).toContain("Event Bus");
      expect(all).toContain("Events Published");
      expect(all).toContain("Subscriptions");
      expect(all).toContain("Dropped");
    });
  });

  it("displays event bus numbers", async () => {
    mockFetch.mockImplementation((url: string) => {
      if (url === "/api/health") return Promise.resolve({ ok: true, json: () => Promise.resolve(mockHealthData()) });
      return Promise.resolve({ json: () => Promise.resolve(mockSessions(0)) });
    });
    render(<NervousSystemPanel />);
    await waitFor(() => {
      const all = document.body.textContent;
      expect(all).toContain("1,234");
    });
  });

  it("shows state machine stats", async () => {
    mockFetch.mockImplementation((url: string) => {
      if (url === "/api/health") return Promise.resolve({ ok: true, json: () => Promise.resolve(mockHealthData()) });
      return Promise.resolve({ json: () => Promise.resolve(mockSessions(0)) });
    });
    render(<NervousSystemPanel />);
    await waitFor(() => {
      const all = document.body.textContent;
      expect(all).toContain("State Machine");
      expect(all).toContain("Active Sessions");
      expect(all).toContain("Transitions");
      expect(all).toContain("Invalid Attempts");
    });
  });

  it("shows state distribution badges", async () => {
    mockFetch.mockImplementation((url: string) => {
      if (url === "/api/health") return Promise.resolve({ ok: true, json: () => Promise.resolve(mockHealthData()) });
      return Promise.resolve({ json: () => Promise.resolve(mockSessions(0)) });
    });
    render(<NervousSystemPanel />);
    await waitFor(() => {
      const all = document.body.textContent;
      expect(all).toContain("State Distribution");
    });
  });

  it("shows VSM layer subscriptions", async () => {
    mockFetch.mockImplementation((url: string) => {
      if (url === "/api/health") return Promise.resolve({ ok: true, json: () => Promise.resolve(mockHealthData()) });
      return Promise.resolve({ json: () => Promise.resolve(mockSessions(0)) });
    });
    render(<NervousSystemPanel />);
    await waitFor(() => expect(screen.getByText("VSM Layer Subscriptions")).toBeInTheDocument());
    expect(screen.getByText("S1")).toBeInTheDocument();
    expect(screen.getByText("Coding Agent")).toBeInTheDocument();
    expect(screen.getByText("S2")).toBeInTheDocument();
    expect(screen.getByText("Event Stream")).toBeInTheDocument();
    expect(screen.getByText("S3")).toBeInTheDocument();
    expect(screen.getByText("Manager")).toBeInTheDocument();
    expect(screen.getByText("S4")).toBeInTheDocument();
    expect(screen.getByText("Planner")).toBeInTheDocument();
    expect(screen.getByText("S5")).toBeInTheDocument();
    expect(screen.getByText("Axioms")).toBeInTheDocument();
  });

  it("shows no state changes message when empty", async () => {
    mockFetch.mockImplementation((url: string) => {
      if (url === "/api/health") return Promise.resolve({ ok: true, json: () => Promise.resolve(mockHealthData()) });
      return Promise.resolve({ json: () => Promise.resolve(mockSessions(0)) });
    });
    render(<NervousSystemPanel />);
    await waitFor(() => expect(screen.getByText("Recent State Changes")).toBeInTheDocument());
    await waitFor(() => {
      const all = document.body.textContent;
      expect(all).toContain("No state changes yet");
    });
  });

  it("shows active sessions count", async () => {
    mockFetch.mockImplementation((url: string) => {
      if (url === "/api/health") return Promise.resolve({ ok: true, json: () => Promise.resolve(mockHealthData()) });
      if (url === "/api/sessions") return Promise.resolve({ ok: true, json: () => Promise.resolve(mockSessions(3)) });
      return Promise.resolve({ json: () => Promise.resolve({}) });
    });
    render(<NervousSystemPanel />);
    await waitFor(() => {
      const all = document.body.textContent;
      expect(all).toContain("Active Sessions (3)");
    });
  });

  it("shows session status badges", async () => {
    mockFetch.mockImplementation((url: string) => {
      if (url === "/api/health") return Promise.resolve({ ok: true, json: () => Promise.resolve(mockHealthData()) });
      if (url === "/api/sessions") return Promise.resolve({ ok: true, json: () => Promise.resolve(mockSessions(3)) });
      return Promise.resolve({ json: () => Promise.resolve({}) });
    });
    render(<NervousSystemPanel />);
    await waitFor(() => {
      const all = document.body.textContent;
      expect(all).toContain("ACTIVE");
      expect(all).toContain("ERR");
      expect(all).toContain("IDLE");
    });
  });

  it("polls data on interval", async () => {
    mockFetch.mockImplementation((url: string) => {
      if (url === "/api/health") return Promise.resolve({ ok: true, json: () => Promise.resolve(mockHealthData()) });
      if (url === "/api/sessions") return Promise.resolve({ ok: true, json: () => Promise.resolve(mockSessions(0)) });
      return Promise.resolve({ json: () => Promise.resolve({}) });
    });
    render(<NervousSystemPanel />);
    await waitFor(() => expect(screen.getByText("Nervous System")).toBeInTheDocument());
    // Wait for the 2s polling interval to trigger a second fetch
    await new Promise((r) => setTimeout(r, 2500));
    const healthCalls = mockFetch.mock.calls.filter((c: any[]) => c[0] === "/api/health");
    expect(healthCalls.length).toBeGreaterThan(1);
  });
});
