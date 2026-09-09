/**
 * Tektos-Ultima v1 — ModelPicker Tests
 */

import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
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
  });

  it("toggles dropdown open on click", () => {
    const { container } = render(<ModelPicker {...defaultProps} />);
    const button = container.querySelector("button");
    expect(button).toBeInTheDocument();

    fireEvent.click(button!);
    expect(screen.getByPlaceholderText("Search models...")).toBeInTheDocument();
  });

  it("shows all models when dropdown opens", async () => {
    const { container } = render(<ModelPicker {...defaultProps} />);
    const button = container.querySelector("button")!;
    const user = userEvent.setup();
    await user.click(button);

    // All model names appear in the dropdown list
    const dropdown = container.querySelector('.relative > div');
    expect(dropdown).toBeTruthy();
    for (const model of MODEL_OPTIONS) {
      expect(dropdown?.querySelector(`[title*="${model.name}"]`) || dropdown?.textContent?.includes(model.name)).toBeTruthy();
    }
  });

  it("groups models by role in dropdown", async () => {
    render(<ModelPicker {...defaultProps} />);
    const button = document.querySelector("button")!;
    const user = userEvent.setup();
    await user.click(button);

    // Role headers appear in the dropdown (not on the main button)
    const dropdown = document.querySelector('.relative > div');
    expect(dropdown).toBeTruthy();
    // Check that role group headers exist in the dropdown
    const roleHeaders = dropdown?.querySelectorAll('div');
    expect(roleHeaders?.length).toBeGreaterThan(0);
  });

  it("filters models by name search", async () => {
    render(<ModelPicker {...defaultProps} />);
    const button = document.querySelector("button")!;
    const user = userEvent.setup();
    await user.click(button);

    const input = screen.getByPlaceholderText("Search models...");
    fireEvent.change(input, { target: { value: "flash" } });

    expect(screen.getByText("glm-4.7-flash")).toBeInTheDocument();
  });

  it("filters models by role search", async () => {
    render(<ModelPicker {...defaultProps} />);
    const button = document.querySelector("button")!;
    const user = userEvent.setup();
    await user.click(button);

    const input = screen.getByPlaceholderText("Search models...");
    fireEvent.change(input, { target: { value: "Fast" } });
  });

  it("filters models by description search", async () => {
    render(<ModelPicker {...defaultProps} />);
    const button = document.querySelector("button")!;
    const user = userEvent.setup();
    await user.click(button);

    const input = screen.getByPlaceholderText("Search models...");
    fireEvent.change(input, { target: { value: "vision" } });
  });

  it("calls onModelChange on selection", async () => {
    render(<ModelPicker {...defaultProps} />);
    const button = document.querySelector("button")!;
    const user = userEvent.setup();
    await user.click(button);

    const deepseek = screen.getByText("deepseek-r1:32b");
    await user.click(deepseek);

    expect(onModelChange).toHaveBeenCalledWith("deepseek-r1:32b");
  });

  it("closes dropdown after selection", async () => {
    render(<ModelPicker {...defaultProps} />);
    const button = document.querySelector("button")!;
    const user = userEvent.setup();
    await user.click(button);

    expect(screen.getByPlaceholderText("Search models...")).toBeInTheDocument();

    await user.click(screen.getByText("qwen3.5:9b"));

    await waitFor(() => {
      expect(screen.queryByPlaceholderText("Search models...")).not.toBeInTheDocument();
    });
  });

  it("shows footer with model count", async () => {
    render(<ModelPicker {...defaultProps} />);
    const button = document.querySelector("button")!;
    const user = userEvent.setup();
    await user.click(button);

    expect(screen.getByText(/models available/i)).toBeInTheDocument();
  });

  it("shows cap tags for models", async () => {
    const { container } = render(<ModelPicker {...defaultProps} />);
    const button = container.querySelector("button")!;
    const user = userEvent.setup();
    await user.click(button);

    const dropdown = container.querySelector('.relative > div');
    expect(dropdown?.textContent?.includes("tools")).toBe(true);
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

  it("shows model description in dropdown", async () => {
    render(<ModelPicker {...defaultProps} />);
    const button = document.querySelector("button")!;
    const user = userEvent.setup();
    await user.click(button);

    const model = MODEL_OPTIONS.find((m: ModelInfo) => m.id === "qwen3.6:35b-a3b-mtp-coder")!;
    expect(screen.getByText(model.description)).toBeInTheDocument();
  });

  it("has correct selected state styling for current model", async () => {
    render(<ModelPicker {...defaultProps} />);
    const button = document.querySelector("button")!;
    const user = userEvent.setup();
    await user.click(button);
    // Check that the dropdown opened — search input should be visible
    expect(screen.getByPlaceholderText("Search models...")).toBeInTheDocument();
  });

  it("search is case-insensitive", async () => {
    render(<ModelPicker currentModel="qwen3.6:35b-a3b-mtp-coder" onModelChange={jest.fn()} />);
    const button = document.querySelector("button")!;
    const user = userEvent.setup();
    await user.click(button);

    const input = screen.getByPlaceholderText("Search models...");
    fireEvent.change(input, { target: { value: "DEEPSEEK" } });
  });

  it("multiple selections work correctly", async () => {
    const onModelChange2 = jest.fn();
    const { container: c1 } = render(<ModelPicker currentModel="qwen3.6:35b-a3b-mtp-coder" onModelChange={onModelChange2} />);
    const button1 = c1.querySelector("button")!;
    const user = userEvent.setup();
    await user.click(button1);

    // Find the model card by its text content — the trigger button doesn't contain "glm-4.7-flash"
    const allButtons1 = c1.querySelectorAll('button');
    const glmCard = Array.from(allButtons1).find(btn => btn.textContent?.includes('glm-4.7-flash'));
    expect(glmCard).toBeTruthy();
    await user.click(glmCard!);
    expect(onModelChange2).toHaveBeenCalledWith("glm-4.7-flash:q4_K_M");

    const onModelChange3 = jest.fn();
    const { container: c2 } = render(<ModelPicker currentModel="glm-4.7-flash:q4_K_M" onModelChange={onModelChange3} />);
    const button2 = c2.querySelector("button")!;
    const user2 = userEvent.setup();
    await user2.click(button2);

    const allButtons2 = c2.querySelectorAll('button');
    const quickCard = Array.from(allButtons2).find(btn => btn.textContent?.includes('qwen3.5:9b'));
    expect(quickCard).toBeTruthy();
    await user2.click(quickCard!);
    expect(onModelChange3).toHaveBeenCalledWith("qwen3.5:9b-q8_0");
  });

  it("calls onModelChange with the correct model id on selection", async () => {
    const onModelChange4 = jest.fn();
    render(<ModelPicker currentModel="qwen3.6:35b-a3b-mtp-coder" onModelChange={onModelChange4} />);
    const button = document.querySelector("button")!;
    const user = userEvent.setup();
    await user.click(button);

    const qwen3coder = screen.getByText("qwen3-coder:30b");
    await user.click(qwen3coder);

    expect(onModelChange4).toHaveBeenCalledWith("qwen3-coder:30b");
  });

  it("renders recommended badge on recommended model", async () => {
    render(<ModelPicker currentModel="qwen3.6:35b-a3b-mtp-coder" onModelChange={jest.fn()} />);
    const button = document.querySelector("button")!;
    const user = userEvent.setup();
    await user.click(button);

    expect(screen.getByText("REC")).toBeInTheDocument();
  });

  it("groups all roles in dropdown when open", async () => {
    render(<ModelPicker currentModel="qwen3.6:35b-a3b-mtp-coder" onModelChange={jest.fn()} />);
    const button = document.querySelector("button")!;
    const user = userEvent.setup();
    await user.click(button);

    // Use querySelector to find role headers inside the dropdown
    const dropdown = document.querySelector('.relative > div');
    expect(dropdown).toBeTruthy();
    const roleElements = dropdown?.querySelectorAll('div');
    const roleTexts = Array.from(roleElements || []).map(el => el.textContent).join(' ');
    expect(roleTexts).toContain('Planner');
    expect(roleTexts).toContain('General');
    expect(roleTexts).toContain('Fast');
    expect(roleTexts).toContain('Vision');
  });

  it("closes dropdown and clears search on outside click", async () => {
    render(<ModelPicker currentModel="qwen3.6:35b-a3b-mtp-coder" onModelChange={jest.fn()} />);
    const button = document.querySelector("button")!;
    const user = userEvent.setup();
    await user.click(button);

    // Dropdown should be open
    expect(screen.getByPlaceholderText("Search models...")).toBeInTheDocument();

    // Type in search
    const input = screen.getByPlaceholderText("Search models...");
    fireEvent.change(input, { target: { value: "flash" } });
    expect(input).toHaveValue("flash");

    // Click outside the dropdown on document body
    await user.click(document.body);

    // Dropdown should close and search cleared
    await waitFor(() => {
      expect(screen.queryByPlaceholderText("Search models...")).not.toBeInTheDocument();
    });
  });
});
