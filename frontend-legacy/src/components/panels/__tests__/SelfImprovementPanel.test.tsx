/**
 * Tests for SelfImprovementPanel — metrics, experiences, report tabs.
 */

import React from "react";
import { render, screen, waitFor, fireEvent } from "@testing-library/react";
import { SelfImprovementPanel } from "../SelfImprovementPanel";

const mockFetch = jest.fn();
global.fetch = mockFetch;

describe("SelfImprovementPanel", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    mockFetch.mockReset();
  });

  function mockImprovementData() {
    return {
      metrics: {
        total_tasks: 42, total_improvements: 15, learning_velocity: 0.357,
        model_rankings: [
          { model: "qwen3-35b", task_type: "coding", tasks: 20, successes: 18, avg_quality: 0.9 },
          { model: "granite-8b", task_type: "coding", tasks: 10, successes: 7, avg_quality: 0.7 },
        ],
        best_model_for_coding: "qwen3-35b",
      },
      experiences: [
        {
          session_id: "sess-001", task: "Fix auth bug", model_used: "qwen3-35b",
          success: true, tests_passed: 5, tests_total: 5, wall_time_seconds: 120,
          evaluation_score: 0.95, lessons: ["Always check edge cases"],
          what_worked: ["Read the code first"], what_failed: ["Skipping tests"],
          created_skills: ["auth-fix-pattern"], created_at: "2024-01-01",
        },
        {
          session_id: "sess-002", task: "Add feature X", model_used: "granite-8b",
          success: false, tests_passed: 2, tests_total: 5, wall_time_seconds: 300,
          evaluation_score: 0.4, lessons: ["Need more context"],
          what_worked: [], what_failed: ["Insufficient requirements"],
          created_skills: [], created_at: "2024-01-02",
        },
      ],
      report: "Self-improvement report content here.",
    };
  }

  function setupMock(data: ReturnType<typeof mockImprovementData>) {
    mockFetch.mockImplementation((url: string) => {
      if (url.includes("/api/self_improvement/metrics")) return Promise.resolve({ ok: true, json: () => Promise.resolve(data.metrics) });
      if (url.includes("/api/self_improvement/experiences")) return Promise.resolve({ ok: true, json: () => Promise.resolve({ experiences: data.experiences }) });
      if (url.includes("/api/self_improvement/report")) return Promise.resolve({ ok: true, json: () => Promise.resolve({ report: data.report }) });
      return Promise.resolve({ ok: false });
    });
  }

  it("renders loading state", () => {
    mockFetch.mockImplementation(() => new Promise(() => {}));
    render(<SelfImprovementPanel />);
    expect(screen.getByText("Loading self-improvement data...")).toBeInTheDocument();
  });

  it("renders metrics tab with overview stats", async () => {
    const data = mockImprovementData();
    setupMock(data);
    render(<SelfImprovementPanel />);
    await waitFor(() => expect(screen.getByText("Total Tasks")).toBeInTheDocument());
    await waitFor(() => expect(screen.getByText("42")).toBeInTheDocument());
    await waitFor(() => expect(screen.getByText("Improvements")).toBeInTheDocument());
    await waitFor(() => expect(screen.getByText("15")).toBeInTheDocument());
  });

  it("renders learning velocity", async () => {
    const data = mockImprovementData();
    setupMock(data);
    render(<SelfImprovementPanel />);
    await waitFor(() => expect(screen.getByText("Velocity")).toBeInTheDocument());
  });

  it("renders best model for coding", async () => {
    const data = mockImprovementData();
    setupMock(data);
    render(<SelfImprovementPanel />);
    await waitFor(() => expect(screen.getByText("Best Model for Coding")).toBeInTheDocument());
    await waitFor(() => expect(screen.getByText("qwen3-35b")).toBeInTheDocument());
  });

  it("renders model rankings", async () => {
    const data = mockImprovementData();
    setupMock(data);
    render(<SelfImprovementPanel />);
    await waitFor(() => expect(screen.getByText("Model Performance Rankings")).toBeInTheDocument());
    await waitFor(() => expect(screen.getByText("qwen3-35b")).toBeInTheDocument());
    await waitFor(() => expect(screen.getByText("granite-8b")).toBeInTheDocument());
  });

  it("renders experiences tab", async () => {
    const data = mockImprovementData();
    setupMock(data);
    render(<SelfImprovementPanel />);
    const expTab = screen.getByText(/Experiences/);
    fireEvent.click(expTab);
    await waitFor(() => expect(screen.getByText("Fix auth bug")).toBeInTheDocument());
    await waitFor(() => expect(screen.getByText("Add feature X")).toBeInTheDocument());
  });

  it("shows success/failure indicators on experiences", async () => {
    const data = mockImprovementData();
    setupMock(data);
    render(<SelfImprovementPanel />);
    const expTab = screen.getByText(/Experiences/);
    fireEvent.click(expTab);
    await waitFor(() => expect(screen.getByText("5/5")).toBeInTheDocument());
    await waitFor(() => expect(screen.getByText("2/5")).toBeInTheDocument());
  });

  it("shows lessons on experience cards", async () => {
    const data = mockImprovementData();
    setupMock(data);
    render(<SelfImprovementPanel />);
    const expTab = screen.getByText(/Experiences/);
    fireEvent.click(expTab);
    await waitFor(() => expect(screen.getByText("Lessons:")).toBeInTheDocument());
    await waitFor(() => expect(screen.getByText("Always check edge cases")).toBeInTheDocument());
  });

  it("shows skills created count", async () => {
    const data = mockImprovementData();
    setupMock(data);
    render(<SelfImprovementPanel />);
    const expTab = screen.getByText(/Experiences/);
    fireEvent.click(expTab);
    await waitFor(() => expect(screen.getByText("+1 skill(s) created")).toBeInTheDocument());
  });

  it("shows report tab content", async () => {
    const data = mockImprovementData();
    setupMock(data);
    render(<SelfImprovementPanel />);
    const reportTab = screen.getByText(/Report/);
    fireEvent.click(reportTab);
    await waitFor(() => expect(screen.getByText("Self-improvement report content here.")).toBeInTheDocument());
  });

  it("shows no experiences message when empty", async () => {
    const data = mockImprovementData();
    data.experiences = [];
    setupMock(data);
    render(<SelfImprovementPanel />);
    const expTab = screen.getByText(/Experiences/);
    fireEvent.click(expTab);
    await waitFor(() => expect(screen.getByText("No experience records yet")).toBeInTheDocument());
  });

  it("shows no report message when empty", async () => {
    const data = mockImprovementData();
    data.report = "";
    setupMock(data);
    render(<SelfImprovementPanel />);
    const reportTab = screen.getByText(/Report/);
    fireEvent.click(reportTab);
    await waitFor(() => expect(screen.getByText("No report available")).toBeInTheDocument());
  });

  it("handles fetch error gracefully", async () => {
    mockFetch.mockRejectedValueOnce(new Error("Network error"));
    const consoleSpy = jest.spyOn(console, "error").mockImplementation(() => {});
    render(<SelfImprovementPanel />);
    await waitFor(() => expect(screen.getByText("Network error")).toBeInTheDocument());
    consoleSpy.mockRestore();
  });

  it("handles null metrics", async () => {
    mockFetch.mockImplementation((url: string) => {
      if (url.includes("/api/self_improvement/metrics")) return Promise.resolve({ ok: true, json: () => Promise.resolve(null) });
      if (url.includes("/api/self_improvement/experiences")) return Promise.resolve({ ok: true, json: () => Promise.resolve({ experiences: [] }) });
      if (url.includes("/api/self_improvement/report")) return Promise.resolve({ ok: true, json: () => Promise.resolve({ report: "" }) });
      return Promise.resolve({ ok: false });
    });
    render(<SelfImprovementPanel />);
    await waitFor(() => expect(screen.getByText("Self-improvement not initialized")).toBeInTheDocument());
  });

  it("renders model ranking with quality score", async () => {
    const data = mockImprovementData();
    setupMock(data);
    render(<SelfImprovementPanel />);
    await waitFor(() => expect(screen.getByText("0.900")).toBeInTheDocument());
  });

  it("renders experience wall time", async () => {
    const data = mockImprovementData();
    setupMock(data);
    render(<SelfImprovementPanel />);
    const expTab = screen.getByText(/Experiences/);
    fireEvent.click(expTab);
    await waitFor(() => expect(screen.getByText("Time:")).toBeInTheDocument());
  });

  it("renders experience model used", async () => {
    const data = mockImprovementData();
    setupMock(data);
    render(<SelfImprovementPanel />);
    const expTab = screen.getByText(/Experiences/);
    fireEvent.click(expTab);
    await waitFor(() => expect(screen.getByText("Model:")).toBeInTheDocument());
  });

  it("renders evaluation score on experience cards", async () => {
    const data = mockImprovementData();
    setupMock(data);
    render(<SelfImprovementPanel />);
    const expTab = screen.getByText(/Experiences/);
    fireEvent.click(expTab);
    await waitFor(() => expect(screen.getByText("Score: 0.95")).toBeInTheDocument());
  });
});
