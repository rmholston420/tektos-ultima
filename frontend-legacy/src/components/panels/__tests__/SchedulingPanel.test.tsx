/**
 * Tests for SchedulingPanel — loading, task list, create form, pause/delete.
 */

import React from "react";
import { render, screen, waitFor, fireEvent } from "@testing-library/react";
import { SchedulingPanel } from "../SchedulingPanel";

const mockFetch = jest.fn();
global.fetch = mockFetch;

describe("SchedulingPanel", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    mockFetch.mockReset();
  });

  function mockTaskData() {
    return [
      {
        id: "task-1",
        title: "Daily Backup",
        message: "Run nightly backup",
        type: "recurring",
        cron: "0 9 * * *",
        timezone: "UTC",
        status: "active",
        nextRun: new Date(Date.now() + 86400000).toISOString(),
        runsCompleted: 12,
        createdAt: new Date().toISOString(),
      },
      {
        id: "task-2",
        title: "One-time Cleanup",
        message: "Clean temp files",
        type: "once",
        timezone: "UTC",
        status: "pending",
        nextRun: new Date(Date.now() + 300000).toISOString(),
        runsCompleted: 0,
        createdAt: new Date().toISOString(),
      },
    ];
  }

  it("renders loading spinner", () => {
    mockFetch.mockImplementation(() => new Promise(() => {}));
    render(<SchedulingPanel />);
    expect(screen.getByText("Schedule Manager")).toBeInTheDocument();
  });

  it("renders header with title and create button", async () => {
    mockFetch.mockResolvedValue({ json: () => Promise.resolve([]) });
    render(<SchedulingPanel />);
    await waitFor(() => expect(screen.getByText("Schedule Manager")).toBeInTheDocument());
    expect(screen.getByText("+ New Schedule")).toBeInTheDocument();
  });

  it("renders task list with tasks", async () => {
    mockFetch.mockResolvedValue({ json: () => Promise.resolve(mockTaskData()) });
    render(<SchedulingPanel />);
    await waitFor(() => expect(screen.getByText("Daily Backup")).toBeInTheDocument());
    await waitFor(() => expect(screen.getByText("One-time Cleanup")).toBeInTheDocument());
  });

  it("renders task status badges", async () => {
    mockFetch.mockResolvedValue({ json: () => Promise.resolve(mockTaskData()) });
    render(<SchedulingPanel />);
    await waitFor(() => expect(screen.getByText("active")).toBeInTheDocument());
    await waitFor(() => expect(screen.getByText("pending")).toBeInTheDocument());
  });

  it("renders task type labels", async () => {
    mockFetch.mockResolvedValue({ json: () => Promise.resolve(mockTaskData()) });
    render(<SchedulingPanel />);
    await waitFor(() => expect(screen.getByText("One-time")).toBeInTheDocument());
  });

  it("renders cron expression for recurring tasks", async () => {
    mockFetch.mockResolvedValue({ json: () => Promise.resolve(mockTaskData()) });
    render(<SchedulingPanel />);
    await waitFor(() => expect(screen.getByText("0 9 * * *")).toBeInTheDocument());
  });

  it("renders run count for tasks", async () => {
    mockFetch.mockResolvedValue({ json: () => Promise.resolve(mockTaskData()) });
    render(<SchedulingPanel />);
    await waitFor(() => expect(screen.getByText("12 runs")).toBeInTheDocument());
  });

  it("renders pause button for each task", async () => {
    mockFetch.mockResolvedValue({ json: () => Promise.resolve(mockTaskData()) });
    render(<SchedulingPanel />);
    await waitFor(() => expect(screen.getByText("Daily Backup")).toBeInTheDocument());
    const pauseButtons = screen.getAllByTitle("Pause");
    expect(pauseButtons).toHaveLength(2);
  });

  it("renders delete button for each task", async () => {
    mockFetch.mockResolvedValue({ json: () => Promise.resolve(mockTaskData()) });
    render(<SchedulingPanel />);
    await waitFor(() => expect(screen.getByText("Daily Backup")).toBeInTheDocument());
    const deleteButtons = screen.getAllByTitle("Delete");
    expect(deleteButtons).toHaveLength(2);
  });

  it("shows empty state when no tasks", async () => {
    mockFetch.mockResolvedValue({ json: () => Promise.resolve([]) });
    render(<SchedulingPanel />);
    await waitFor(() => expect(screen.getByText("No scheduled tasks")).toBeInTheDocument());
    await waitFor(() => expect(screen.getByText("Create a schedule to automate your workflow")).toBeInTheDocument());
  });

  it("opens create form when + New Schedule clicked", async () => {
    mockFetch.mockResolvedValue({ json: () => Promise.resolve([]) });
    render(<SchedulingPanel />);
    await waitFor(() => expect(screen.getByText("+ New Schedule")).toBeInTheDocument());
    fireEvent.click(screen.getByText("+ New Schedule"));
    expect(screen.getByText("Create New Schedule")).toBeInTheDocument();
    expect(screen.getByPlaceholderText("e.g., Daily Backup")).toBeInTheDocument();
    expect(screen.getByPlaceholderText("What should the AI do?")).toBeInTheDocument();
  });

  it("shows one-time presets in create form", async () => {
    mockFetch.mockResolvedValue({ json: () => Promise.resolve([]) });
    render(<SchedulingPanel />);
    await waitFor(() => expect(screen.getByText("+ New Schedule")).toBeInTheDocument());
    fireEvent.click(screen.getByText("+ New Schedule"));
    expect(screen.getByText("In 5 minutes")).toBeInTheDocument();
    expect(screen.getByText("In 15 minutes")).toBeInTheDocument();
    expect(screen.getByText("In 1 hour")).toBeInTheDocument();
    expect(screen.getByText("Tomorrow 9:00 AM")).toBeInTheDocument();
  });

  it("shows recurring presets when recurring selected", async () => {
    mockFetch.mockResolvedValue({ json: () => Promise.resolve([]) });
    render(<SchedulingPanel />);
    await waitFor(() => expect(screen.getByText("+ New Schedule")).toBeInTheDocument());
    fireEvent.click(screen.getByText("+ New Schedule"));
    fireEvent.click(screen.getByText("Recurring"));
    expect(screen.getByText("Every hour")).toBeInTheDocument();
    expect(screen.getByText("Daily at 9 AM")).toBeInTheDocument();
    expect(screen.getByText("Weekdays 9-5")).toBeInTheDocument();
  });

  it("toggles between one-time and recurring schedule types", async () => {
    mockFetch.mockResolvedValue({ json: () => Promise.resolve([]) });
    render(<SchedulingPanel />);
    await waitFor(() => expect(screen.getByText("+ New Schedule")).toBeInTheDocument());
    fireEvent.click(screen.getByText("+ New Schedule"));
    expect(screen.getByText("In 5 minutes")).toBeInTheDocument();
    expect(screen.queryByText("Every hour")).not.toBeInTheDocument();

    fireEvent.click(screen.getByText("Recurring"));
    expect(screen.queryByText("In 5 minutes")).not.toBeInTheDocument();
    expect(screen.getByText("Every hour")).toBeInTheDocument();
  });

  it("creates a task and shows success notification", async () => {
    mockFetch.mockResolvedValue({ json: () => Promise.resolve([]) });
    render(<SchedulingPanel />);
    await waitFor(() => expect(screen.getByText("+ New Schedule")).toBeInTheDocument());
    fireEvent.click(screen.getByText("+ New Schedule"));
    fireEvent.click(screen.getByText("Create Schedule"));
    await waitFor(() => expect(screen.getByText("✓ Schedule created successfully")).toBeInTheDocument());
  });

  it("cancels create form", async () => {
    mockFetch.mockResolvedValue({ json: () => Promise.resolve([]) });
    render(<SchedulingPanel />);
    await waitFor(() => expect(screen.getByText("+ New Schedule")).toBeInTheDocument());
    fireEvent.click(screen.getByText("+ New Schedule"));
    fireEvent.click(screen.getByText("Cancel"));
    expect(screen.queryByText("Create New Schedule")).not.toBeInTheDocument();
  });

  it("deletes a task", async () => {
    mockFetch.mockResolvedValue({ json: () => Promise.resolve(mockTaskData()) });
    render(<SchedulingPanel />);
    await waitFor(() => expect(screen.getByText("Daily Backup")).toBeInTheDocument());
    const deleteButtons = screen.getAllByTitle("Delete");
    fireEvent.click(deleteButtons[0]);
    await waitFor(() => expect(screen.queryByText("Daily Backup")).not.toBeInTheDocument());
    await waitFor(() => expect(screen.getByText("One-time Cleanup")).toBeInTheDocument());
  });

  it("toggles pause state on task", async () => {
    mockFetch.mockResolvedValue({ json: () => Promise.resolve(mockTaskData()) });
    render(<SchedulingPanel />);
    await waitFor(() => expect(screen.getByText("active")).toBeInTheDocument());
    const pauseButtons = screen.getAllByTitle("Pause");
    fireEvent.click(pauseButtons[0]);
    await waitFor(() => expect(screen.getByText("paused")).toBeInTheDocument());
    fireEvent.click(pauseButtons[0]);
    await waitFor(() => expect(screen.getByText("active")).toBeInTheDocument());
  });

  it("renders overdue label for past nextRun", async () => {
    const data = mockTaskData();
    data[0].nextRun = new Date(Date.now() - 3600000).toISOString();
    mockFetch.mockResolvedValue({ json: () => Promise.resolve(data) });
    render(<SchedulingPanel />);
    await waitFor(() => expect(screen.getByText("Overdue")).toBeInTheDocument());
  });

  it("renders relative time for near-future nextRun", async () => {
    const data = mockTaskData();
    data[0].nextRun = new Date(Date.now() + 3600000).toISOString();
    mockFetch.mockResolvedValue({ json: () => Promise.resolve(data) });
    render(<SchedulingPanel />);
    await waitFor(() => expect(screen.getByText("In 1h")).toBeInTheDocument());
  });
});
