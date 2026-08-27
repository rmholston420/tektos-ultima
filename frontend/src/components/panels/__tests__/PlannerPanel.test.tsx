/**
 * Tests for PlannerPanel — loading, tab switching, prompt input, error handling.
 */

import React from "react";
import { render, screen, waitFor, fireEvent } from "@testing-library/react";
import { PlannerPanel } from "../PlannerPanel";

const mockFetch = jest.fn();
global.fetch = mockFetch;

describe("PlannerPanel", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    mockFetch.mockReset();
  });

  function mockPlannerResponse() {
    return {
      templates: [
        { name: "microservice", description: "Independent services", pros: ["Scalable", "Independent deploy"], cons: ["Complex networking", "Data consistency"], use_cases: ["Large apps"], recommended_for: "Enterprise" },
        { name: "monolith", description: "Single application", pros: ["Simple", "Easy deploy"], cons: ["Hard to scale"], use_cases: ["Small apps"], recommended_for: "Startups" },
      ],
      language_games: [
        { name: "web-app", description: "Web Application" },
        { name: "api-service", description: "API Service" },
      ],
    };
  }

  function mockPlannerOutput() {
    return {
      spec: {
        id: "spec-001", version: "1.0", created_at: "2024-01-01",
        description: "Build a REST API",
        requirements: ["REST endpoints", "Auth", "DB integration"],
        constraints: ["TypeScript", "Node.js"],
        tech_stack: ["Express", "PostgreSQL"],
        test_strategy: "Unit + Integration",
        architecture: { selected: "microservice", reason: "Scalability", is_user_choice: false },
        phases: [
          { id: "p1", description: "Setup", deliverables: ["Project init"], acceptance_criteria: ["Build passes"], estimated_effort: "1 day" },
          { id: "p2", description: "API", deliverables: ["Endpoints"], acceptance_criteria: ["All endpoints work"], estimated_effort: "3 days" },
        ],
        context_budget_warning: null,
        notes: [],
      },
      language_game_detected: "web-app",
      ambiguities_found: [{ term: "API", possible_meanings: ["REST", "GraphQL"], criticality: "medium" }],
      clarifying_questions_asked: [],
      templates_presented: ["microservice", "monolith"],
      context_budget_used: 5000,
      context_budget_total: 10000,
    };
  }

  function setupMock(data: ReturnType<typeof mockPlannerResponse>, output?: ReturnType<typeof mockPlannerOutput>) {
    mockFetch.mockImplementation((url: string, opts?: any) => {
      if (url.includes("/api/planner/templates")) return Promise.resolve({ ok: true, json: () => Promise.resolve(data) });
      if (url.includes("/api/planner/language-games")) return Promise.resolve({ ok: true, json: () => Promise.resolve(data) });
      if (url.includes("/api/planner/plan") && output) return Promise.resolve({ ok: true, json: () => Promise.resolve(output) });
      return Promise.resolve({ ok: false });
    });
  }

  it("renders loading state", () => {
    mockFetch.mockImplementation(() => new Promise(() => {}));
    render(<PlannerPanel />);
    expect(screen.getByText("Loading planner data...")).toBeInTheDocument();
  });

  it("renders templates tab with data", async () => {
    const data = mockPlannerResponse();
    setupMock(data);
    render(<PlannerPanel />);
    await waitFor(() => expect(screen.getByText("Architecture Templates")).toBeInTheDocument());
    await waitFor(() => expect(screen.getByText("microservice")).toBeInTheDocument());
    await waitFor(() => expect(screen.getByText("monolith")).toBeInTheDocument());
  });

  it("renders language games section", async () => {
    const data = mockPlannerResponse();
    setupMock(data);
    render(<PlannerPanel />);
    await waitFor(() => expect(screen.getByText("Language Games (Domains)")).toBeInTheDocument());
    await waitFor(() => expect(screen.getByText("Web Application")).toBeInTheDocument());
  });

  it("renders plan tab with textarea and quick prompts", async () => {
    const data = mockPlannerResponse();
    setupMock(data);
    render(<PlannerPanel />);
    // Tab buttons render capitalized: "Templates", "Plan", "Output"
    const planTab = screen.getByText("Plan");
    fireEvent.click(planTab);
    await waitFor(() => expect(screen.getByPlaceholderText(/Describe what you want to build/i)).toBeInTheDocument());
    await waitFor(() => expect(screen.getByText("Run Planner")).toBeInTheDocument());
  });

  it("renders quick prompt buttons", async () => {
    const data = mockPlannerResponse();
    setupMock(data);
    render(<PlannerPanel />);
    const planTab = screen.getByText("Plan");
    fireEvent.click(planTab);
    await waitFor(() => expect(screen.getByText("Build a REST API")).toBeInTheDocument());
  });

  it("runs planner and shows output tab", async () => {
    const data = mockPlannerResponse();
    const output = mockPlannerOutput();
    setupMock(data, output);
    render(<PlannerPanel />);
    const planTab = screen.getByText("Plan");
    fireEvent.click(planTab);
    const textarea = screen.getByPlaceholderText(/Describe what you want to build/i);
    fireEvent.change(textarea, { target: { value: "Build a REST API" } });
    const runBtn = screen.getByText("Run Planner");
    fireEvent.click(runBtn);
    await waitFor(() => expect(screen.getByText("Output")).toBeInTheDocument());
    await waitFor(() => expect(screen.getByText("Build a REST API")).toBeInTheDocument());
  });

  it("shows spec details in output tab", async () => {
    const data = mockPlannerResponse();
    const output = mockPlannerOutput();
    setupMock(data, output);
    render(<PlannerPanel />);
    const planTab = screen.getByText("Plan");
    fireEvent.click(planTab);
    fireEvent.change(screen.getByPlaceholderText(/Describe/i), { target: { value: "test prompt" } });
    fireEvent.click(screen.getByText("Run Planner"));
    await waitFor(() => expect(screen.getByText("Architecture:")).toBeInTheDocument());
    await waitFor(() => expect(screen.getByText("microservice")).toBeInTheDocument());
    await waitFor(() => expect(screen.getByText("Phases:")).toBeInTheDocument());
    await waitFor(() => expect(screen.getByText("Requirements:")).toBeInTheDocument());
  });

  it("shows ambiguities in output", async () => {
    const data = mockPlannerResponse();
    const output = mockPlannerOutput();
    setupMock(data, output);
    render(<PlannerPanel />);
    const planTab = screen.getByText("Plan");
    fireEvent.click(planTab);
    fireEvent.change(screen.getByPlaceholderText(/Describe/i), { target: { value: "test" } });
    fireEvent.click(screen.getByText("Run Planner"));
    await waitFor(() => expect(screen.getByText("Ambiguities Found")).toBeInTheDocument());
    await waitFor(() => expect(screen.getByText("API")).toBeInTheDocument());
  });

  it("shows context budget bar", async () => {
    const data = mockPlannerResponse();
    const output = mockPlannerOutput();
    setupMock(data, output);
    render(<PlannerPanel />);
    const planTab = screen.getByText("Plan");
    fireEvent.click(planTab);
    fireEvent.change(screen.getByPlaceholderText(/Describe/i), { target: { value: "test" } });
    fireEvent.click(screen.getByText("Run Planner"));
    await waitFor(() => expect(screen.getByText("Context Budget")).toBeInTheDocument());
  });

  it("shows build phases in output", async () => {
    const data = mockPlannerResponse();
    const output = mockPlannerOutput();
    setupMock(data, output);
    render(<PlannerPanel />);
    const planTab = screen.getByText("Plan");
    fireEvent.click(planTab);
    fireEvent.change(screen.getByPlaceholderText(/Describe/i), { target: { value: "test" } });
    fireEvent.click(screen.getByText("Run Planner"));
    await waitFor(() => expect(screen.getByText("Build Phases")).toBeInTheDocument());
    await waitFor(() => expect(screen.getByText("Setup")).toBeInTheDocument());
    await waitFor(() => expect(screen.getByText("API")).toBeInTheDocument());
  });

  it("shows error state on fetch failure", async () => {
    mockFetch.mockRejectedValueOnce(new Error("Network error"));
    const consoleSpy = jest.spyOn(console, "error").mockImplementation(() => {});
    render(<PlannerPanel />);
    await waitFor(() => expect(screen.getByText("Network error")).toBeInTheDocument());
    consoleSpy.mockRestore();
  });

  it("disables run button when prompt is empty", async () => {
    const data = mockPlannerResponse();
    setupMock(data);
    render(<PlannerPanel />);
    const planTab = screen.getByText("Plan");
    fireEvent.click(planTab);
    const btn = screen.getByText("Run Planner");
    expect(btn).toHaveAttribute("disabled");
  });

  it("enables run button when prompt has text", async () => {
    const data = mockPlannerResponse();
    setupMock(data);
    render(<PlannerPanel />);
    const planTab = screen.getByText("Plan");
    fireEvent.click(planTab);
    const textarea = screen.getByPlaceholderText(/Describe/i);
    fireEvent.change(textarea, { target: { value: "test" } });
    const btn = screen.getByText("Run Planner");
    expect(btn).not.toHaveAttribute("disabled");
  });

  it("renders template pros and cons", async () => {
    const data = mockPlannerResponse();
    setupMock(data);
    render(<PlannerPanel />);
    await waitFor(() => expect(screen.getByText("Pros:")).toBeInTheDocument());
    await waitFor(() => expect(screen.getByText("Cons:")).toBeInTheDocument());
  });

  it("renders template recommended_for", async () => {
    const data = mockPlannerResponse();
    setupMock(data);
    render(<PlannerPanel />);
    await waitFor(() => expect(screen.getByText("Enterprise")).toBeInTheDocument());
  });

  it("shows 'Run the planner' placeholder when no output", async () => {
    const data = mockPlannerResponse();
    setupMock(data);
    render(<PlannerPanel />);
    const outputTab = screen.getByText("Output");
    fireEvent.click(outputTab);
    await waitFor(() => expect(screen.getByText("Run the planner to see output here")).toBeInTheDocument());
  });
});
