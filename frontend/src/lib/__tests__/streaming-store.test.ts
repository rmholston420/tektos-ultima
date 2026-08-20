/**
 * Tests for the streaming message hook — useStreamingMessages.
 *
 * Since this is a React hook, we test it by rendering it in a component.
 */

import { renderHook, act } from "@testing-library/react";
import { useStreamingMessages, type ChatMessage, type AssistantMessage, type UserMessage } from "@/lib/streaming-store";

describe("useStreamingMessages", () => {
  it("starts with empty messages and not streaming", () => {
    const { result } = renderHook(() => useStreamingMessages());
    expect(result.current.messages).toEqual([]);
    expect(result.current.isStreaming).toBe(false);
  });

  describe("sendMessage", () => {
    it("adds user and assistant messages", () => {
      const { result } = renderHook(() => useStreamingMessages());

      act(() => {
        result.current.sendMessage("hello world");
      });

      const messages = result.current.messages;
      expect(messages.length).toBe(2);

      // User message
      const userMsg = messages[0] as UserMessage;
      expect(userMsg.role).toBe("user");
      expect(userMsg.content).toBe("hello world");

      // Assistant message
      const assistantMsg = messages[1] as AssistantMessage;
      expect(assistantMsg.role).toBe("assistant");
      expect(assistantMsg.parts).toHaveLength(1);
      expect(assistantMsg.parts[0].type).toBe("text");
      expect(assistantMsg.parts[0].status).toBe("running");
    });

    it("sets isStreaming to true", () => {
      const { result } = renderHook(() => useStreamingMessages());

      act(() => {
        result.current.sendMessage("hello");
      });

      expect(result.current.isStreaming).toBe(true);
    });

    it("generates unique message IDs", () => {
      const { result } = renderHook(() => useStreamingMessages());

      act(() => {
        result.current.sendMessage("first");
      });
      const firstMsgs = result.current.messages;

      act(() => {
        result.current.sendMessage("second");
      });
      const secondMsgs = result.current.messages;

      expect(firstMsgs[0].id).not.toBe(secondMsgs[0].id);
      expect(firstMsgs[1].id).not.toBe(secondMsgs[1].id);
    });
  });

  describe("addDelta", () => {
    it("appends text to active assistant message", () => {
      const { result } = renderHook(() => useStreamingMessages());

      act(() => {
        result.current.sendMessage("hello");
      });

      act(() => {
        result.current.addDelta(" world");
      });

      const messages = result.current.messages;
      const assistantMsg = messages[1] as AssistantMessage;
      const textPart = assistantMsg.parts[0] as { type: "text"; text: string };
      expect(textPart.text).toBe(" world");
    });

    it("appends multiple deltas", () => {
      const { result } = renderHook(() => useStreamingMessages());

      act(() => {
        result.current.sendMessage("hello");
      });

      act(() => {
        result.current.addDelta(" world");
        result.current.addDelta("!");
      });

      const messages = result.current.messages;
      const assistantMsg = messages[1] as AssistantMessage;
      const textPart = assistantMsg.parts[0] as { type: "text"; text: string };
      expect(textPart.text).toBe(" world!");
    });

    it("does nothing when no active assistant", () => {
      const { result } = renderHook(() => useStreamingMessages());

      // No sendMessage called, so no active assistant
      act(() => {
        result.current.addDelta("orphan delta");
      });

      expect(result.current.messages.length).toBe(0);
    });

    it("does nothing when assistant is not running", () => {
      const { result } = renderHook(() => useStreamingMessages());

      act(() => {
        result.current.sendMessage("hello");
        result.current.completeMessage();
      });

      act(() => {
        result.current.addDelta("after complete");
      });

      const messages = result.current.messages;
      const assistantMsg = messages[1] as AssistantMessage;
      // Should not have changed
      const textPart = assistantMsg.parts[0] as { type: "text"; text: string };
      expect(textPart.text).toBe("");
    });
  });

  describe("completeMessage", () => {
    it("transitions assistant message to complete", () => {
      const { result } = renderHook(() => useStreamingMessages());

      act(() => {
        result.current.sendMessage("hello");
        result.current.addDelta(" world");
        result.current.completeMessage();
      });

      const messages = result.current.messages;
      const assistantMsg = messages[1] as AssistantMessage;
      const textPart = assistantMsg.parts[0] as { type: "text"; status: string };
      expect(textPart.status).toBe("complete");
      expect(assistantMsg.status).toBe("complete");
    });

    it("sets isStreaming to false", () => {
      const { result } = renderHook(() => useStreamingMessages());

      act(() => {
        result.current.sendMessage("hello");
        expect(result.current.isStreaming).toBe(true);

        result.current.completeMessage();
        expect(result.current.isStreaming).toBe(false);
      });
    });

    it("does nothing when no active assistant", () => {
      const { result } = renderHook(() => useStreamingMessages());

      act(() => {
        result.current.completeMessage();
      });

      // Should not throw or change state
      expect(result.current.messages.length).toBe(0);
    });
  });

  describe("interrupt", () => {
    it("interrupts active stream", () => {
      const { result } = renderHook(() => useStreamingMessages());

      act(() => {
        result.current.sendMessage("hello");
        result.current.addDelta(" world");
        result.current.interrupt();
      });

      const messages = result.current.messages;
      const assistantMsg = messages[1] as AssistantMessage;
      const textPart = assistantMsg.parts[0] as { type: "text"; status: string };
      expect(textPart.status).toBe("complete");
      expect(result.current.isStreaming).toBe(false);
    });

    it("does nothing when no active assistant", () => {
      const { result } = renderHook(() => useStreamingMessages());

      act(() => {
        result.current.interrupt();
      });

      expect(result.current.messages.length).toBe(0);
    });
  });

  describe("multiple messages", () => {
    it("handles multiple send/complete cycles", () => {
      const { result } = renderHook(() => useStreamingMessages());

      // First exchange
      act(() => {
        result.current.sendMessage("first");
        result.current.addDelta(" response");
        result.current.completeMessage();
      });

      // Second exchange
      act(() => {
        result.current.sendMessage("second");
        result.current.addDelta(" response 2");
        result.current.completeMessage();
      });

      const messages = result.current.messages;
      expect(messages.length).toBe(4); // 2 user + 2 assistant

      // Verify first exchange
      expect((messages[0] as UserMessage).content).toBe("first");
      const am1 = messages[1] as AssistantMessage;
      const tp1 = am1.parts[0] as { type: "text"; text: string; status: string };
      expect(tp1.text).toBe(" response");
      expect(tp1.status).toBe("complete");

      // Verify second exchange
      expect((messages[2] as UserMessage).content).toBe("second");
      const am2 = messages[3] as AssistantMessage;
      const tp2 = am2.parts[0] as { type: "text"; text: string; status: string };
      expect(tp2.text).toBe(" response 2");
      expect(tp2.status).toBe("complete");
    });

    it("maintains message order", () => {
      const { result } = renderHook(() => useStreamingMessages());

      act(() => {
        result.current.sendMessage("user-1");
        result.current.addDelta("assistant-1");
        result.current.sendMessage("user-2");
        result.current.addDelta("assistant-2");
        result.current.completeMessage();
        result.current.completeMessage();
      });

      const messages = result.current.messages;
      expect(messages[0].role).toBe("user");
      expect(messages[1].role).toBe("assistant");
      expect(messages[2].role).toBe("user");
      expect(messages[3].role).toBe("assistant");
    });
  });

  describe("isStreaming flag", () => {
    it("is true while streaming", () => {
      const { result } = renderHook(() => useStreamingMessages());

      act(() => {
        result.current.sendMessage("hello");
      });
      expect(result.current.isStreaming).toBe(true);

      act(() => {
        result.current.addDelta(" world");
      });
      expect(result.current.isStreaming).toBe(true);
    });

    it("is false when not streaming", () => {
      const { result } = renderHook(() => useStreamingMessages());
      expect(result.current.isStreaming).toBe(false);

      act(() => {
        result.current.sendMessage("hello");
        result.current.completeMessage();
      });
      expect(result.current.isStreaming).toBe(false);
    });
  });

  describe("message structure", () => {
    it("user message has correct structure", () => {
      const { result } = renderHook(() => useStreamingMessages());

      act(() => {
        result.current.sendMessage("test content");
      });

      const userMsg = result.current.messages[0] as UserMessage;
      expect(userMsg.id).toMatch(/^user-/);
      expect(userMsg.role).toBe("user");
      expect(userMsg.content).toBe("test content");
      expect(typeof userMsg.timestamp).toBe("string");
    });

    it("assistant message has correct structure", () => {
      const { result } = renderHook(() => useStreamingMessages());

      act(() => {
        result.current.sendMessage("test");
      });

      const assistantMsg = result.current.messages[1] as AssistantMessage;
      expect(assistantMsg.id).toMatch(/^assistant-/);
      expect(assistantMsg.role).toBe("assistant");
      expect(assistantMsg.parts).toHaveLength(1);
      expect(assistantMsg.parts[0].type).toBe("text");
      expect(typeof assistantMsg.timestamp).toBe("string");
    });

    it("text part has correct structure", () => {
      const { result } = renderHook(() => useStreamingMessages());

      act(() => {
        result.current.sendMessage("test");
        result.current.addDelta(" content");
      });

      const assistantMsg = result.current.messages[1] as AssistantMessage;
      const textPart = assistantMsg.parts[0] as { type: "text"; text: string; status: string; id: string };
      expect(textPart.type).toBe("text");
      expect(textPart.text).toBe(" content");
      expect(textPart.status).toBe("running");
      expect(textPart.id).toMatch(/^text-/);
    });
  });
});
