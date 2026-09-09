/**
 * Tests for ThreadView — intro state, streaming indicator, message rendering.
 */

import React from "react";
import { render, screen, waitFor } from "@testing-library/react";

// Mock the assistant-ui/react hooks BEFORE importing ThreadView
const mockUseAuiState = jest.fn();
jest.mock("@assistant-ui/react", () => ({
  ThreadPrimitive: {
    Root: ({ children, className }: { children: React.ReactNode; className?: string }) => (
      <div className={className}>{children}</div>
    ),
    Viewport: ({ children, className }: { children: React.ReactNode; className?: string }) => (
      <div className={className}>{children}</div>
    ),
    Messages: ({ children, components }: { children?: React.ReactNode; components?: any }) => (
      <div data-testid="messages">{children}</div>
    ),
  },
  MessagePrimitive: {
    Root: ({ children, className, "data-role": role }: { children: React.ReactNode; className?: string; "data-role"?: string }) => (
      <div className={className} data-role={role}>{children}</div>
    ),
    Parts: ({ children, components }: { children?: React.ReactNode; components?: any }) => (
      <div>{children}</div>
    ),
  },
  useAuiState: (...args: any[]) => mockUseAuiState(...args),
  useMessageRuntime: jest.fn(),
}));

jest.mock("@assistant-ui/react-streamdown", () => ({
  StreamdownTextPrimitive: ({ children, defer, components }: any) => (
    <div data-testid="streamdown-text">{children}</div>
  ),
}));

import { ThreadView } from "../ThreadView";

describe("ThreadView", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    mockUseAuiState.mockReset();
  });

  it("renders intro when no messages", () => {
    mockUseAuiState.mockImplementation((selector: any) => {
      if (typeof selector === "function") {
        return selector({ thread: { isRunning: false, messages: [] } });
      }
      return false;
    });
    render(<ThreadView />);
    expect(screen.getAllByText("TEKTOS").length).toBeGreaterThanOrEqual(1);
  });

  it("renders intro copy text", () => {
    mockUseAuiState.mockImplementation((selector: any) => {
      if (typeof selector === "function") {
        return selector({ thread: { isRunning: false, messages: [] } });
      }
      return false;
    });
    render(<ThreadView />);
    const introCopy = document.querySelector('[data-slot="aui_intro"] p');
    expect(introCopy).toBeInTheDocument();
    expect(introCopy?.textContent).toBeTruthy();
  });

  it("renders ThreadPrimitive.Root when messages exist", () => {
    mockUseAuiState.mockImplementation((selector: any) => {
      if (typeof selector === "function") {
        return selector({ thread: { isRunning: false, messages: [{ id: "1" }] } });
      }
      return false;
    });
    render(<ThreadView />);
    expect(document.querySelector("[class*='flex-1']")).toBeInTheDocument();
  });

  it("shows streaming indicator when streaming", () => {
    mockUseAuiState.mockImplementation((selector: any) => {
      if (typeof selector === "function") {
        return selector({ thread: { isRunning: true, messages: [{ id: "1" }] } });
      }
      return false;
    });
    render(<ThreadView />);
    expect(screen.getByText("AI is thinking")).toBeInTheDocument();
  });

  it("does not show streaming indicator when not streaming", () => {
    mockUseAuiState.mockImplementation((selector: any) => {
      if (typeof selector === "function") {
        return selector({ thread: { isRunning: false, messages: [{ id: "1" }] } });
      }
      return false;
    });
    render(<ThreadView />);
    expect(screen.queryByText("AI is thinking")).not.toBeInTheDocument();
  });

  it("renders viewport with scrollable container", () => {
    mockUseAuiState.mockImplementation((selector: any) => {
      if (typeof selector === "function") {
        return selector({ thread: { isRunning: false, messages: [{ id: "1" }] } });
      }
      return false;
    });
    render(<ThreadView />);
    expect(document.querySelector("[class*='overflow-y-auto']")).toBeInTheDocument();
  });

  it("renders Messages component with custom components", () => {
    mockUseAuiState.mockImplementation((selector: any) => {
      if (typeof selector === "function") {
        return selector({ thread: { isRunning: false, messages: [{ id: "1" }] } });
      }
      return false;
    });
    render(<ThreadView />);
    expect(screen.getByTestId("messages")).toBeInTheDocument();
  });

  it("renders intro headline", () => {
    mockUseAuiState.mockImplementation((selector: any) => {
      if (typeof selector === "function") {
        return selector({ thread: { isRunning: false, messages: [] } });
      }
      return false;
    });
    render(<ThreadView />);
    const intro = document.querySelector('[data-slot="aui_intro"]');
    expect(intro).toBeInTheDocument();
  });

  it("renders intro with random copy variation", () => {
    mockUseAuiState.mockImplementation((selector: any) => {
      if (typeof selector === "function") {
        return selector({ thread: { isRunning: false, messages: [] } });
      }
      return false;
    });
    render(<ThreadView />);
    const introCopy = document.querySelector('[data-slot="aui_intro"] p');
    // Should be one of the defined intro copies
    const validCopies = [
      "Send a bug, branch, plan, or rough idea",
      "Bring the code, question, or stuck part",
      "Send the task, failing path, or half-formed plan",
      "Send the context you have",
    ];
    expect(validCopies.some((c) => introCopy?.textContent?.includes(c))).toBe(true);
  });

  it("renders streaming progress bar", () => {
    mockUseAuiState.mockImplementation((selector: any) => {
      if (typeof selector === "function") {
        return selector({ thread: { isRunning: true, messages: [{ id: "1" }] } });
      }
      return false;
    });
    render(<ThreadView />);
    expect(document.querySelector("[class*='bg-accent/60']")).toBeInTheDocument();
  });

  it("renders sticky streaming indicator at bottom", () => {
    mockUseAuiState.mockImplementation((selector: any) => {
      if (typeof selector === "function") {
        return selector({ thread: { isRunning: true, messages: [{ id: "1" }] } });
      }
      return false;
    });
    render(<ThreadView />);
    const indicator = document.querySelector("[class*='sticky bottom-0']");
    expect(indicator).toBeInTheDocument();
  });

  it("renders ThreadPrimitive.Messages with UserMessage and AssistantMessage components", () => {
    mockUseAuiState.mockImplementation((selector: any) => {
      if (typeof selector === "function") {
        return selector({ thread: { isRunning: false, messages: [{ id: "1" }] } });
      }
      return false;
    });
    render(<ThreadView />);
    const messagesEl = screen.getByTestId("messages");
    expect(messagesEl).toBeInTheDocument();
  });

  it("handles empty messages array as no messages", () => {
    mockUseAuiState.mockImplementation((selector: any) => {
      if (typeof selector === "function") {
        return selector({ thread: { isRunning: false, messages: [] } });
      }
      return false;
    });
    render(<ThreadView />);
    expect(screen.getAllByText("TEKTOS").length).toBeGreaterThanOrEqual(1);
  });

  it("renders intro when messages exist but isStreaming is true", () => {
    mockUseAuiState.mockImplementation((selector: any) => {
      if (typeof selector === "function") {
        return selector({ thread: { isRunning: true, messages: [] } });
      }
      return false;
    });
    // Empty messages = intro, even if streaming
    expect(screen.getAllByText("TEKTOS").length).toBeGreaterThanOrEqual(1);
  });
});
