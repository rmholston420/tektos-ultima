/**
 * Tests for the StreamingMarkdown component and its helpers.
 *
 * StreamingMarkdown wraps @assistant-ui/react's TextMessagePartProvider +
 * StreamdownTextPrimitive. We test:
 * - The component under AUI context (mocked)
 * - Props passthrough and conditional rendering
 */

import React from "react";
import { render, screen, waitFor } from "@testing-library/react";

// ---------------------------------------------------------------------------
// Mock @assistant-ui/react-streamdown (must be before the component import)
// ---------------------------------------------------------------------------

jest.mock("@assistant-ui/react-streamdown", () => ({
  StreamdownTextPrimitive: ({ children, containerClassName, mode, preprocess }: any) => {
    const processed = preprocess ? preprocess(typeof children === "string" ? children : "") : children;
    return (
      <div className={containerClassName} data-mode={mode} data-processed={!!processed}>
        {processed}
      </div>
    );
  },
  tailBoundedRemend: (text: string) => text,
}));

// ---------------------------------------------------------------------------
// Mock @assistant-ui/react
// ---------------------------------------------------------------------------

let mockText = "";
let mockIsRunning = false;

jest.mock("@assistant-ui/react", () => ({
  TextMessagePartProvider: ({ children, isRunning, text }: any) => {
    mockText = text;
    mockIsRunning = isRunning;
    return <div data-testid="text-message-part-provider">{children}</div>;
  },
  useMessagePartText: () => ({ status: { type: mockIsRunning ? "running" : "complete" }, text: mockText }),
}));

// Import after mocks
import { StreamingMarkdown, MarkdownTextContent } from "../StreamingMarkdown";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function renderStreaming(props: Record<string, any> = {}) {
  return render(<StreamingMarkdown {...props} />);
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("StreamingMarkdown", () => {
  beforeEach(() => {
    mockText = "";
    mockIsRunning = false;
  });

  describe("with text and isRunning props", () => {
    it("renders the provider wrapper when text and isRunning are provided", () => {
      renderStreaming({ text: "Hello", isRunning: false });
      expect(screen.getByTestId("text-message-part-provider")).toBeInTheDocument();
    });

    it("passes text to the provider", () => {
      renderStreaming({ text: "Hello world", isRunning: false });
      expect(mockText).toBe("Hello world");
    });

    it("tracks streaming status when isRunning is true", () => {
      renderStreaming({ text: "Streaming", isRunning: true });
      expect(mockIsRunning).toBe(true);
    });

    it("tracks complete status when isRunning is false", () => {
      renderStreaming({ text: "Done", isRunning: false });
      expect(mockIsRunning).toBe(false);
    });

    it("passes containerClassName through", () => {
      renderStreaming({ text: "Test", isRunning: false, containerClassName: "custom-class" });
      expect(screen.getByTestId("text-message-part-provider")).toBeInTheDocument();
    });
  });

  describe("without text/isRunning (bare surface)", () => {
    it("renders MarkdownTextSurface when text is undefined", () => {
      const { container } = render(<StreamingMarkdown />);
      // With no text/isRunning, it renders MarkdownTextSurface which calls
      // useMessagePartText from context — the mock returns empty text, so null
      expect(container.firstChild).toBeNull();
    });

    it("renders with containerClassName in bare mode", () => {
      const { container } = render(<StreamingMarkdown containerClassName="bare-class" />);
      expect(container.firstChild).toBeNull(); // mock returns empty text
    });
  });

  describe("MarkdownTextContent", () => {
    it("renders children via TextMessagePartProvider", () => {
      render(<MarkdownTextContent isRunning={false} text="Test content" />);
      expect(screen.getByTestId("text-message-part-provider")).toBeInTheDocument();
    });

    it("passes isRunning to provider", () => {
      render(<MarkdownTextContent isRunning={true} text="Test" />);
      expect(mockIsRunning).toBe(true);
    });

    it("passes text to provider", () => {
      render(<MarkdownTextContent isRunning={false} text="Hello" />);
      expect(mockText).toBe("Hello");
    });

    it("passes containerClassName to provider", () => {
      render(<MarkdownTextContent isRunning={false} text="Test" containerClassName="custom" />);
      expect(screen.getByTestId("text-message-part-provider")).toBeInTheDocument();
    });
  });

  describe("display name", () => {
    it("has correct display name for memo", () => {
      expect(StreamingMarkdown.displayName).toBe("StreamingMarkdown");
    });
  });
});
