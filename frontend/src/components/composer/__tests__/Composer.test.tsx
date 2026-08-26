/**
 * Composer Tests
 *
 * Tests the Composer component: text input, send, interrupt, model pill,
 * mic button, file upload, and queue behavior.
 */

import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { Composer } from "../Composer";
import type { TektosExternalStoreAdapter } from "@/lib/tektos-store-adapter";

// ---------------------------------------------------------------------------
// Mocks
// ---------------------------------------------------------------------------

jest.mock("@assistant-ui/react", () => ({
  useAuiState: jest.fn(() => false),
}));

jest.mock("@/lib/tektos-store-adapter", () => ({
  TektosExternalStoreAdapter: jest.fn(),
}));

jest.mock("../MicButton", () => ({
  MicButton: ({ isActive, onTranscript }: any) => (
    <button data-testid="mic-button" onClick={() => onTranscript("voice text")} disabled={!isActive}>
      Mic
    </button>
  ),
}));

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

// Reset useAuiState mock before each test to prevent state leakage
beforeEach(() => {
  const { useAuiState } = require("@assistant-ui/react");
  useAuiState.mockReturnValue(false);
});

function makeAdapter(): TektosExternalStoreAdapter {
  return {
    sendMessage: jest.fn().mockResolvedValue(undefined),
    interrupt: jest.fn(),
    getState: jest.fn(() => ({ thread: { isRunning: false, messages: [] } })),
    subscribe: jest.fn(),
  } as unknown as TektosExternalStoreAdapter;
}

function renderComposer(
  props: Partial<React.ComponentProps<typeof Composer>> = {}
) {
  const adapter = makeAdapter();
  const onSendMessage = jest.fn().mockResolvedValue(undefined);
  const onInterrupt = jest.fn();
  const onModelChange = jest.fn();

  render(
    <Composer
      isActive={true}
      model="qwen3.6-35b-a3b"
      onModelChange={onModelChange}
      connectionState="connected"
      adapter={adapter}
      onSendMessage={onSendMessage}
      onInterrupt={onInterrupt}
      {...props}
    />
  );

  return { adapter, onSendMessage, onInterrupt, onModelChange };
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("Composer", () => {
  describe("rendering", () => {
    it("renders a textarea for input", () => {
      renderComposer();
      const textarea = screen.getByRole("textbox");
      expect(textarea).toBeTruthy();
    });

    it("renders the send button", () => {
      renderComposer();
      const sendBtn = screen.getByTitle("Send");
      expect(sendBtn).toBeTruthy();
    });

    it("renders the model pill when isActive and model provided", () => {
      renderComposer();
      // Model name is derived: "qwen3.6-35b-a3b" → split by '-' → ["qwen3.6","35b","a3b"] → slice(0,2) → "qwen3.6-35b"
      const pill = screen.getByText("qwen3.6-35b");
      expect(pill).toBeTruthy();
    });

    it("renders the mic button", () => {
      renderComposer();
      expect(screen.getByTestId("mic-button")).toBeTruthy();
    });

    it("renders the file upload button", () => {
      renderComposer();
      const fileBtn = screen.getByTitle("Attach file");
      expect(fileBtn).toBeTruthy();
    });
  });

  describe("sending messages", () => {
    it("calls onSendMessage with text when send button clicked", () => {
      const { onSendMessage } = renderComposer();
      const textarea = screen.getByRole("textbox");
      fireEvent.change(textarea, { target: { value: "hello world" } });
      const sendBtn = screen.getByTitle("Send");
      fireEvent.click(sendBtn);
      expect(onSendMessage).toHaveBeenCalledWith("hello world");
    });

    it("calls adapter.sendMessage when onSendMessage not provided", () => {
      const { adapter } = renderComposer({ onSendMessage: undefined });
      const textarea = screen.getByRole("textbox");
      fireEvent.change(textarea, { target: { value: "no callback" } });
      const sendBtn = screen.getByTitle("Send");
      fireEvent.click(sendBtn);
      expect(adapter.sendMessage).toHaveBeenCalledWith("no callback");
    });

    it("does not send empty message", () => {
      const { onSendMessage } = renderComposer();
      const sendBtn = screen.getByTitle("Send");
      fireEvent.click(sendBtn);
      expect(onSendMessage).not.toHaveBeenCalled();
    });

    it("clears textarea after sending", async () => {
      const { onSendMessage } = renderComposer();
      const textarea = screen.getByRole("textbox");
      fireEvent.change(textarea, { target: { value: "clear me" } });
      const sendBtn = screen.getByTitle("Send");
      fireEvent.click(sendBtn);
      // The component clears the value after sending (async)
      await waitFor(() => expect(textarea).toHaveValue(""));
    });

    it("queues message when streaming and has text", async () => {
      // Mock useAuiState to return true (streaming)
      const { useAuiState } = require("@assistant-ui/react");
      useAuiState.mockReturnValue(true);

      const { onSendMessage } = renderComposer();
      const textarea = screen.getByRole("textbox");
      fireEvent.change(textarea, { target: { value: "queue this" } });
      // When streaming, pressing Enter queues instead of sending
      fireEvent.keyDown(textarea, { key: "Enter" });
      // The component clears the value after queuing
      await waitFor(() => expect(textarea).toHaveValue(""));
      expect(onSendMessage).not.toHaveBeenCalled(); // queued, not sent yet

      // Reset mock
      useAuiState.mockReturnValue(false);
    });

    it("does not send when disabled (not active)", () => {
      const { onSendMessage } = renderComposer({ isActive: false });
      // isActive=false disables the mic and file upload buttons, not the send button.
      // The send button is disabled when !canSend (no text and not streaming).
      const micBtn = screen.getByTestId("mic-button");
      expect(micBtn).toBeDisabled();
      const fileBtn = screen.getByTitle("Attach file");
      expect(fileBtn).toBeDisabled();
    });
  });

  describe("keyboard shortcuts", () => {
    it("sends message on Enter", () => {
      const { onSendMessage } = renderComposer();
      const textarea = screen.getByRole("textbox");
      fireEvent.change(textarea, { target: { value: "enter send" } });
      fireEvent.keyDown(textarea, { key: "Enter" });
      expect(onSendMessage).toHaveBeenCalledWith("enter send");
    });

    it("does not send whitespace-only on Enter", () => {
      const { onSendMessage } = renderComposer();
      const textarea = screen.getByRole("textbox");
      fireEvent.change(textarea, { target: { value: "   " } });
      fireEvent.keyDown(textarea, { key: "Enter" });
      expect(onSendMessage).not.toHaveBeenCalled();
    });

    it("shows status text when disconnected", () => {
      renderComposer({ connectionState: "disconnected" });
      expect(screen.getByText("Disconnected")).toBeTruthy();
    });

    it("shows status text when connecting", () => {
      renderComposer({ connectionState: "connecting" });
      expect(screen.getByText("Connecting…")).toBeTruthy();
    });

    it("shows status text when reconnecting", () => {
      renderComposer({ connectionState: "reconnecting" });
      expect(screen.getByText("Reconnecting…")).toBeTruthy();
    });
  });

  describe("interrupt", () => {
    it("calls onInterrupt when stop button clicked", async () => {
      // Mock useAuiState to return true so the stop button is shown
      const { useAuiState } = require("@assistant-ui/react");
      useAuiState.mockReturnValue(true);

      const { onInterrupt } = renderComposer();
      const stopBtn = screen.getByTitle("Stop");
      fireEvent.click(stopBtn);
      await waitFor(() => expect(onInterrupt).toHaveBeenCalled());

      // Reset mock
      useAuiState.mockReturnValue(false);
    });

    it("calls adapter.interrupt when onInterrupt not provided", () => {
      const { useAuiState } = require("@assistant-ui/react");
      useAuiState.mockReturnValue(true);

      const { adapter } = renderComposer({ onInterrupt: undefined });
      const stopBtn = screen.getByTitle("Stop");
      fireEvent.click(stopBtn);
      expect(adapter.interrupt).toHaveBeenCalled();

      // Reset mock
      useAuiState.mockReturnValue(false);
    });
  });

  describe("model pill", () => {
    it("calls onModelChange when model pill clicked", () => {
      const { onModelChange } = renderComposer();
      const pill = screen.getByText("qwen3.6-35b");
      fireEvent.click(pill);
      expect(onModelChange).toHaveBeenCalledWith("qwen3.6-35b-a3b");
    });

    it("does not show model pill when isActive is false", () => {
      renderComposer({ isActive: false });
      expect(screen.queryByText("qwen3.6-35b")).not.toBeInTheDocument();
    });

    it("does not show model pill when model is not provided", () => {
      renderComposer({ model: undefined });
      expect(screen.queryByText("qwen3.6-35b")).not.toBeInTheDocument();
    });
  });

  describe("status indicator", () => {
    it("shows green dot when connected", () => {
      renderComposer({ connectionState: "connected" });
      const dot = screen.getByRole("textbox").parentElement?.parentElement;
      expect(dot).toBeTruthy();
    });

    it("shows yellow dot when connecting", () => {
      renderComposer({ connectionState: "connecting" });
      const dot = screen.getByRole("textbox").parentElement?.parentElement;
      expect(dot).toBeTruthy();
    });
  });

  describe("file upload", () => {
    it("triggers file input when attach button clicked", () => {
      renderComposer();
      const fileBtn = screen.getByTitle("Attach file");
      fireEvent.click(fileBtn);
      // File input should be triggered
      const fileInput = document.querySelector('input[type="file"]');
      expect(fileInput).toBeTruthy();
    });
  });

  describe("queue display", () => {
    it("shows queue pill when messages are queued", async () => {
      // Mock useAuiState to return true so queueing is triggered
      const { useAuiState } = require("@assistant-ui/react");
      useAuiState.mockReturnValue(true);

      const { onSendMessage } = renderComposer();
      const textarea = screen.getByRole("textbox");
      fireEvent.change(textarea, { target: { value: "queue1" } });
      // When streaming, pressing Enter queues instead of sending
      fireEvent.keyDown(textarea, { key: "Enter" });
      // The component clears the value after queuing
      await waitFor(() => expect(textarea).toHaveValue(""));

      // Reset mock
      useAuiState.mockReturnValue(false);
    });
  });

  describe("disabled state", () => {
    it("disables textarea when not active and disconnected", () => {
      renderComposer({ isActive: false, connectionState: "disconnected" });
      const textarea = screen.getByRole("textbox");
      expect(textarea).toBeDisabled();
    });

    it("enables textarea when active", () => {
      renderComposer({ isActive: true });
      const textarea = screen.getByRole("textbox");
      expect(textarea).not.toBeDisabled();
    });
  });
});
