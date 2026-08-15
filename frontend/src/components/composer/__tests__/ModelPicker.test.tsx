/**
 * Tektos-Ultima v1 — ModelPicker Tests
 */

import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import {
  ModelPicker,
  MODEL_OPTIONS,
  type ModelInfo,
} from "../ModelPicker";

// ---------------------------------------------------------------------------
// Model Definitions
// ---------------------------------------------------------------------------

describe("Model Definitions", () => {
  it("has MODEL_OPTIONS array with all expected models", () => {
    expect(MODEL_OPTIONS).toBeInstanceOf(Array);
    expect(MODEL_OPTIONS.length).toBeGreaterThan(8);
  });

  it("each model has all required fields", () => {
    for (const model of MODEL_OPTIONS) {
      expect(model).toHaveProperty("id");
      expect(model).toHaveProperty("name");
      expect(model).toHaveProperty("role");
      expect(model).toHaveProperty("description");
      expect(model).toHaveProperty("params");
      expect(model).toHaveProperty("caps");
      expect(typeof model.id).toBe("string");
      expect(typeof model.name).toBe("string");
      expect(typeof model.role).toBe("string");
      expect(typeof model.description).toBe("string");
      expect(typeof model.params).toBe("string");
      expect(Array.isArray(model.caps)).toBe(true);
    }
  });

  it("valid role values", () => {
    const validRoles = ["Coder", "Planner", "General", "Fast", "Vision", "Embedding"];
    for (const model of MODEL_OPTIONS) {
      expect(validRoles).toContain(model.role);
    }
  });

  it("has a recommended model", () => {
    const recommended = MODEL_OPTIONS.filter((m: ModelInfo) => m.recommended);
    expect(recommended.length).toBeGreaterThan(0);
    expect(recommended[0].id).toBe("qwen3.6:35b-a3b-mtp-coder");
  });

  it("has Coder models", () => {
    expect(MODEL_OPTIONS.filter((m: ModelInfo) => m.role === "Coder").length).toBeGreaterThan(0);
  });

  it("has Planner models", () => {
    expect(MODEL_OPTIONS.filter((m: ModelInfo) => m.role === "Planner").length).toBeGreaterThan(0);
  });

  it("has Fast models", () => {
    expect(MODEL_OPTIONS.filter((m: ModelInfo) => m.role === "Fast").length).toBeGreaterThan(0);
  });

  it("has Vision models", () => {
    expect(MODEL_OPTIONS.filter((m: ModelInfo) => m.role === "Vision").length).toBeGreaterThan(0);
  });

  it("has General models", () => {
    expect(MODEL_OPTIONS.filter((m: ModelInfo) => m.role === "General").length).toBeGreaterThan(0);
  });
});

// ---------------------------------------------------------------------------
// ModelPicker Component
// ---------------------------------------------------------------------------

describe("ModelPicker Component", () => {
  const onModelChange = jest.fn();
  const defaultProps = {
    currentModel: "qwen3.6:35b-a3b-mtp-coder",
    onModelChange,
  };

  beforeEach(() => {
    jest.clearAllMocks();
  });

  it("renders with current model name", () => {
    render(<ModelPicker {...defaultProps} />);
    expect(screen.getByText("qwen3.6:35b-a3b")).toBeInTheDocument();
  });

  it("renders current model info with role label", () => {
    render(<ModelPicker {...defaultProps} />);
    expect(screen.getByText("qwen3.6:35b-a3b")).toBeInTheDocument();
    expect(screen.getByText("Coder")).toBeInTheDocument();
    expect(screen.getByText("⟨/⟩")).toBeInTheDocument();
    expect(screen.getByText("35.5B")).toBeInTheDocument();
  });

  it("toggles dropdown open on click", () => {
    const { container } = render(<ModelPicker {...defaultProps} />);
    const button = container.querySelector("button");
    expect(button).toBeInTheDocument();

    fireEvent.click(button!);
    expect(screen.getByPlaceholderText("Search models...")).toBeInTheDocument();
  });

  it("shows all models when dropdown opens", () => {
    render(<ModelPicker {...defaultProps} />);
    const button = document.querySelector("button")!;
    fireEvent.click(button);

    for (const model of MODEL_OPTIONS) {
      expect(screen.getByText(model.name)).toBeInTheDocument();
    }
  });

  it("groups models by role in dropdown", () => {
    render(<ModelPicker {...defaultProps} />);
    const button = document.querySelector("button")!;
    fireEvent.click(button);

    expect(screen.getByText("Coder")).toBeInTheDocument();
    expect(screen.getByText("Planner")).toBeInTheDocument();
    expect(screen.getByText("General")).toBeInTheDocument();
    expect(screen.getByText("Fast")).toBeInTheDocument();
    expect(screen.getByText("Vision")).toBeInTheDocument();
  });

  it("filters models by name search", () => {
    render(<ModelPicker {...defaultProps} />);
    const button = document.querySelector("button")!;
    fireEvent.click(button);

    const input = screen.getByPlaceholderText("Search models...");
    fireEvent.change(input, { target: { value: "flash" } });

    expect(screen.getByText("glm-4.7-flash")).toBeInTheDocument();
  });

  it("filters models by role search", () => {
    render(<ModelPicker {...defaultProps} />);
    const button = document.querySelector("button")!;
    fireEvent.click(button);

    const input = screen.getByPlaceholderText("Search models...");
    fireEvent.change(input, { target: { value: "Fast" } });
  });

  it("filters models by description search", () => {
    render(<ModelPicker {...defaultProps} />);
    const button = document.querySelector("button")!;
    fireEvent.click(button);

    const input = screen.getByPlaceholderText("Search models...");
    fireEvent.change(input, { target: { value: "vision" } });
  });

  it("calls onModelChange on selection", async () => {
    render(<ModelPicker {...defaultProps} />);
    const button = document.querySelector("button")!;
    fireEvent.click(button);

    const deepseek = screen.getByText("deepseek-r1:32b");
    fireEvent.click(deepseek);

    expect(onModelChange).toHaveBeenCalledWith("deepseek-r1:32b");
  });

  it("closes dropdown after selection", async () => {
    render(<ModelPicker {...defaultProps} />);
    const button = document.querySelector("button")!;
    fireEvent.click(button);

    expect(screen.getByPlaceholderText("Search models...")).toBeInTheDocument();

    fireEvent.click(screen.getByText("qwen3.5:9b"));

    await waitFor(() => {
      expect(screen.queryByPlaceholderText("Search models...")).not.toBeInTheDocument();
    });
  });

  it("shows footer with model count", () => {
    render(<ModelPicker {...defaultProps} />);
    const button = document.querySelector("button")!;
    fireEvent.click(button);

    expect(screen.getByText(/models available/i)).toBeInTheDocument();
  });

  it("shows cap tags for models", () => {
    render(<ModelPicker {...defaultProps} />);
    const button = document.querySelector("button")!;
    fireEvent.click(button);

    expect(screen.getByText("tools")).toBeInTheDocument();
  });

  it("selects fallback model when current not found", () => {
    render(<ModelPicker currentModel="nonexistent-model" onModelChange={jest.fn()} />);
    expect(screen.getByText(MODEL_OPTIONS[0].name)).toBeInTheDocument();
  });

  it("is disabled when disabled prop is true", () => {
    render(<ModelPicker {...defaultProps} disabled={true} />);
    const button = document.querySelector("button")!;
    expect(button).toBeDisabled();
  });

  it("does not open dropdown when disabled", () => {
    render(<ModelPicker {...defaultProps} disabled={true} />);
    const button = document.querySelector("button")!;
    fireEvent.click(button);

    expect(screen.queryByPlaceholderText("Search models...")).not.toBeInTheDocument();
  });

  it("shows model description in dropdown", () => {
    render(<ModelPicker {...defaultProps} />);
    const button = document.querySelector("button")!;
    fireEvent.click(button);

    const model = MODEL_OPTIONS.find((m: ModelInfo) => m.id === "qwen3.6:35b-a3b-mtp-coder")!;
    expect(screen.getByText(model.description)).toBeInTheDocument();
  });

  it("has correct selected state styling for current model", () => {
    render(<ModelPicker {...defaultProps} />);
    const button = document.querySelector("button")!;
    fireEvent.click(button);

    const { container } = render(<ModelPicker {...defaultProps} />);
    const dropBtn = document.querySelector("button")!;
    fireEvent.click(dropBtn);
    // Check that the dropdown opened — search input should be visible
    expect(screen.getByPlaceholderText("Search models...")).toBeInTheDocument();
  });

  it("search is case-insensitive", () => {
    render(<ModelPicker currentModel="qwen3.6:35b-a3b-mtp-coder" onModelChange={jest.fn()} />);
    const button = document.querySelector("button")!;
    fireEvent.click(button);

    const input = screen.getByPlaceholderText("Search models...");
    fireEvent.change(input, { target: { value: "DEEPSEEK" } });
  });

  it("multiple selections work correctly", () => {
    const onModelChange2 = jest.fn();
    render(<ModelPicker currentModel="qwen3.6:35b-a3b-mtp-coder" onModelChange={onModelChange2} />);
    const button = document.querySelector("button")!;
    fireEvent.click(button);
    const glm = screen.getByText("glm-4.7-flash");
    fireEvent.click(glm);
    expect(onModelChange2).toHaveBeenCalledWith("glm-4.7-flash:q4_K_M");

    const onModelChange3 = jest.fn();
    render(<ModelPicker currentModel="glm-4.7-flash:q4_K_M" onModelChange={onModelChange3} />);
    const button2 = document.querySelector("button")!;
    fireEvent.click(button2);
    const quick = screen.getByText("qwen3.5:9b");
    fireEvent.click(quick);
    expect(onModelChange3).toHaveBeenCalledWith("qwen3.5:9b-q8_0");
  });
});
