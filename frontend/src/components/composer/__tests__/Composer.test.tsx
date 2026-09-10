/**
 * Tests for the Composer component.
 *
 * Composer is the chat input bar with model pill, textarea, send/stop
 * buttons, file attachment, and vision mode. We mock @assistant-ui/react
 * and the adapter, then test rendering and interaction.
 */

import React from "react";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { Composer } from "../Composer";

// Module-level state object — accessible from mock factory
const mockState = { isRunning: false, messages: [] as any[] };

// Mock @assistant-ui/react — factory reads from shared object
jest.mock("@assistant-ui/react", () => ({
  useAuiState: jest.fn((selector: (s: any) => any) => {
    return selector({ thread: { isRunning: mockState.isRunning, messages: mockState.messages } });
  }),
}));

// Mock the adapter
const mockAdapter = {
  sendMessage: jest.fn().mockResolvedValue(undefined),
  interrupt: jest.fn(),
} as any;

function setStreaming(isStreaming: boolean) {
  mockState.isRunning = isStreaming;
  if (isStreaming) {
    mockState.messages = [{ role: "assistant" as const, content: [] }];
  } else {
    mockState.messages = [];
  }
}

function renderComposer(props: Record<string, any> = {}) {
  return render(
    <Composer
      adapter={mockAdapter}
      isActive={true}
      sessionId="test-session"
      model="Qwen3.6-35B-A3B"
      connectionState="connected"
      {...props}
    />
  );
}

describe("Composer", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    mockState.isRunning = false;
    mockState.messages = [];
  });

  it("renders textarea with placeholder", () => {
    renderComposer();
    const textarea = screen.getByRole("textbox");
    expect(textarea).toBeInTheDocument();
  });

  it("renders send button", () => {
    renderComposer();
    expect(screen.getByTitle("Send")).toBeInTheDocument();
  });

  it("renders file attachment button", () => {
    renderComposer();
    expect(screen.getByTitle("Attach file")).toBeInTheDocument();
  });

  it("renders model pill when onModelChange provided", () => {
    renderComposer({ onModelChange: jest.fn() });
    const all = document.body.textContent;
    expect(all).toContain("Qwen3.6-35B");
  });

  it("does not render model pill when isActive is false", () => {
    renderComposer({ isActive: false, onModelChange: jest.fn() });
    const all = document.body.textContent;
    expect(all).not.toContain("Qwen3.6-35B");
  });

  it("shows stop button when streaming", () => {
    setStreaming(true);
    renderComposer();
    expect(screen.getByTitle("Stop")).toBeInTheDocument();
  });

  it("shows send button when not streaming", () => {
    renderComposer();
    expect(screen.getByTitle("Send")).toBeInTheDocument();
    expect(screen.queryByTitle("Stop")).not.toBeInTheDocument();
  });

  it("sends message on Enter key", async () => {
    renderComposer({ onSendMessage: mockAdapter.sendMessage });
    const textarea = screen.getByRole("textbox");
    fireEvent.change(textarea, { target: { value: "Hello" } });
    fireEvent.keyDown(textarea, { key: "Enter" });
    await waitFor(() => expect(mockAdapter.sendMessage).toHaveBeenCalledWith("Hello"));
  });

  it("sends message on send button click", async () => {
    renderComposer({ onSendMessage: mockAdapter.sendMessage });
    const textarea = screen.getByRole("textbox");
    fireEvent.change(textarea, { target: { value: "Test message" } });
    fireEvent.click(screen.getByTitle("Send"));
    await waitFor(() => expect(mockAdapter.sendMessage).toHaveBeenCalledWith("Test message"));
  });

  it("clears textarea after sending", async () => {
    renderComposer({ onSendMessage: mockAdapter.sendMessage });
    const textarea = screen.getByRole("textbox");
    fireEvent.change(textarea, { target: { value: "Test message" } });
    fireEvent.click(screen.getByTitle("Send"));
    await waitFor(() => expect(textarea).toHaveValue(""));
  });

  it("does not send empty message", () => {
    renderComposer({ onSendMessage: mockAdapter.sendMessage });
    fireEvent.click(screen.getByTitle("Send"));
    expect(mockAdapter.sendMessage).not.toHaveBeenCalled();
  });

  it("disables send button when no text and not streaming", () => {
    renderComposer();
    const sendBtn = screen.getByTitle("Send");
    expect(sendBtn).toBeDisabled();
  });

  it("enables send button when streaming", () => {
    setStreaming(true);
    renderComposer();
    const stopBtn = screen.getByTitle("Stop");
    expect(stopBtn).not.toBeDisabled();
  });

  it("shows connection status", () => {
    renderComposer({ connectionState: "disconnected" });
    const textarea = screen.getByRole("textbox");
    expect(textarea).toHaveAttribute("placeholder", "Disconnected");
  });

  it("calls onInterrupt when stop button clicked", () => {
    setStreaming(true);
    renderComposer({ onInterrupt: mockAdapter.interrupt });
    fireEvent.click(screen.getByTitle("Stop"));
    expect(mockAdapter.interrupt).toHaveBeenCalled();
  });

  it("handles file attachment", () => {
    const mockAttach = jest.fn();
    renderComposer({ onAttachFiles: mockAttach });
    const fileInput = document.querySelector('input[type="file"]') as HTMLInputElement;
    const file = new File(["test"], "test.txt", { type: "text/plain" });
    fireEvent.change(fileInput, { target: { files: [file] } });
    expect(mockAttach).toHaveBeenCalledWith([file]);
  });

  it("shortens model name by stripping path", () => {
    renderComposer({ model: "/path/to/Qwen3.6-35B-A3B", onModelChange: jest.fn() });
    const all = document.body.textContent;
    expect(all).toMatch(/Qwen3\.6-35B/);
  });

  it("renders with custom CSS variables", () => {
    const { container } = renderComposer();
    const root = container.querySelector('[data-slot="composer-root"]');
    expect(root).toHaveStyle({ "--composer-control-size": "1.5rem" });
  });

  it("handles Escape to interrupt while streaming", () => {
    setStreaming(true);
    renderComposer({ onInterrupt: mockAdapter.interrupt });
    const textarea = screen.getByRole("textbox");
    fireEvent.keyDown(textarea, { key: "Escape" });
    expect(mockAdapter.interrupt).toHaveBeenCalled();
  });
});
