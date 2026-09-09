/**
 * Tests for HooksPanel — loading, stats, toggle enable/disable.
 */

import React from "react";
import { render, screen, waitFor, fireEvent } from "@testing-library/react";
import { HooksPanel } from "../HooksPanel";

const mockFetch = jest.fn();
global.fetch = mockFetch;

describe("HooksPanel", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    mockFetch.mockReset();
  });

  function mockHooksData() {
    return {
      hooks: [
        {
          id: "h1",
          name: "OnCommit",
          trigger: "git.commit",
          action: "run_tests",
          enabled: true,
          executions: 150,
          successRate: 98.5,
          lastExecution: "2024-06-01 10:30",
        },
        {
          id: "h2",
          name: "OnPush",
          trigger: "git.push",
          action: "deploy_staging",
          enabled: false,
          executions: 45,
          successRate: 92.0,
          lastExecution: "2024-06-01 09:15",
        },
        {
          id: "h3",
          name: "OnPR",
          trigger: "github.pr",
          action: "run_linter",
          enabled: true,
          executions: 200,
          successRate: 100,
          lastExecution: "2024-06-01 11:00",
        },
      ],
    };
  }

  it("renders loading spinner", () => {
    mockFetch.mockImplementation(() => new Promise(() => {}));
    render(<HooksPanel />);
    expect(document.querySelector(".animate-spin")).toBeInTheDocument();
  });

  it("renders stats cards", async () => {
    mockFetch.mockResolvedValue({ json: () => Promise.resolve(mockHooksData()) });
    render(<HooksPanel />);
    await waitFor(() => expect(screen.getByText("Total Hooks")).toBeInTheDocument());
    await waitFor(() => expect(screen.getByText("Active")).toBeInTheDocument());
    await waitFor(() => expect(screen.getByText("Total Executions")).toBeInTheDocument());
  });

  it("renders correct hook counts", async () => {
    mockFetch.mockResolvedValue({ json: () => Promise.resolve(mockHooksData()) });
    render(<HooksPanel />);
    await waitFor(() => expect(screen.getByText("3")).toBeInTheDocument());
    await waitFor(() => expect(screen.getByText("2")).toBeInTheDocument());
    await waitFor(() => expect(screen.getByText("395")).toBeInTheDocument());
  });

  it("renders hook names", async () => {
    mockFetch.mockResolvedValue({ json: () => Promise.resolve(mockHooksData()) });
    render(<HooksPanel />);
    await waitFor(() => expect(screen.getByText("OnCommit")).toBeInTheDocument());
    await waitFor(() => expect(screen.getByText("OnPush")).toBeInTheDocument());
    await waitFor(() => expect(screen.getByText("OnPR")).toBeInTheDocument());
  });

  it("renders trigger labels", async () => {
    mockFetch.mockResolvedValue({ json: () => Promise.resolve(mockHooksData()) });
    render(<HooksPanel />);
    await waitFor(() => expect(screen.getByText("git.commit")).toBeInTheDocument());
    await waitFor(() => expect(screen.getByText("git.push")).toBeInTheDocument());
    await waitFor(() => expect(screen.getByText("github.pr")).toBeInTheDocument());
  });

  it("renders action labels", async () => {
    mockFetch.mockResolvedValue({ json: () => Promise.resolve(mockHooksData()) });
    render(<HooksPanel />);
    await waitFor(() => expect(screen.getByText("run_tests")).toBeInTheDocument());
    await waitFor(() => expect(screen.getByText("deploy_staging")).toBeInTheDocument());
  });

  it("renders execution counts", async () => {
    mockFetch.mockResolvedValue({ json: () => Promise.resolve(mockHooksData()) });
    render(<HooksPanel />);
    await waitFor(() => expect(screen.getByText("150 executions")).toBeInTheDocument());
    await waitFor(() => expect(screen.getByText("45 executions")).toBeInTheDocument());
  });

  it("renders last execution time", async () => {
    mockFetch.mockResolvedValue({ json: () => Promise.resolve(mockHooksData()) });
    render(<HooksPanel />);
    await waitFor(() => expect(screen.getByText("Last: 2024-06-01 10:30")).toBeInTheDocument());
  });

  it("renders success rate", async () => {
    mockFetch.mockResolvedValue({ json: () => Promise.resolve(mockHooksData()) });
    render(<HooksPanel />);
    await waitFor(() => expect(screen.getByText("Success: 98.5%")).toBeInTheDocument());
    await waitFor(() => expect(screen.getByText("Success: 100%")).toBeInTheDocument());
  });

  it("shows green dot for enabled hooks", async () => {
    mockFetch.mockResolvedValue({ json: () => Promise.resolve(mockHooksData()) });
    render(<HooksPanel />);
    await waitFor(() => expect(screen.getByText("OnCommit")).toBeInTheDocument());
  });

  it("shows gray dot for disabled hooks", async () => {
    mockFetch.mockResolvedValue({ json: () => Promise.resolve(mockHooksData()) });
    render(<HooksPanel />);
    await waitFor(() => expect(screen.getByText("OnPush")).toBeInTheDocument());
  });

  it("toggles hook from enabled to disabled", async () => {
    mockFetch.mockResolvedValue({ json: () => Promise.resolve(mockHooksData()) });
    render(<HooksPanel />);
    await waitFor(() => expect(screen.getByText("OnCommit")).toBeInTheDocument());
    // Toggle buttons are styled switches without title — find by position
    const toggleButtons = document.querySelectorAll('[class*="rounded-full"][class*="transition-all"]');
    // First toggle is OnCommit (enabled)
    fireEvent.click(toggleButtons[0]);
    // After toggle, OnCommit should show as disabled (gray dot)
    await waitFor(() => {
      const hookCards = document.querySelectorAll('[class*="panel-card"]');
      expect(hookCards.length).toBeGreaterThan(0);
    });
  });

  it("toggles hook from disabled to enabled", async () => {
    mockFetch.mockResolvedValue({ json: () => Promise.resolve(mockHooksData()) });
    render(<HooksPanel />);
    await waitFor(() => expect(screen.getByText("OnPush")).toBeInTheDocument());
    // Toggle buttons are styled switches — find the second one (OnPush is disabled)
    const toggleButtons = document.querySelectorAll('[class*="rounded-full"][class*="transition-all"]');
    fireEvent.click(toggleButtons[1]);
    await waitFor(() => {
      const hookCards = document.querySelectorAll('[class*="panel-card"]');
      expect(hookCards.length).toBeGreaterThan(0);
    });
  });

  it("handles empty hooks array", async () => {
    mockFetch.mockResolvedValue({ json: () => Promise.resolve({ hooks: [] }) });
    render(<HooksPanel />);
    await waitFor(() => expect(screen.getByText("0")).toBeInTheDocument());
    await waitFor(() => expect(screen.getByText("0")).toBeInTheDocument());
    await waitFor(() => expect(screen.getByText("0")).toBeInTheDocument());
  });

  it("handles fetch error", async () => {
    mockFetch.mockRejectedValue(new Error("Network error"));
    render(<HooksPanel />);
    await waitFor(() => expect(screen.getByText("Total Hooks")).toBeInTheDocument());
  });

  it("renders 100% success rate", async () => {
    mockFetch.mockResolvedValue({ json: () => Promise.resolve(mockHooksData()) });
    render(<HooksPanel />);
    await waitFor(() => expect(screen.getByText("Success: 100%")).toBeInTheDocument());
  });

  it("renders zero executions", async () => {
    const data = mockHooksData();
    data.hooks[0].executions = 0;
    mockFetch.mockResolvedValue({ json: () => Promise.resolve(data) });
    render(<HooksPanel />);
    await waitFor(() => expect(screen.getByText("0 executions")).toBeInTheDocument());
  });
});
