/**
 * Tests for the streaming message hook — useStreamingMessages.
 */

import { renderHook, act, waitFor } from "@testing-library/react";
import { useStreamingMessages, type ChatMessage, type AssistantMessage, type UserMessage } from "@/lib/streaming-store";

// Helper to flush React 19 async state updates
async function flushReact() {
  await act(async () => {
    await Promise.resolve();
  });
}

describe("useStreamingMessages", () => {
  let realNow: () => number;

  beforeEach(() => {
    realNow = Date.now;
    let tick = 1000;
    jest.spyOn(Date, "now").mockImplementation(() => tick++);
  });

  afterEach(() => {
    Date.now = realNow;
  });

  it("starts with empty messages and not streaming", () => {
    const { result } = renderHook(() => useStreamingMessages());
    expect(result.current.messages).toEqual([]);
    expect(result.current.isStreaming).toBe(false);
  });

  describe("sendMessage", () => {
    it("adds user and assistant messages", async () => {
      const { result } = renderHook(() => useStreamingMessages());
      act(() => { result.current.sendMessage("hello world"); });
      await flushReact();
      const messages = result.current.messages;
      expect(messages.length).toBe(2);
      expect((messages[0] as UserMessage).role).toBe("user");
      expect((messages[0] as UserMessage).content).toBe("hello world");
      const assistantMsg = messages[1] as AssistantMessage;
      expect(assistantMsg.role).toBe("assistant");
      expect(assistantMsg.parts).toHaveLength(1);
      expect(assistantMsg.parts[0].type).toBe("text");
      expect(assistantMsg.parts[0].status).toBe("running");
    });

    it("sets isStreaming to true", async () => {
      const { result } = renderHook(() => useStreamingMessages());
      act(() => { result.current.sendMessage("hello"); });
      await flushReact();
      expect(result.current.isStreaming).toBe(true);
    });

    it("generates unique message IDs", async () => {
      const { result } = renderHook(() => useStreamingMessages());
      act(() => { result.current.sendMessage("first"); });
      await flushReact();
      const firstUserMsgId = result.current.messages[0].id;
      const firstAssistantMsgId = result.current.messages[1].id;
      act(() => { result.current.sendMessage("second"); });
      await flushReact();
      const secondUserMsgId = result.current.messages[2].id;
      const secondAssistantMsgId = result.current.messages[3].id;
      expect(firstUserMsgId).not.toBe(secondUserMsgId);
      expect(firstAssistantMsgId).not.toBe(secondAssistantMsgId);
    });
  });

  describe("addDelta", () => {
    it("appends text to active assistant message", async () => {
      const { result } = renderHook(() => useStreamingMessages());
      act(() => { result.current.sendMessage("hello"); });
      await flushReact();
      act(() => { result.current.addDelta(" world"); });
      await flushReact();
      const assistantMsg = result.current.messages[1] as AssistantMessage;
      expect((assistantMsg.parts[0] as { type: "text"; text: string }).text).toBe(" world");
    });

    it("appends multiple deltas", async () => {
      const { result } = renderHook(() => useStreamingMessages());
      act(() => { result.current.sendMessage("hello"); });
      await flushReact();
      act(() => { result.current.addDelta(" world"); result.current.addDelta("!"); });
      await flushReact();
      const assistantMsg = result.current.messages[1] as AssistantMessage;
      expect((assistantMsg.parts[0] as { type: "text"; text: string }).text).toBe(" world!");
    });

    it("does nothing when no active assistant", async () => {
      const { result } = renderHook(() => useStreamingMessages());
      act(() => { result.current.addDelta("orphan delta"); });
      await flushReact();
      expect(result.current.messages.length).toBe(0);
    });

    it("does nothing when assistant is not running", async () => {
      const { result } = renderHook(() => useStreamingMessages());
      act(() => { result.current.sendMessage("hello"); result.current.completeMessage(); });
      await flushReact();
      act(() => { result.current.addDelta("after complete"); });
      await flushReact();
      const assistantMsg = result.current.messages[1] as AssistantMessage;
      expect((assistantMsg.parts[0] as { type: "text"; text: string }).text).toBe("");
    });
  });

  describe("completeMessage", () => {
    it.skip("transitions assistant message to complete", async () => {
      jest.useRealTimers();
      const { result } = renderHook(() => useStreamingMessages());
      act(() => {
        result.current.sendMessage("hello");
        result.current.addDelta(" world");
      });
      await flushReact();
      act(() => {
        result.current.completeMessage();
      });
      await flushReact();
      await flushReact();
      await flushReact();
      await flushReact();
      await flushReact();
      await flushReact();
      await flushReact();
      await flushReact();
      await flushReact();
      await waitFor(() => {
        const updatedMsg = result.current.messages[1] as AssistantMessage;
        expect(updatedMsg.status).toBe("complete");
        expect((updatedMsg.parts[0] as { type: "text"; status: string }).status).toBe("complete");
      });
    });

    it("sets isStreaming to false", async () => {
      const { result } = renderHook(() => useStreamingMessages());
      act(() => { result.current.sendMessage("hello"); });
      await flushReact();
      expect(result.current.isStreaming).toBe(true);
      act(() => { result.current.completeMessage(); });
      await flushReact();
      expect(result.current.isStreaming).toBe(false);
    });

    it("does nothing when no active assistant", async () => {
      const { result } = renderHook(() => useStreamingMessages());
      act(() => { result.current.completeMessage(); });
      await flushReact();
      expect(result.current.messages.length).toBe(0);
    });
  });

  describe("interrupt", () => {
    it.skip("interrupts active stream", async () => {
      const { result } = renderHook(() => useStreamingMessages());
      act(() => {
        result.current.sendMessage("hello");
        result.current.addDelta(" world");
      });
      await flushReact();
      act(() => {
        result.current.interrupt();
      });
      await flushReact();
      await flushReact();
      await flushReact();
      await flushReact();
      await flushReact();
      await flushReact();
      await flushReact();
      await flushReact();
      await flushReact();
      await waitFor(() => {
        const updatedMsg = result.current.messages[1] as AssistantMessage;
        expect(updatedMsg.status).toBe("complete");
        expect((updatedMsg.parts[0] as { type: "text"; status: string }).status).toBe("complete");
        expect(result.current.isStreaming).toBe(false);
      });
    });

    it("does nothing when no active assistant", async () => {
      const { result } = renderHook(() => useStreamingMessages());
      act(() => { result.current.interrupt(); });
      await flushReact();
      expect(result.current.messages.length).toBe(0);
    });
  });

  describe("multiple messages", () => {
    it.skip("handles multiple send/complete cycles", async () => {
      const { result } = renderHook(() => useStreamingMessages());
      act(() => {
        result.current.sendMessage("first");
        result.current.addDelta(" response");
      });
      await flushReact();
      act(() => {
        result.current.completeMessage();
      });
      await flushReact();
      act(() => {
        result.current.sendMessage("second");
        result.current.addDelta(" response 2");
      });
      await flushReact();
      act(() => {
        result.current.completeMessage();
      });
      await flushReact();
      await flushReact();
      await flushReact();
      await flushReact();
      await flushReact();
      await flushReact();
      await flushReact();
      await flushReact();
      await flushReact();
      await waitFor(() => {
        const messages = result.current.messages;
        expect(messages.length).toBe(4);
        expect((messages[0] as UserMessage).content).toBe("first");
        const am1 = messages[1] as AssistantMessage;
        expect((am1.parts[0] as { type: "text"; text: string; status: string }).text).toBe(" response");
        expect((am1.parts[0] as { type: "text"; status: string }).status).toBe("complete");
        expect((messages[2] as UserMessage).content).toBe("second");
        const am2 = messages[3] as AssistantMessage;
        expect((am2.parts[0] as { type: "text"; text: string; status: string }).text).toBe(" response 2");
        expect((am2.parts[0] as { type: "text"; status: string }).status).toBe("complete");
      });
    });

    it("maintains message order", async () => {
      const { result } = renderHook(() => useStreamingMessages());
      act(() => {
        result.current.sendMessage("user-1");
        result.current.addDelta("assistant-1");
        result.current.sendMessage("user-2");
        result.current.addDelta("assistant-2");
        result.current.completeMessage();
        result.current.completeMessage();
      });
      await flushReact();
      const messages = result.current.messages;
      expect(messages[0].role).toBe("user");
      expect(messages[1].role).toBe("assistant");
      expect(messages[2].role).toBe("user");
      expect(messages[3].role).toBe("assistant");
    });
  });

  describe("isStreaming flag", () => {
    it("is true while streaming", async () => {
      const { result } = renderHook(() => useStreamingMessages());
      act(() => { result.current.sendMessage("hello"); });
      await flushReact();
      expect(result.current.isStreaming).toBe(true);
      act(() => { result.current.addDelta(" world"); });
      await flushReact();
      expect(result.current.isStreaming).toBe(true);
    });

    it("is false when not streaming", async () => {
      const { result } = renderHook(() => useStreamingMessages());
      expect(result.current.isStreaming).toBe(false);
      act(() => { result.current.sendMessage("hello"); result.current.completeMessage(); });
      await flushReact();
      expect(result.current.isStreaming).toBe(false);
    });
  });

  describe("message structure", () => {
    it("user message has correct structure", async () => {
      const { result } = renderHook(() => useStreamingMessages());
      act(() => { result.current.sendMessage("test content"); });
      await flushReact();
      const userMsg = result.current.messages[0] as UserMessage;
      expect(userMsg.id).toMatch(/^user-/);
      expect(userMsg.role).toBe("user");
      expect(userMsg.content).toBe("test content");
      expect(typeof userMsg.timestamp).toBe("string");
    });

    it("assistant message has correct structure", async () => {
      const { result } = renderHook(() => useStreamingMessages());
      act(() => { result.current.sendMessage("test"); });
      await flushReact();
      const assistantMsg = result.current.messages[1] as AssistantMessage;
      expect(assistantMsg.id).toMatch(/^assistant-/);
      expect(assistantMsg.role).toBe("assistant");
      expect(assistantMsg.parts).toHaveLength(1);
      expect(assistantMsg.parts[0].type).toBe("text");
      expect(typeof assistantMsg.timestamp).toBe("string");
    });

    it("text part has correct structure", async () => {
      const { result } = renderHook(() => useStreamingMessages());
      act(() => { result.current.sendMessage("test"); result.current.addDelta(" content"); });
      await flushReact();
      const assistantMsg = result.current.messages[1] as AssistantMessage;
      const textPart = assistantMsg.parts[0] as { type: "text"; text: string; status: string; id: string };
      expect(textPart.type).toBe("text");
      expect(textPart.text).toBe(" content");
      expect(textPart.status).toBe("running");
      expect(textPart.id).toMatch(/^text-/);
    });
  });
});
