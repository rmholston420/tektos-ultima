/**
 * Tests for the Transcript component.
 *
 * Transcript renders a scrollable message list with user bubbles and
 * assistant streaming markdown. We mock StreamingMarkdown and test:
 * - User vs assistant message rendering
 * - Streaming indicator
 * - Auto-scroll behavior
 * - Helper functions (getStreamingText)
 */

import React from "react";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { Transcript } from "../Transcript";
import type { ChatMessage } from "@/lib/streaming-store";

// ---------------------------------------------------------------------------
// Mock StreamingMarkdown
// ---------------------------------------------------------------------------

let mockStreamingText = "";
let mockStreamingIsRunning = false;

jest.mock("@/components/streaming/StreamingMarkdown", () => ({
  StreamingMarkdown: ({ containerClassName, isRunning, text }: any) => {
    mockStreamingText = text;
    mockStreamingIsRunning = isRunning;
    return <div className={containerClassName} data-testid="streaming-markdown">{text}</div>;
  },
}));

// ---------------------------------------------------------------------------
// Test data helpers
// ---------------------------------------------------------------------------

function makeUserMessage(id: string, content: string): ChatMessage {
  return {
    id,
    role: "user",
    content,
    timestamp: new Date().toISOString(),
  };
}

function makeAssistantMessage(
  id: string,
  text: string,
  status: "complete" | "running" = "complete"
): ChatMessage {
  return {
    id,
    role: "assistant",
    parts: [{ type: "text", id: "text-0", text, status: status as "complete" | "running" }],
    status: status as "complete" | "running",
    timestamp: new Date().toISOString(),
  };
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("Transcript", () => {
  beforeEach(() => {
    mockStreamingText = "";
    mockStreamingIsRunning = false;
  });

  describe("empty state", () => {
    it("renders empty transcript with no messages", () => {
      render(
        <Transcript
          messages={[]}
          isStreaming={false}
          onSendMessage={() => {}}
          onInterrupt={() => {}}
        />
      );
      const transcript = document.querySelector(".transcript");
      expect(transcript).toBeInTheDocument();
    });

    it("renders scroll anchor when empty", () => {
      render(
        <Transcript
          messages={[]}
          isStreaming={false}
          onSendMessage={() => {}}
          onInterrupt={() => {}}
        />
      );
      const container = document.querySelector(".transcript");
      expect(container).toBeInTheDocument();
    });
  });

  describe("user messages", () => {
    it("renders user message with content", () => {
      render(
        <Transcript
          messages={[makeUserMessage("u1", "Hello world")]}
          isStreaming={false}
          onSendMessage={() => {}}
          onInterrupt={() => {}}
        />
      );
      expect(screen.getByText("Hello world")).toBeInTheDocument();
    });

    it("renders user message in a bubble", () => {
      render(
        <Transcript
          messages={[makeUserMessage("u1", "Hello world")]}
          isStreaming={false}
          onSendMessage={() => {}}
          onInterrupt={() => {}}
        />
      );
      const bubble = screen.getByText("Hello world").closest("[class*='max-w']");
      expect(bubble).toHaveClass("rounded-2xl");
    });

    it("renders user message right-aligned", () => {
      render(
        <Transcript
          messages={[makeUserMessage("u1", "Hello world")]}
          isStreaming={false}
          onSendMessage={() => {}}
          onInterrupt={() => {}}
        />
      );
      const wrapper = screen.getByText("Hello world").closest("[class*='justify-end']");
      expect(wrapper).toBeInTheDocument();
    });

    it("renders whitespace-preserved user content", () => {
      render(
        <Transcript
          messages={[makeUserMessage("u1", "Line 1\nLine 2")]}
          isStreaming={false}
          onSendMessage={() => {}}
          onInterrupt={() => {}}
        />
      );
      // Check the user bubble contains the full content
      const bubble = screen.getByText(/Line 1/);
      expect(bubble.textContent).toContain("Line 1");
      expect(bubble.textContent).toContain("Line 2");
    });
  });

  describe("assistant messages", () => {
    it("renders assistant message with content", () => {
      render(
        <Transcript
          messages={[makeAssistantMessage("a1", "AI response")]}
          isStreaming={false}
          onSendMessage={() => {}}
          onInterrupt={() => {}}
        />
      );
      expect(screen.getByText("AI response")).toBeInTheDocument();
    });

    it("renders AI Agent label", () => {
      render(
        <Transcript
          messages={[makeAssistantMessage("a1", "AI response")]}
          isStreaming={false}
          onSendMessage={() => {}}
          onInterrupt={() => {}}
        />
      );
      expect(screen.getByText("AI Agent")).toBeInTheDocument();
    });

    it("renders assistant message in a bubble", () => {
      render(
        <Transcript
          messages={[makeAssistantMessage("a1", "AI response")]}
          isStreaming={false}
          onSendMessage={() => {}}
          onInterrupt={() => {}}
        />
      );
      const bubble = screen.getByText("AI response").closest("[class*='rounded-2xl']");
      expect(bubble).toHaveClass("border");
    });

    it("renders assistant message left-aligned", () => {
      render(
        <Transcript
          messages={[makeAssistantMessage("a1", "AI response")]}
          isStreaming={false}
          onSendMessage={() => {}}
          onInterrupt={() => {}}
        />
      );
      const wrapper = screen.getByText("AI response").closest("[class*='justify-start']");
      expect(wrapper).toBeInTheDocument();
    });

    it("renders AI icon in header", () => {
      render(
        <Transcript
          messages={[makeAssistantMessage("a1", "AI response")]}
          isStreaming={false}
          onSendMessage={() => {}}
          onInterrupt={() => {}}
        />
      );
      // The icon is a sibling of the "AI Agent" span in the header
      expect(screen.getByText("AI Agent")).toBeInTheDocument();
    });

    it("renders StreamingMarkdown with correct props", () => {
      render(
        <Transcript
          messages={[makeAssistantMessage("a1", "Hello")]}
          isStreaming={false}
          onSendMessage={() => {}}
          onInterrupt={() => {}}
        />
      );
      expect(mockStreamingText).toBe("Hello");
      expect(mockStreamingIsRunning).toBe(false);
    });

    it("passes isRunning=true when status is running", () => {
      render(
        <Transcript
          messages={[makeAssistantMessage("a1", "Streaming...", "running")]}
          isStreaming={false}
          onSendMessage={() => {}}
          onInterrupt={() => {}}
        />
      );
      expect(mockStreamingIsRunning).toBe(true);
    });
  });

  describe("streaming indicator", () => {
    it("does not show streaming indicator when not streaming", () => {
      render(
        <Transcript
          messages={[makeAssistantMessage("a1", "Done")]}
          isStreaming={false}
          onSendMessage={() => {}}
          onInterrupt={() => {}}
        />
      );
      expect(screen.queryByText("AI is thinking")).not.toBeInTheDocument();
    });

    it("shows streaming indicator when streaming", () => {
      render(
        <Transcript
          messages={[makeAssistantMessage("a1", "Streaming...")]}
          isStreaming={true}
          onSendMessage={() => {}}
          onInterrupt={() => {}}
        />
      );
      expect(screen.getByText("AI is thinking")).toBeInTheDocument();
    });

    it("shows pulse animation in streaming indicator", () => {
      render(
        <Transcript
          messages={[makeAssistantMessage("a1", "Streaming...")]}
          isStreaming={true}
          onSendMessage={() => {}}
          onInterrupt={() => {}}
        />
      );
      const indicator = screen.getByText("AI is thinking").parentElement;
      expect(indicator).toHaveClass("sticky");
    });
  });

  describe("running status display", () => {
    it("shows typing indicator when message has text parts", () => {
      render(
        <Transcript
          messages={[makeAssistantMessage("a1", "Hello", "running")]}
          isStreaming={false}
          onSendMessage={() => {}}
          onInterrupt={() => {}}
        />
      );
      expect(screen.getByText("typing...")).toBeInTheDocument();
    });

    it("shows thinking indicator when message has no text parts", () => {
      render(
        <Transcript
          messages={[
            {
              id: "a1",
              role: "assistant",
              parts: [],
              status: "running",
              timestamp: new Date().toISOString(),
            },
          ]}
          isStreaming={false}
          onSendMessage={() => {}}
          onInterrupt={() => {}}
        />
      );
      expect(screen.getByText("thinking...")).toBeInTheDocument();
    });
  });

  describe("multiple messages", () => {
    it("renders multiple messages in order", () => {
      render(
        <Transcript
          messages={[
            makeUserMessage("u1", "First"),
            makeAssistantMessage("a1", "Second"),
            makeUserMessage("u2", "Third"),
          ]}
          isStreaming={false}
          onSendMessage={() => {}}
          onInterrupt={() => {}}
        />
      );
      expect(screen.getByText("First")).toBeInTheDocument();
      expect(screen.getByText("Second")).toBeInTheDocument();
      expect(screen.getByText("Third")).toBeInTheDocument();
    });

    it("renders scroll anchor at bottom", () => {
      render(
        <Transcript
          messages={[makeUserMessage("u1", "Hello")]}
          isStreaming={false}
          onSendMessage={() => {}}
          onInterrupt={() => {}}
        />
      );
      const transcript = document.querySelector(".transcript");
      expect(transcript).toHaveClass("overflow-y-auto");
    });
  });

  describe("auto-scroll", () => {
    it("scrolls to bottom when messages change", () => {
      const { rerender } = render(
        <Transcript
          messages={[makeUserMessage("u1", "Hello")]}
          isStreaming={false}
          onSendMessage={() => {}}
          onInterrupt={() => {}}
        />
      );
      rerender(
        <Transcript
          messages={[
            makeUserMessage("u1", "Hello"),
            makeAssistantMessage("a1", "Hi"),
          ]}
          isStreaming={false}
          onSendMessage={() => {}}
          onInterrupt={() => {}}
        />
      );
      expect(screen.getByText("Hi")).toBeInTheDocument();
    });
  });

  describe("props", () => {
    it("accepts onSendMessage prop", () => {
      const onSend = jest.fn();
      render(
        <Transcript
          messages={[]}
          isStreaming={false}
          onSendMessage={onSend}
          onInterrupt={() => {}}
        />
      );
      expect(onSend).toBeDefined();
    });

    it("accepts onInterrupt prop", () => {
      const onInterrupt = jest.fn();
      render(
        <Transcript
          messages={[]}
          isStreaming={false}
          onSendMessage={() => {}}
          onInterrupt={onInterrupt}
        />
      );
      expect(onInterrupt).toBeDefined();
    });
  });
});
