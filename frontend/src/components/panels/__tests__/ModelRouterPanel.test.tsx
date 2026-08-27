/**
 * Tests for ModelRouterPanel — loading, decision interface, model cards, tier display.
 */

import React from "react";
import { render, screen, waitFor, fireEvent } from "@testing-library/react";

jest.mock("@/lib/api", () => {
  const mockGetModels = jest.fn();
  const mockGetRoutingDecision = jest.fn();
  return {
    api: {
      getModels: mockGetModels,
      getRoutingDecision: mockGetRoutingDecision,
    },
    ModelProfile: Object,
    RoutingDecision: Object,
  };
});

import { ModelRouterPanel } from "../ModelRouterPanel";
import * as api from "@/lib/api";

const mockGetModels = api.api.getModels as jest.Mock;
const mockGetRoutingDecision = api.api.getRoutingDecision as jest.Mock;

describe("ModelRouterPanel", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    mockGetModels.mockReset();
    mockGetRoutingDecision.mockReset();
  });

  function mockModels() {
    return [
      {
        name: "qwen3-35b",
        model_name: "Qwen3.6-35B-A3B",
        tier: "power",
        api_base: "http://localhost:8090/v1",
        context_window: 131072,
        is_default: true,
      },
      {
        name: "qwen3-30b",
        model_name: "Qwen3-Coder-30B",
        tier: "balanced",
        api_base: "http://localhost:8091/v1",
        context_window: 32768,
        is_default: false,
      },
      {
        name: "granite-8b",
        model_name: "Granite4.1-8B-UD",
        tier: "fast",
        api_base: "http://localhost:8092/v1",
        context_window: 8192,
        is_default: false,
      },
    ];
  }

  function mockDecision() {
    return {
      selected_model: "qwen3-35b",
      tier: "power",
      confidence: 0.92,
      reason: "High complexity task requires powerful model",
      fallback_model: "qwen3-30b",
    };
  }

  it("renders header", async () => {
    mockGetModels.mockResolvedValue([]);
    render(<ModelRouterPanel />);
    await waitFor(() => expect(screen.getByText("Model Router")).toBeInTheDocument());
  });

  it("renders loading state for models", async () => {
    mockGetModels.mockImplementation(() => new Promise(() => {}));
    render(<ModelRouterPanel />);
    expect(screen.getByText("Loading models...")).toBeInTheDocument();
  });

  it("renders decision interface with input", async () => {
    mockGetModels.mockResolvedValue([]);
    render(<ModelRouterPanel />);
    expect(screen.getByPlaceholderText("Describe the task...")).toBeInTheDocument();
  });

  it("renders complexity slider", async () => {
    mockGetModels.mockResolvedValue([]);
    render(<ModelRouterPanel />);
    const sliders = screen.getAllByRole("slider");
    expect(sliders).toHaveLength(1);
  });

  it("renders Decide button", async () => {
    mockGetModels.mockResolvedValue([]);
    render(<ModelRouterPanel />);
    expect(screen.getByText("Decide")).toBeInTheDocument();
  });

  it("renders available models section", async () => {
    mockGetModels.mockResolvedValue(mockModels());
    render(<ModelRouterPanel />);
    await waitFor(() => expect(screen.getByText("Available Models")).toBeInTheDocument());
  });

  it("renders model cards with names", async () => {
    mockGetModels.mockResolvedValue(mockModels());
    render(<ModelRouterPanel />);
    await waitFor(() => expect(screen.getByText("Qwen3.6-35B-A3B")).toBeInTheDocument());
    await waitFor(() => expect(screen.getByText("Qwen3-Coder-30B")).toBeInTheDocument());
    await waitFor(() => expect(screen.getByText("Granite4.1-8B-UD")).toBeInTheDocument());
  });

  it("renders tier badges", async () => {
    mockGetModels.mockResolvedValue(mockModels());
    render(<ModelRouterPanel />);
    await waitFor(() => expect(screen.getByText("Power")).toBeInTheDocument());
    await waitFor(() => expect(screen.getByText("Balanced")).toBeInTheDocument());
    await waitFor(() => expect(screen.getByText("Fast")).toBeInTheDocument());
  });

  it("renders context window info", async () => {
    mockGetModels.mockResolvedValue(mockModels());
    render(<ModelRouterPanel />);
    await waitFor(() => expect(screen.getByText("Context: 131,072 tokens")).toBeInTheDocument());
  });

  it("renders default star on default model", async () => {
    mockGetModels.mockResolvedValue(mockModels());
    render(<ModelRouterPanel />);
    await waitFor(() => expect(screen.getByText("★ Default")).toBeInTheDocument());
  });

  it("renders API base info", async () => {
    mockGetModels.mockResolvedValue(mockModels());
    render(<ModelRouterPanel />);
    await waitFor(() => expect(screen.getByText("API: http://localhost:8090/v1")).toBeInTheDocument());
  });

  it("shows decision result after clicking Decide", async () => {
    mockGetModels.mockResolvedValue(mockModels());
    mockGetRoutingDecision.mockResolvedValue(mockDecision());
    render(<ModelRouterPanel />);
    await waitFor(() => expect(screen.getByText("Available Models")).toBeInTheDocument());
    const input = screen.getByPlaceholderText("Describe the task...");
    fireEvent.change(input, { target: { value: "Write a complex algorithm" } });
    fireEvent.click(screen.getByText("Decide"));
    await waitFor(() => expect(screen.getByText("Power")).toBeInTheDocument());
    await waitFor(() => expect(screen.getByText("Qwen3.6-35B-A3B")).toBeInTheDocument());
  });

  it("shows confidence percentage in decision", async () => {
    mockGetModels.mockResolvedValue(mockModels());
    mockGetRoutingDecision.mockResolvedValue(mockDecision());
    render(<ModelRouterPanel />);
    const input = screen.getByPlaceholderText("Describe the task...");
    fireEvent.change(input, { target: { value: "Test task" } });
    fireEvent.click(screen.getByText("Decide"));
    await waitFor(() => expect(screen.getByText("Confidence: 92%")).toBeInTheDocument());
  });

  it("shows decision reason", async () => {
    mockGetModels.mockResolvedValue(mockModels());
    mockGetRoutingDecision.mockResolvedValue(mockDecision());
    render(<ModelRouterPanel />);
    const input = screen.getByPlaceholderText("Describe the task...");
    fireEvent.change(input, { target: { value: "Test task" } });
    fireEvent.click(screen.getByText("Decide"));
    await waitFor(() => expect(screen.getByText("High complexity task requires powerful model")).toBeInTheDocument());
  });

  it("shows fallback model in decision", async () => {
    mockGetModels.mockResolvedValue(mockModels());
    mockGetRoutingDecision.mockResolvedValue(mockDecision());
    render(<ModelRouterPanel />);
    const input = screen.getByPlaceholderText("Describe the task...");
    fireEvent.change(input, { target: { value: "Test task" } });
    fireEvent.click(screen.getByText("Decide"));
    await waitFor(() => expect(screen.getByText("Qwen3-Coder-30B")).toBeInTheDocument());
  });

  it("does not show decision when no input", async () => {
    mockGetModels.mockResolvedValue(mockModels());
    render(<ModelRouterPanel />);
    fireEvent.click(screen.getByText("Decide"));
    expect(screen.queryByText("Confidence:")).not.toBeInTheDocument();
  });

  it("handles API error gracefully", async () => {
    mockGetModels.mockResolvedValue(mockModels());
    mockGetRoutingDecision.mockRejectedValue(new Error("API error"));
    const consoleSpy = jest.spyOn(console, "error").mockImplementation(() => {});
    render(<ModelRouterPanel />);
    const input = screen.getByPlaceholderText("Describe the task...");
    fireEvent.change(input, { target: { value: "Test" } });
    fireEvent.click(screen.getByText("Decide"));
    await waitFor(() => expect(consoleSpy).toHaveBeenCalledWith("Routing decision failed:", expect.any(Error)));
    consoleSpy.mockRestore();
  });

  it("renders Expert tier badge", async () => {
    const models = mockModels();
    models.push({
      name: "expert-model",
      model_name: "Expert-Model",
      tier: "expert",
      api_base: "http://localhost:8093/v1",
      context_window: 2048,
      is_default: false,
    });
    mockGetModels.mockResolvedValue(models);
    render(<ModelRouterPanel />);
    await waitFor(() => expect(screen.getByText("Expert")).toBeInTheDocument());
  });

  it("renders complexity value next to slider", async () => {
    mockGetModels.mockResolvedValue([]);
    render(<ModelRouterPanel />);
    await waitFor(() => expect(screen.getByText("Complexity:")).toBeInTheDocument());
  });
});
