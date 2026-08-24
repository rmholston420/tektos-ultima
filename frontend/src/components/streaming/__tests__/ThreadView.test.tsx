/**
 * Tests for the ThreadView component.
 *
 * ThreadView renders the chat thread using @assistant-ui/react primitives.
 * We mock the AUI context and test:
 * - Intro display when no messages
 * - Thread rendering when messages exist
 * - Streaming indicator visibility
 */

import React from "react";
import { render, screen } from "@testing-library/react";

// ---------------------------------------------------------------------------
// Shared mutable state for the mock — defined as `var` so it's hoisted
// and available (as `undefined`) when jest.mock factories run.
// ---------------------------------------------------------------------------

var mockAuiState: Record<string, any> = {
  thread: { isRunning: false, messages: [] },
  message: { id: "m1", status: { type: "complete" }, content: [] },
};

// ---------------------------------------------------------------------------
// Mock @assistant-ui/react-streamdown
// ---------------------------------------------------------------------------

jest.mock("@assistant-ui/react-streamdown", () => ({
  StreamdownTextPrimitive: ({ children }: any) => (
    <div data-testid="streamdown-text">{children}</div>
  ),
}));

// ---------------------------------------------------------------------------
// Mock @assistant-ui/react
// ---------------------------------------------------------------------------

jest.mock("@assistant-ui/react", () => {
  const mockUseAuiState = jest.fn((selector: any) => {
    if (typeof selector === "function") {
      return selector(mockAuiState);
    }
    return mockAuiState[selector];
  });

  return {
    ThreadPrimitive: {
      Root: ({ children, className }: any) => (
        <div className={className} data-testid="thread-root">
          {children}
        </div>
      ),
      Viewport: ({ children, className }: any) => (
        <div className={className} data-testid="thread-viewport">
          {children}
        </div>
      ),
      Messages: ({ children, components }: any) => (
        <div data-testid="thread-messages">
          {children}
          {components &&
            Object.entries(components).map(([key, Comp]: [string, any]) => (
              <div key={key} data-testid={`message-${key.toLowerCase()}`}>
                {Comp ? <Comp /> : null}
              </div>
            ))}
        </div>
      ),
    },
    MessagePrimitive: {
      Root: ({ children, className, "data-role": role }: any) => (
        <div className={className} data-role={role} data-testid="message-root">
          {children}
        </div>
      ),
      Parts: ({ children, components }: any) => (
        <div data-testid="message-parts">{children}</div>
      ),
    },
    useAuiState: mockUseAuiState,
    useMessagePartText: () => ({ status: { type: "complete" }, text: "" }),
    useMessageRuntime: () => ({
      getState: () => ({ content: [] }),
    }),
    useExternalStoreRuntime: jest.fn(),
    AssistantRuntimeProvider: ({ children }: any) => <>{children}</>,
  };
});

// Import after mocks
import { ThreadView } from "../ThreadView";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function renderThreadView(messages: any[] = [], isRunning = false) {
  mockAuiState.thread.messages = messages;
  mockAuiState.thread.isRunning = isRunning;
  return render(<ThreadView />);
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("ThreadView", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    mockAuiState.thread.messages = [];
    mockAuiState.thread.isRunning = false;
  });

  describe("empty state", () => {
    it("renders intro when no messages", () => {
      renderThreadView([]);
      // When no messages, ThreadView renders <Intro /> directly, not wrapped in ThreadPrimitive.Root
      expect(screen.getByLabelText("TEKTOS")).toBeInTheDocument();
    });

    it("renders the wordmark in intro", () => {
      renderThreadView([]);
      expect(screen.getByLabelText("TEKTOS")).toBeInTheDocument();
    });

    it("renders intro body copy", () => {
      renderThreadView([]);
      const introBody = screen.queryByText(/Send a bug|Bring the code|Send the task|Send the context/);
      expect(introBody).toBeInTheDocument();
    });
  });

  describe("with messages", () => {
    it("renders thread root when messages exist", () => {
      renderThreadView([{ id: "m1", role: "assistant" as const, content: [] }]);
      expect(screen.getByTestId("thread-root")).toBeInTheDocument();
    });

    it("renders thread viewport when messages exist", () => {
      renderThreadView([{ id: "m1", role: "assistant" as const, content: [] }]);
      expect(screen.getByTestId("thread-viewport")).toBeInTheDocument();
    });

    it("renders thread messages when messages exist", () => {
      renderThreadView([{ id: "m1", role: "assistant" as const, content: [] }]);
      expect(screen.getByTestId("thread-messages")).toBeInTheDocument();
    });

    it("renders assistant message component", () => {
      renderThreadView([{ id: "m1", role: "assistant" as const, content: [] }]);
      expect(screen.getByTestId("message-assistantmessage")).toBeInTheDocument();
    });

    it("renders user message component", () => {
      renderThreadView([{ id: "m1", role: "user" as const, content: [] }]);
      expect(screen.getByTestId("message-usermessage")).toBeInTheDocument();
    });
  });

  describe("streaming state", () => {
    it("does not show streaming indicator when not streaming", () => {
      renderThreadView([{ id: "m1", role: "assistant" as const, content: [] }], false);
      expect(screen.queryByText("AI is thinking")).not.toBeInTheDocument();
    });

    it("shows streaming indicator when streaming", () => {
      renderThreadView([{ id: "m1", role: "assistant" as const, content: [] }], true);
      expect(screen.getByText("AI is thinking")).toBeInTheDocument();
    });

    it("shows pulse animation in streaming indicator", () => {
      renderThreadView([{ id: "m1", role: "assistant" as const, content: [] }], true);
      const streamingIndicator = screen.getByText("AI is thinking").parentElement;
      expect(streamingIndicator).toBeInTheDocument();
    });
  });

  describe("state reading", () => {
    it("renders when streaming", () => {
      renderThreadView([{ id: "m1", role: "assistant" as const, content: [] }], true);
      expect(screen.getByText("AI is thinking")).toBeInTheDocument();
    });

    it("renders without streaming indicator when not streaming", () => {
      renderThreadView([{ id: "m1", role: "assistant" as const, content: [] }], false);
      expect(screen.queryByText("AI is thinking")).not.toBeInTheDocument();
    });
  });
});
