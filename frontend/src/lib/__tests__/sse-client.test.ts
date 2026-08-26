/**
 * Tests for SSEClient — event handling, error paths, disconnect.
 */

import { SSEClient, type SSEEnvelope } from "@/lib/sse-client";

// Mock fetch globally
const mockFetch = jest.fn();
global.fetch = mockFetch;

// Mock TextDecoder
class MockTextDecoder {
  decode(data: Uint8Array, options?: { stream?: boolean }): string {
    return new TextDecoder().decode(data, options);
  }
}
global.TextDecoder = MockTextDecoder as any;

// Mock AbortController
class MockAbortController {
  signal: any = {};
  abort() {}
}
global.AbortController = MockAbortController as any;

describe("SSEClient", () => {
  let client: SSEClient;

  beforeEach(() => {
    jest.clearAllMocks();
    client = new SSEClient();
  });

  describe("event handling", () => {
    it("registers and emits event handlers", async () => {
      const handler = jest.fn();
      client.on("assistant_delta", handler);

      mockFetch.mockResolvedValueOnce({
        ok: true,
        body: {
          getReader: () => ({
            read: jest.fn()
              .mockResolvedValueOnce({ done: false, value: new TextEncoder().encode("data: {\"session_id\":\"s1\",\"event_type\":\"assistant_delta\",\"payload\":{\"text\":\"hello\"}}\n\n") })
              .mockResolvedValueOnce({ done: true, value: undefined }),
          }),
        },
      });

      await client.sendPrompt({ prompt: "hi", sessionId: "s1" });
      expect(handler).toHaveBeenCalledWith(
        expect.objectContaining({
          session_id: "s1",
          event_type: "assistant_delta",
          payload: { text: "hello" },
        })
      );
    });

    it("emits to wildcard handler", async () => {
      const wildcardHandler = jest.fn();
      client.on("*", wildcardHandler);

      mockFetch.mockResolvedValueOnce({
        ok: true,
        body: {
          getReader: () => ({
            read: jest.fn()
              .mockResolvedValueOnce({ done: false, value: new TextEncoder().encode("data: {\"session_id\":\"s1\",\"event_type\":\"tool_started\",\"payload\":{\"tool\":\"read_file\"}}\n\n") })
              .mockResolvedValueOnce({ done: true, value: undefined }),
          }),
        },
      });

      await client.sendPrompt({ prompt: "hi", sessionId: "s1" });
      expect(wildcardHandler).toHaveBeenCalledWith(
        expect.objectContaining({
          event_type: "tool_started",
        })
      );
    });

    it("emits to both specific and wildcard handlers", async () => {
      const specificHandler = jest.fn();
      const wildcardHandler = jest.fn();
      client.on("assistant_delta", specificHandler);
      client.on("*", wildcardHandler);

      mockFetch.mockResolvedValueOnce({
        ok: true,
        body: {
          getReader: () => ({
            read: jest.fn()
              .mockResolvedValueOnce({ done: false, value: new TextEncoder().encode("data: {\"session_id\":\"s1\",\"event_type\":\"assistant_delta\",\"payload\":{\"text\":\"test\"}}\n\n") })
              .mockResolvedValueOnce({ done: true, value: undefined }),
          }),
        },
      });

      await client.sendPrompt({ prompt: "hi", sessionId: "s1" });
      expect(specificHandler).toHaveBeenCalled();
      expect(wildcardHandler).toHaveBeenCalled();
    });

    it("handles non-JSON data as raw delta", async () => {
      const handler = jest.fn();
      client.on("assistant_delta", handler);

      mockFetch.mockResolvedValueOnce({
        ok: true,
        body: {
          getReader: () => ({
            read: jest.fn()
              .mockResolvedValueOnce({ done: false, value: new TextEncoder().encode("data: raw text delta\n\n") })
              .mockResolvedValueOnce({ done: true, value: undefined }),
          }),
        },
      });

      await client.sendPrompt({ prompt: "hi", sessionId: "s1" });
      expect(handler).toHaveBeenCalledWith(
        expect.objectContaining({
          event_type: "assistant_delta",
          payload: { text: "raw text delta" },
        })
      );
    });

    it("skips empty lines and comment lines", async () => {
      const handler = jest.fn();
      client.on("assistant_delta", handler);

      mockFetch.mockResolvedValueOnce({
        ok: true,
        body: {
          getReader: () => ({
            read: jest.fn()
              .mockResolvedValueOnce({ done: false, value: new TextEncoder().encode(": comment\ndata: {\"session_id\":\"s1\",\"event_type\":\"assistant_delta\",\"payload\":{\"text\":\"x\"}}\n\n") })
              .mockResolvedValueOnce({ done: true, value: undefined }),
          }),
        },
      });

      await client.sendPrompt({ prompt: "hi", sessionId: "s1" });
      expect(handler).toHaveBeenCalled();
    });

    it("handles multiple events in one read", async () => {
      const handler = jest.fn();
      client.on("assistant_delta", handler);

      mockFetch.mockResolvedValueOnce({
        ok: true,
        body: {
          getReader: () => ({
            read: jest.fn()
              .mockResolvedValueOnce({ done: false, value: new TextEncoder().encode("data: {\"session_id\":\"s1\",\"event_type\":\"assistant_delta\",\"payload\":{\"text\":\"a\"}}\n\ndata: {\"session_id\":\"s1\",\"event_type\":\"assistant_delta\",\"payload\":{\"text\":\"b\"}}\n\n") })
              .mockResolvedValueOnce({ done: true, value: undefined }),
          }),
        },
      });

      await client.sendPrompt({ prompt: "hi", sessionId: "s1" });
      expect(handler).toHaveBeenCalledTimes(2);
    });
  });

  describe("error handling", () => {
    it("throws on non-OK response", async () => {
      mockFetch.mockResolvedValueOnce({
        ok: false,
        status: 500,
        text: () => Promise.resolve("Internal Server Error"),
      });

      await expect(
        client.sendPrompt({ prompt: "hi", sessionId: "s1" })
      ).rejects.toThrow("SSE request failed: 500 Internal Server Error");
    });

    it("throws when response has no body", async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        body: null,
      });

      await expect(
        client.sendPrompt({ prompt: "hi", sessionId: "s1" })
      ).rejects.toThrow("SSE response has no body");
    });

    it("calls error handlers on fetch error", async () => {
      const errorHandler = jest.fn();
      client.onError(errorHandler);

      mockFetch.mockRejectedValueOnce(new Error("Network error"));

      await client.sendPrompt({ prompt: "hi", sessionId: "s1" });
      expect(errorHandler).toHaveBeenCalledWith(expect.any(Error));
    });

    it("handles handler throwing without crashing", async () => {
      const consoleSpy = jest.spyOn(console, "error").mockImplementation(() => {});
      const badHandler = jest.fn(() => { throw new Error("handler error"); });
      client.on("assistant_delta", badHandler);

      mockFetch.mockResolvedValueOnce({
        ok: true,
        body: {
          getReader: () => ({
            read: jest.fn()
              .mockResolvedValueOnce({ done: false, value: new TextEncoder().encode("data: {\"session_id\":\"s1\",\"event_type\":\"assistant_delta\",\"payload\":{\"text\":\"x\"}}\n\n") })
              .mockResolvedValueOnce({ done: true, value: undefined }),
          }),
        },
      });

      await client.sendPrompt({ prompt: "hi", sessionId: "s1" });
      expect(consoleSpy).toHaveBeenCalledWith("SSE handler threw", expect.any(Error));
      consoleSpy.mockRestore();
    });

    it("handles wildcard handler throwing without crashing", async () => {
      const consoleSpy = jest.spyOn(console, "error").mockImplementation(() => {});
      const badHandler = jest.fn(() => { throw new Error("wildcard handler error"); });
      client.on("*", badHandler);

      mockFetch.mockResolvedValueOnce({
        ok: true,
        body: {
          getReader: () => ({
            read: jest.fn()
              .mockResolvedValueOnce({ done: false, value: new TextEncoder().encode("data: {\"session_id\":\"s1\",\"event_type\":\"assistant_delta\",\"payload\":{\"text\":\"x\"}}\n\n") })
              .mockResolvedValueOnce({ done: true, value: undefined }),
          }),
        },
      });

      await client.sendPrompt({ prompt: "hi", sessionId: "s1" });
      expect(consoleSpy).toHaveBeenCalledWith("SSE wildcard handler threw", expect.any(Error));
      consoleSpy.mockRestore();
    });
  });

  describe("disconnect and state", () => {
    it("disconnects by aborting", () => {
      const abortSpy = jest.fn();
      (global.AbortController as any).mockImplementation(() => ({
        signal: {},
        abort: abortSpy,
      }));

      client.disconnect();
      expect(abortSpy).toHaveBeenCalled();
    });

    it("isConnected returns true when active", () => {
      expect(client.isConnected()).toBe(false);
    });

    it("removes specific event handler", () => {
      const handler = jest.fn();
      client.on("assistant_delta", handler);
      client.off("assistant_delta", handler);
      // No handler should be registered
      expect(client["handlers"].get("assistant_delta")).toBeUndefined();
    });

    it("removes wildcard handler", () => {
      const handler = jest.fn();
      client.on("*", handler);
      client.off("*", handler);
      expect(client["handlers"].get("*")).toBeUndefined();
    });

    it("removes error handler", () => {
      const errorHandler = jest.fn();
      client.onError(errorHandler);
      client.offError(errorHandler);
      expect(client["errorHandlers"]).toEqual([]);
    });

    it("includes model in query params", async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        body: {
          getReader: () => ({
            read: jest.fn().mockResolvedValueOnce({ done: true, value: undefined }),
          }),
        },
      });

      await client.sendPrompt({ prompt: "hi", sessionId: "s1", model: "test-model" });
      expect(mockFetch).toHaveBeenCalledWith(
        expect.stringContaining("model=test-model"),
        expect.any(Object)
      );
    });

    it("includes system_prompt in body", async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        body: {
          getReader: () => ({
            read: jest.fn().mockResolvedValueOnce({ done: true, value: undefined }),
          }),
        },
      });

      await client.sendPrompt({ prompt: "hi", sessionId: "s1", systemPrompt: "custom system" });
      const callArgs = mockFetch.mock.calls[0];
      const body = JSON.parse(callArgs[1].body);
      expect(body.system_prompt).toBe("custom system");
    });

    it("handles AbortError silently", async () => {
      const errorHandler = jest.fn();
      client.onError(errorHandler);

      const abortError = new Error("aborted");
      abortError.name = "AbortError";
      mockFetch.mockRejectedValueOnce(abortError);

      await client.sendPrompt({ prompt: "hi", sessionId: "s1" });
      expect(errorHandler).not.toHaveBeenCalled();
    });

    it("uses session_id from opts when not in payload", async () => {
      const handler = jest.fn();
      client.on("assistant_delta", handler);

      mockFetch.mockResolvedValueOnce({
        ok: true,
        body: {
          getReader: () => ({
            read: jest.fn()
              .mockResolvedValueOnce({ done: false, value: new TextEncoder().encode("data: {\"event_type\":\"assistant_delta\",\"payload\":{\"text\":\"x\"}}\n\n") })
              .mockResolvedValueOnce({ done: true, value: undefined }),
          }),
        },
      });

      await client.sendPrompt({ prompt: "hi", sessionId: "fallback-session" });
      expect(handler).toHaveBeenCalledWith(
        expect.objectContaining({
          session_id: "fallback-session",
        })
      );
    });

    it("parses seq and protocol_version from envelope", async () => {
      const handler = jest.fn();
      client.on("assistant_delta", handler);

      mockFetch.mockResolvedValueOnce({
        ok: true,
        body: {
          getReader: () => ({
            read: jest.fn()
              .mockResolvedValueOnce({ done: false, value: new TextEncoder().encode("data: {\"session_id\":\"s1\",\"event_type\":\"assistant_delta\",\"payload\":{\"text\":\"x\"},\"seq\":42,\"protocol_version\":\"1.0\"}\n\n") })
              .mockResolvedValueOnce({ done: true, value: undefined }),
          }),
        },
      });

      await client.sendPrompt({ prompt: "hi", sessionId: "s1" });
      expect(handler).toHaveBeenCalledWith(
        expect.objectContaining({
          seq: 42,
          protocol_version: "1.0",
        })
      );
    });
  });
});
