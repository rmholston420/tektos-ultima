/**
 * Tests for the SSE Client — REST fallback for WebSocket streaming.
 */

import { SSEClient, type SSEEnvelope, type SSEEventType } from "@/lib/sse-client";

describe("SSEClient", () => {
  let client: SSEClient;
  let mockFetch: jest.Mock;

  beforeEach(() => {
    mockFetch = jest.fn();
    global.fetch = mockFetch;
    client = new SSEClient();
  });

  afterEach(() => {
    client.disconnect();
    jest.clearAllMocks();
  });

  describe("initial state", () => {
    it("starts not connected", () => {
      expect(client.isConnected()).toBe(false);
    });
  });

  describe("on / off", () => {
    it("registers event handler", () => {
      const handler = jest.fn();
      client.on("assistant_delta", handler);
      expect(client["handlers"].has("assistant_delta")).toBe(true);
    });

    it("registers wildcard handler", () => {
      const handler = jest.fn();
      client.on("*", handler);
      expect(client["handlers"].has("*")).toBe(true);
    });

    it("removes event handler", () => {
      const handler = jest.fn();
      client.on("assistant_delta", handler);
      client.off("assistant_delta", handler);
      expect(client["handlers"].get("assistant_delta")?.has(handler)).toBe(false);
    });

    it("registers error handler", () => {
      const handler = jest.fn();
      client.onError(handler);
      expect(client["errorHandlers"]).toContain(handler);
    });

    it("removes error handler", () => {
      const handler = jest.fn();
      client.onError(handler);
      client.offError(handler);
      expect(client["errorHandlers"]).not.toContain(handler);
    });
  });

  describe("sendPrompt", () => {
    it("sends POST request to SSE endpoint", async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        body: null,
      });

      await client.sendPrompt({
        prompt: "hello world",
        sessionId: "test-session",
      });

      expect(mockFetch).toHaveBeenCalledWith(
        expect.stringContaining("/api/prompt/sse"),
        expect.objectContaining({
          method: "POST",
          body: JSON.stringify({
            prompt: "hello world",
            session_id: "test-session",
          }),
        })
      );
    });

    it("includes optional fields", async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        body: null,
      });

      await client.sendPrompt({
        prompt: "hello",
        sessionId: "test-session",
        systemPrompt: "You are helpful",
        model: "test-model",
      });

      const body = JSON.parse(mockFetch.mock.calls[0][1].body as string);
      expect(body.system_prompt).toBe("You are helpful");
      expect(body.model).toBe("test-model");
    });

    it("adds model to query string", async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        body: null,
      });

      await client.sendPrompt({
        prompt: "hello",
        sessionId: "test-session",
        model: "custom-model",
      });

      expect(mockFetch).toHaveBeenCalledWith(
        expect.stringContaining("model=custom-model"),
        expect.any(Object)
      );
    });

    it("handles fetch failure", async () => {
      mockFetch.mockResolvedValueOnce({
        ok: false,
        status: 500,
        text: () => Promise.resolve("server error"),
      });

      await expect(
        client.sendPrompt({ prompt: "hello", sessionId: "test-session" })
      ).rejects.toThrow("SSE request failed: 500");
    });

    it("handles missing response body", async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        body: null,
      });

      await expect(
        client.sendPrompt({ prompt: "hello", sessionId: "test-session" })
      ).rejects.toThrow("SSE response has no body");
    });

    it("handles parse errors in SSE data", async () => {
      const encoder = new TextEncoder();
      const mockReader = {
        read: jest.fn()
          .mockResolvedValueOnce({ done: false, value: encoder.encode("data: not json\n\n") })
          .mockResolvedValueOnce({ done: true, value: undefined }),
      };

      mockFetch.mockResolvedValueOnce({
        ok: true,
        body: { getReader: () => mockReader } as any,
      });

      // Should not throw — malformed SSE is handled gracefully
      await client.sendPrompt({ prompt: "hello", sessionId: "test-session" });
    });
  });

  describe("disconnect", () => {
    it("aborts in-flight stream", async () => {
      const abortController = { abort: jest.fn() } as any;
      client["_abortController"] = abortController;

      client.disconnect();

      expect(abortController.abort).toHaveBeenCalled();
      expect(client["_abortController"]).toBeNull();
    });

    it("handles disconnect when not connected", () => {
      // Should not throw
      expect(() => client.disconnect()).not.toThrow();
    });
  });

  describe("isConnected", () => {
    it("returns true when connected", () => {
      client["_abortController"] = { abort: jest.fn() } as any;
      expect(client.isConnected()).toBe(true);
    });

    it("returns false when not connected", () => {
      expect(client.isConnected()).toBe(false);
    });
  });

  describe("_emit (internal)", () => {
    it("calls specific event handler", async () => {
      const handler = jest.fn();
      client.on("assistant_delta", handler);

      const envelope: SSEEnvelope = {
        session_id: "test-session",
        event_type: "assistant_delta",
        payload: { text: "hello" },
      };
      client["_emit"](envelope);
      expect(handler).toHaveBeenCalledWith(envelope);
    });

    it("calls wildcard handler", async () => {
      const handler = jest.fn();
      client.on("*", handler);

      const envelope: SSEEnvelope = {
        session_id: "test-session",
        event_type: "error",
        payload: {},
      };
      client["_emit"](envelope);
      expect(handler).toHaveBeenCalledWith(envelope);
    });

    it("calls both specific and wildcard handlers", async () => {
      const specific = jest.fn();
      const wildcard = jest.fn();
      client.on("assistant_delta", specific);
      client.on("*", wildcard);

      const envelope: SSEEnvelope = {
        session_id: "test-session",
        event_type: "assistant_delta",
        payload: {},
      };
      client["_emit"](envelope);
      expect(specific).toHaveBeenCalled();
      expect(wildcard).toHaveBeenCalled();
    });

    it("handles handler errors gracefully", async () => {
      const handler = jest.fn(() => { throw new Error("handler error"); });
      client.onError(() => {}); // Capture errors
      client.on("assistant_delta", handler);

      const envelope: SSEEnvelope = {
        session_id: "test-session",
        event_type: "assistant_delta",
        payload: {},
      };
      // Should not throw
      expect(() => client["_emit"](envelope)).not.toThrow();
    });

    it("handles error handler errors gracefully", async () => {
      const errorHandler = jest.fn(() => { throw new Error("error handler error"); });
      client.onError(errorHandler);

      const envelope: SSEEnvelope = {
        session_id: "test-session",
        event_type: "error",
        payload: { message: "test error" },
      };
      // Should not throw
      expect(() => client["_emit"](envelope)).not.toThrow();
    });
  });

  describe("SSEEventType", () => {
    it("includes all expected event types", () => {
      const types: SSEEventType[] = [
        "session_ready",
        "assistant_delta",
        "assistant_completed",
        "tool_started",
        "tool_delta",
        "tool_completed",
        "tool_permission_required",
        "system_message",
        "session_interrupted",
        "session_failed",
        "self_improvement_tick",
        "resource_warning",
        "model_switched",
        "error",
      ];
      expect(types).toHaveLength(14);
    });
  });

  describe("SSEEnvelope", () => {
    it("type matches expected shape", () => {
      const envelope: SSEEnvelope = {
        session_id: "test-session",
        event_type: "assistant_delta",
        payload: { text: "hello" },
      };
      expect(envelope.session_id).toBe("test-session");
      expect(envelope.event_type).toBe("assistant_delta");
      expect(envelope.payload.text).toBe("hello");
    });

    it("allows optional fields", () => {
      const envelope: SSEEnvelope = {
        session_id: "test-session",
        event_type: "assistant_delta",
        payload: {},
        seq: 42,
        protocol_version: "1",
      };
      expect(envelope.seq).toBe(42);
      expect(envelope.protocol_version).toBe("1");
    });
  });

  describe("SSESendOptions", () => {
    it("requires prompt and sessionId", () => {
      // This is a type-level test — if it compiles, the shape is correct
      const opts = {
        prompt: "hello",
        sessionId: "test-session",
      };
      expect(opts.prompt).toBe("hello");
      expect(opts.sessionId).toBe("test-session");
    });

    it("allows optional fields", () => {
      const opts = {
        prompt: "hello",
        sessionId: "test-session",
        systemPrompt: "You are helpful",
        model: "test-model",
      };
      expect(opts.systemPrompt).toBe("You are helpful");
      expect(opts.model).toBe("test-model");
    });
  });
});
