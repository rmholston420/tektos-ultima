/**
 * Tests for ConfigPanel — loading, search, inline editing.
 */

import React from "react";
import { render, screen, waitFor, fireEvent } from "@testing-library/react";
import { ConfigPanel } from "../ConfigPanel";

// ConfigPanel uses fetch("/api/config"), not api.getConfig()
global.fetch = jest.fn();

describe("ConfigPanel", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    (global.fetch as jest.Mock).mockReset();
  });

  function mockConfigData() {
    return {
      config: [
        { key: "model.name", value: "qwen3-35b", type: "string" as const, description: "Model name", sensitive: false },
        { key: "model.temperature", value: "0.7", type: "number" as const, description: "Sampling temperature", sensitive: false },
        { key: "api.key", value: "sk-abc123", type: "string" as const, description: "API key", sensitive: true },
      ],
    };
  }

  it("renders loading spinner", async () => {
    (global.fetch as jest.Mock).mockImplementation(() => new Promise(() => {}));
    render(<ConfigPanel />);
    await waitFor(() => expect(document.querySelector(".animate-spin")).toBeInTheDocument());
  });

  it("renders header", async () => {
    (global.fetch as jest.Mock).mockResolvedValue({
      json: () => Promise.resolve(mockConfigData()),
    });
    render(<ConfigPanel />);
    await waitFor(() => expect(screen.getByText("System Configuration")).toBeInTheDocument());
  });

  it("renders search input", async () => {
    (global.fetch as jest.Mock).mockResolvedValue({
      json: () => Promise.resolve(mockConfigData()),
    });
    render(<ConfigPanel />);
    await waitFor(() => expect(screen.getByPlaceholderText("Search settings...")).toBeInTheDocument());
  });

  it("renders config keys", async () => {
    (global.fetch as jest.Mock).mockResolvedValue({
      json: () => Promise.resolve(mockConfigData()),
    });
    render(<ConfigPanel />);
    await waitFor(() => expect(screen.getByText("model.name")).toBeInTheDocument());
  });

  it("renders config types", async () => {
    (global.fetch as jest.Mock).mockResolvedValue({
      json: () => Promise.resolve(mockConfigData()),
    });
    render(<ConfigPanel />);
    await waitFor(() => expect(screen.getByText("String")).toBeInTheDocument());
    await waitFor(() => expect(screen.getByText("Number")).toBeInTheDocument());
  });

  it("renders config descriptions", async () => {
    (global.fetch as jest.Mock).mockResolvedValue({
      json: () => Promise.resolve(mockConfigData()),
    });
    render(<ConfigPanel />);
    await waitFor(() => expect(screen.getByText("Model name")).toBeInTheDocument());
  });

  it("renders sensitive badge", async () => {
    (global.fetch as jest.Mock).mockResolvedValue({
      json: () => Promise.resolve(mockConfigData()),
    });
    render(<ConfigPanel />);
    await waitFor(() => expect(screen.getByText("SENSITIVE")).toBeInTheDocument());
  });

  it("renders setting count", async () => {
    (global.fetch as jest.Mock).mockResolvedValue({
      json: () => Promise.resolve(mockConfigData()),
    });
    render(<ConfigPanel />);
    await waitFor(() => expect(screen.getByText("3 settings")).toBeInTheDocument());
  });

  it("filters config by search", async () => {
    (global.fetch as jest.Mock).mockResolvedValue({
      json: () => Promise.resolve(mockConfigData()),
    });
    render(<ConfigPanel />);
    const searchInput = await waitFor(() => screen.getByPlaceholderText("Search settings..."));
    fireEvent.change(searchInput, { target: { value: "model" } });
    await waitFor(() => expect(screen.getByText("model.name")).toBeInTheDocument());
    expect(screen.queryByText("api.key")).not.toBeInTheDocument();
  });

  it("case-insensitive search filter", async () => {
    (global.fetch as jest.Mock).mockResolvedValue({
      json: () => Promise.resolve(mockConfigData()),
    });
    render(<ConfigPanel />);
    const searchInput = await waitFor(() => screen.getByPlaceholderText("Search settings..."));
    fireEvent.change(searchInput, { target: { value: "MODEL" } });
    await waitFor(() => expect(screen.getByText("model.name")).toBeInTheDocument());
  });

  it("enters edit mode on click", async () => {
    (global.fetch as jest.Mock).mockResolvedValue({
      json: () => Promise.resolve(mockConfigData()),
    });
    render(<ConfigPanel />);
    await waitFor(() => expect(screen.getByText("model.name")).toBeInTheDocument());
    fireEvent.click(screen.getByText("qwen3-35b"));
    await waitFor(() => expect(screen.getByDisplayValue("qwen3-35b")).toBeInTheDocument());
  });

  it("shows masked value for sensitive config", async () => {
    (global.fetch as jest.Mock).mockResolvedValue({
      json: () => Promise.resolve(mockConfigData()),
    });
    render(<ConfigPanel />);
    await waitFor(() => expect(screen.getByText("••••••")).toBeInTheDocument());
  });

  it("handles fetch error gracefully", async () => {
    (global.fetch as jest.Mock).mockRejectedValue(new Error("Network error"));
    render(<ConfigPanel />);
    await waitFor(() => expect(screen.getByText("System Configuration")).toBeInTheDocument());
  });

  it("renders empty config list", async () => {
    (global.fetch as jest.Mock).mockResolvedValue({
      json: () => Promise.resolve({ config: [] }),
    });
    render(<ConfigPanel />);
    await waitFor(() => expect(screen.getByText("0 settings")).toBeInTheDocument());
  });

  it("saves edited value", async () => {
    (global.fetch as jest.Mock).mockResolvedValue({
      json: () => Promise.resolve(mockConfigData()),
    });
    render(<ConfigPanel />);
    await waitFor(() => expect(screen.getByText("model.name")).toBeInTheDocument());
    fireEvent.click(screen.getByText("qwen3-35b"));
    const editInput = await waitFor(() => screen.getByDisplayValue("qwen3-35b"));
    fireEvent.change(editInput, { target: { value: "new-model" } });
    fireEvent.click(screen.getByText("Save"));
    await waitFor(() => expect(screen.getByText("new-model")).toBeInTheDocument());
  });
});
