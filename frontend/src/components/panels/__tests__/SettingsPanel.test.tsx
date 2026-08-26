/**
 * Tests for SettingsPanel — section toggling, config updates, plugin toggling.
 */

import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { SettingsPanel } from "@/components/panels/SettingsPanel";
import * as api from "@/lib/api";

jest.mock("@/lib/api", () => ({
  api: {
    updateConfig: jest.fn().mockResolvedValue(undefined),
    togglePlugin: jest.fn().mockResolvedValue(undefined),
  },
  PluginInfo: Object,
}));

describe("SettingsPanel", () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  it("renders settings header", () => {
    render(<SettingsPanel />);
    expect(screen.getByText("Settings & Preferences")).toBeInTheDocument();
  });

  it("renders all section headers", () => {
    render(<SettingsPanel />);
    expect(screen.getByText("models")).toBeInTheDocument();
    expect(screen.getByText("appearance")).toBeInTheDocument();
    expect(screen.getByText("system")).toBeInTheDocument();
    expect(screen.getByText("plugins")).toBeInTheDocument();
    expect(screen.getByText("keys")).toBeInTheDocument();
  });

  it("expands and collapses sections", () => {
    render(<SettingsPanel />);
    const modelSection = screen.getByText("models");
    fireEvent.click(modelSection);
    expect(screen.getByText("Default Model")).toBeInTheDocument();
    fireEvent.click(modelSection);
    expect(screen.queryByText("Default Model")).not.toBeInTheDocument();
  });

  it("renders model settings when expanded", () => {
    render(<SettingsPanel />);
    const modelSection = screen.getByText("models");
    fireEvent.click(modelSection);
    expect(screen.getByText("Default Model")).toBeInTheDocument();
    expect(screen.getByText("Context Window")).toBeInTheDocument();
    expect(screen.getByText("Max Tokens")).toBeInTheDocument();
  });

  it("renders appearance settings when expanded", () => {
    render(<SettingsPanel />);
    const appearanceSection = screen.getByText("appearance");
    fireEvent.click(appearanceSection);
    expect(screen.getByText("Font Size")).toBeInTheDocument();
    expect(screen.getByText("UI Density")).toBeInTheDocument();
  });

  it("renders system settings when expanded", () => {
    render(<SettingsPanel />);
    const systemSection = screen.getByText("system");
    fireEvent.click(systemSection);
    expect(screen.getByText("Auto-Save Interval (minutes)")).toBeInTheDocument();
    expect(screen.getByText("Enable automatic backups")).toBeInTheDocument();
  });

  it("renders keys settings when expanded", () => {
    render(<SettingsPanel />);
    const keysSection = screen.getByText("keys");
    fireEvent.click(keysSection);
    expect(screen.getByText("API keys are stored securely and encrypted at rest.")).toBeInTheDocument();
  });

  it("renders initial config values", () => {
    const initialConfig = {
      models: { default_model: "qwen3-coder-30b", context_window: 4096, max_tokens: 16000 },
      appearance: { font_size: "large", density: "compact" },
      system: { auto_save_interval: 5, enable_backups: true },
    };
    render(<SettingsPanel initialConfig={initialConfig} />);
    const modelSection = screen.getByText("models");
    fireEvent.click(modelSection);
    const selects = screen.getAllByRole("combobox");
    expect(selects[0]).toHaveValue("qwen3-coder-30b");
  });

  it("saves config on model select change", async () => {
    render(<SettingsPanel />);
    const modelSection = screen.getByText("models");
    fireEvent.click(modelSection);
    const selects = screen.getAllByRole("combobox");
    fireEvent.change(selects[0], { target: { value: "qwen3-coder-30b" } });
    await waitFor(() => {
      expect(api.api.updateConfig).toHaveBeenCalledWith("models.default_model", "qwen3-coder-30b");
    });
  });

  it("saves config on context window change", async () => {
    render(<SettingsPanel />);
    const modelSection = screen.getByText("models");
    fireEvent.click(modelSection);
    const inputs = screen.getAllByRole("spinbutton");
    fireEvent.change(inputs[0], { target: { value: "8192" } });
    await waitFor(() => {
      expect(api.api.updateConfig).toHaveBeenCalledWith("models.context_window", 8192);
    });
  });

  it("saves config on max tokens change", async () => {
    render(<SettingsPanel />);
    const modelSection = screen.getByText("models");
    fireEvent.click(modelSection);
    const range = screen.getByRole("slider");
    fireEvent.change(range, { target: { value: "16000" } });
    await waitFor(() => {
      expect(api.api.updateConfig).toHaveBeenCalledWith("models.max_tokens", 16000);
    });
  });

  it("saves config on font size change", async () => {
    render(<SettingsPanel />);
    const appearanceSection = screen.getByText("appearance");
    fireEvent.click(appearanceSection);
    const selects = screen.getAllByRole("combobox");
    fireEvent.change(selects[0], { target: { value: "large" } });
    await waitFor(() => {
      expect(api.api.updateConfig).toHaveBeenCalledWith("appearance.font_size", "large");
    });
  });

  it("saves config on UI density change", async () => {
    render(<SettingsPanel />);
    const appearanceSection = screen.getByText("appearance");
    fireEvent.click(appearanceSection);
    const selects = screen.getAllByRole("combobox");
    fireEvent.change(selects[1], { target: { value: "compact" } });
    await waitFor(() => {
      expect(api.api.updateConfig).toHaveBeenCalledWith("appearance.density", "compact");
    });
  });

  it("saves config on auto-save interval change", async () => {
    render(<SettingsPanel />);
    const systemSection = screen.getByText("system");
    fireEvent.click(systemSection);
    const inputs = screen.getAllByRole("spinbutton");
    fireEvent.change(inputs[0], { target: { value: "10" } });
    await waitFor(() => {
      expect(api.api.updateConfig).toHaveBeenCalledWith("system.auto_save_interval", 10);
    });
  });

  it("saves config on backup toggle change", async () => {
    render(<SettingsPanel />);
    const systemSection = screen.getByText("system");
    fireEvent.click(systemSection);
    const checkbox = screen.getByRole("checkbox");
    fireEvent.click(checkbox);
    await waitFor(() => {
      expect(api.api.updateConfig).toHaveBeenCalledWith("system.enable_backups", true);
    });
  });

  it("handles save error gracefully", async () => {
    (api.api.updateConfig as jest.Mock).mockRejectedValueOnce(new Error("Network error"));
    const consoleSpy = jest.spyOn(console, "error").mockImplementation(() => {});
    render(<SettingsPanel />);
    const modelSection = screen.getByText("models");
    fireEvent.click(modelSection);
    const selects = screen.getAllByRole("combobox");
    fireEvent.change(selects[0], { target: { value: "qwen3-coder-30b" } });
    await waitFor(() => {
      expect(consoleSpy).toHaveBeenCalledWith("Failed to save config:", expect.any(Error));
    });
    consoleSpy.mockRestore();
  });

  it("renders plugin section with loading state", () => {
    render(<SettingsPanel />);
    const pluginsSection = screen.getByText("plugins");
    fireEvent.click(pluginsSection);
    expect(screen.getByText("Loading plugins...")).toBeInTheDocument();
  });

  it("renders keys section with API key entries", () => {
    render(<SettingsPanel />);
    const keysSection = screen.getByText("keys");
    fireEvent.click(keysSection);
    expect(screen.getByText("searxng API Key")).toBeInTheDocument();
    expect(screen.getByText("tavily API Key")).toBeInTheDocument();
    expect(screen.getByText("farfalle API Key")).toBeInTheDocument();
    expect(screen.getByText("gmail API Key")).toBeInTheDocument();
  });

  it("renders Change buttons for each API key", () => {
    render(<SettingsPanel />);
    const keysSection = screen.getByText("keys");
    fireEvent.click(keysSection);
    const changeButtons = screen.getAllByText("Change");
    expect(changeButtons).toHaveLength(4);
  });

  it("renders section icons", () => {
    render(<SettingsPanel />);
    expect(screen.getByText("🧠")).toBeInTheDocument();
    expect(screen.getByText("🎨")).toBeInTheDocument();
    expect(screen.getByText("⚙️")).toBeInTheDocument();
    expect(screen.getByText("🔌")).toBeInTheDocument();
    expect(screen.getByText("🔑")).toBeInTheDocument();
  });

  it("renders max tokens display with default value", () => {
    render(<SettingsPanel />);
    const modelSection = screen.getByText("models");
    fireEvent.click(modelSection);
    expect(screen.getByText("8000")).toBeInTheDocument();
  });

  it("renders max tokens display with custom value", () => {
    render(<SettingsPanel initialConfig={{ models: { max_tokens: 16000 } }} />);
    const modelSection = screen.getByText("models");
    fireEvent.click(modelSection);
    expect(screen.getByText("16000")).toBeInTheDocument();
  });

  it("renders 1K and 32K labels for max tokens range", () => {
    render(<SettingsPanel />);
    const modelSection = screen.getByText("models");
    fireEvent.click(modelSection);
    expect(screen.getByText("1K")).toBeInTheDocument();
    expect(screen.getByText("32K")).toBeInTheDocument();
  });

  it("renders font size options", () => {
    render(<SettingsPanel />);
    const appearanceSection = screen.getByText("appearance");
    fireEvent.click(appearanceSection);
    expect(screen.getByText("Small (12px)")).toBeInTheDocument();
    expect(screen.getByText("Medium (14px)")).toBeInTheDocument();
    expect(screen.getByText("Large (16px)")).toBeInTheDocument();
  });

  it("renders UI density options", () => {
    render(<SettingsPanel />);
    const appearanceSection = screen.getByText("appearance");
    fireEvent.click(appearanceSection);
    expect(screen.getByText("Comfortable")).toBeInTheDocument();
    expect(screen.getByText("Compact")).toBeInTheDocument();
    expect(screen.getByText("Dense")).toBeInTheDocument();
  });

  it("renders model options", () => {
    render(<SettingsPanel />);
    const modelSection = screen.getByText("models");
    fireEvent.click(modelSection);
    const selects = screen.getAllByRole("combobox");
    expect(selects[0]).toHaveTextContent("Qwen3.6-35B-A3B");
    expect(selects[0]).toHaveTextContent("Qwen3-Coder-30B");
  });
});
