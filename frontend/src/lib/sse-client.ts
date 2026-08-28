"use client";

/**
 * SSE Client — REST fallback for WebSocket streaming.
 *
 * When the WebSocket connection is unavailable (or the ProtocolClient
 * queue is exhausted), this client hits the /api/prompt/sse endpoint
 * and consumes Server-Sent Events to render assistant deltas inline.
 *
 * The SSE stream uses the OpenAI-compatible chat.completion.chunk format,
 * identical to the Hermes Agent desktop GUI SSE stream:
 *
 *   data: {"id":"...","object":"chat.completion.chunk","created":...,"model":"...","choices":[{"index":0,"delta":{"role":"assistant"},"finish_reason":null}]}
 *   data: {"id":"...","object":"chat.completion.chunk","created":...,"model":"...","choices":[{"index":0,"delta":{"content":"hello"},"finish_reason":null}]}
 *   data: {"id":"...","object":"chat.completion.chunk","created":...,"model":"...","choices":[{"index":0,"delta":{},"finish_reason":"stop"}]}
 *   data: [DONE]
 *
 * Custom hermes.tool.progress events are emitted for tool lifecycle:
 *   event: hermes.tool.progress
 *   data: {"toolCallId":"...","toolName":"...","status":"...","input":{...}}
 *
 * Usage:
 *   const client = new SSEClient();
 *   client.on("assistant_delta", (delta: { text: string }) => { … });
 *   await client.sendPrompt({ prompt: "hello", sessionId: "abc123" });
 *   client.disconnect();
 */

export type SSEEventType =
  | "session_ready"
  | "assistant_delta"
  | "assistant_completed"
  | "tool_started"
  | "tool_delta"
  | "tool_completed"
  | "tool_permission_required"
  | "system_message"
  | "session_interrupted"
  | "session_failed"
  | "self_improvement_tick"
  | "resource_warning"
  | "model_switched"
  | "error";

export interface SSEEnvelope {
  session_id: string;
  event_type: SSEEventType;
  payload: Record<string, unknown>;
  seq?: number;
  protocol_version?: string;
}

export type SSEEventHandler = (envelope: SSEEnvelope) => void;

export interface SSESendOptions {
  prompt: string;
  sessionId: string;
  systemPrompt?: string;
  model?: string;
}

/** Parse an OpenAI-compatible chat.completion.chunk SSE frame. */
function parseChunk(
  data: unknown,
  sessionId: string,
): SSEEnvelope | null {
  if (typeof data !== "object" || data === null) return null;
  const obj = data as Record<string, unknown>;
  const object = obj.object;
  if (object !== "chat.completion.chunk") return null;

  const choices = obj.choices as unknown[] | undefined;
  if (!Array.isArray(choices) || choices.length === 0) return null;
  const choice = choices[0] as Record<string, unknown> | undefined;
  if (!choice) return null;

  const delta = choice.delta as Record<string, unknown> | undefined;
  const finishReason = choice.finish_reason as string | null | undefined;

  // Role chunk — skip (no user-facing event)
  if (delta?.role === "assistant") {
    return null;
  }

  // Error chunk
  if (finishReason === "error") {
    const error = obj.error as Record<string, unknown> | undefined;
    const hermes = obj.hermes as Record<string, unknown> | undefined;
    return {
      session_id: sessionId,
      event_type: "session_failed",
      payload: {
        error: error?.message ?? "Agent error",
        type: error?.type ?? "agent_error",
        completed: hermes?.completed,
        partial: hermes?.partial,
        failed: hermes?.failed,
        error_code: hermes?.error_code,
      },
    };
  }

  // Tool call delta
  const toolCalls = delta?.tool_calls as unknown[] | undefined;
  if (Array.isArray(toolCalls) && toolCalls.length > 0) {
    const tc = toolCalls[0] as Record<string, unknown>;
    const func = tc.function as Record<string, unknown> | undefined;
    const toolId = tc.id as string ?? "";
    const toolName = func?.name as string ?? "";
    const args = func?.arguments as string ?? "";

    // Parse the arguments — they may be a JSON string or a raw object
    let parsedArgs: Record<string, unknown> = {};
    try {
      parsedArgs = typeof args === "string" ? JSON.parse(args) : args;
    } catch {
      parsedArgs = { raw: args };
    }

    // Determine if this is a start or completion based on content
    const hasName = !!toolName;
    const hasArgs = !!args;

    if (hasName && !hasArgs) {
      // Tool started — name provided, no arguments yet
      return {
        session_id: sessionId,
        event_type: "tool_started",
        payload: {
          tool_id: toolId,
          tool_name: toolName,
          tool_input: {},
        },
      };
    } else if (hasArgs) {
      // Tool completed — arguments contain status/output
      return {
        session_id: sessionId,
        event_type: "tool_completed",
        payload: {
          tool_id: toolId,
          status: parsedArgs.status ?? "success",
          output: parsedArgs.output ?? "",
        },
      };
    }
  }

  // Content delta
  const content = delta?.content as string | undefined;
  if (content) {
    return {
      session_id: sessionId,
      event_type: "assistant_delta",
      payload: { text: content },
    };
  }

  // Finish chunk (finish_reason is set, no content/tool_calls)
  if (finishReason) {
    return {
      session_id: sessionId,
      event_type: "assistant_completed",
      payload: { stop_reason: finishReason },
    };
  }

  return null;
}

/** Parse a hermes.tool.progress custom event. */
function parseToolProgress(data: unknown, sessionId: string): SSEEnvelope | null {
  if (typeof data !== "object" || data === null) return null;
  const obj = data as Record<string, unknown>;
  const status = obj.status as string | undefined;
  const toolCallId = obj.toolCallId as string | undefined;
  const toolName = obj.toolName as string | undefined;

  if (!status) return null;

  if (status === "permission_required") {
    return {
      session_id: sessionId,
      event_type: "tool_permission_required",
      payload: {
        tool_id: toolCallId ?? "",
        tool_name: toolName ?? "",
        tool_input: obj.input ?? {},
      },
    };
  }

  // Other progress events (loop_safety_warning, resource_warning)
  if (obj.state !== undefined) {
    return {
      session_id: sessionId,
      event_type: "self_improvement_tick",
      payload: {
        state: obj.state,
        details: obj.details ?? {},
      },
    };
  }

  if (obj.resource !== undefined) {
    return {
      session_id: sessionId,
      event_type: "resource_warning",
      payload: {
        resource: obj.resource,
        current: obj.current ?? 0,
        threshold: obj.threshold ?? 0,
        message: obj.message ?? "",
      },
    };
  }

  return null;
}

export class SSEClient {
  private _abortController: AbortController | null = null;
  private handlers = new Map<string, Set<SSEEventHandler>>();
  private errorHandlers: Array<(error: Error) => void> = [];

  on(eventType: string | "*", handler: SSEEventHandler): void {
    const key = eventType === "*" ? "*" : eventType;
    if (!this.handlers.has(key)) this.handlers.set(key, new Set());
    this.handlers.get(key)!.add(handler);
  }

  off(eventType: string | "*", handler: SSEEventHandler): void {
    const key = eventType === "*" ? "*" : eventType;
    this.handlers.get(key)?.delete(handler);
  }

  onError(handler: (error: Error) => void): void {
    this.errorHandlers.push(handler);
  }

  offError(handler: (error: Error) => void): void {
    const i = this.errorHandlers.indexOf(handler);
    if (i >= 0) this.errorHandlers.splice(i, 1);
  }

  /** Send a prompt via REST SSE and stream events until completion. */
  async sendPrompt(opts: SSESendOptions): Promise<void> {
    this._abortController = new AbortController();
    const signal = this._abortController.signal;

    const body: Record<string, string | undefined> = {
      prompt: opts.prompt,
      session_id: opts.sessionId,
      system_prompt: opts.systemPrompt,
      model: opts.model,
    };

    // Build query string for model override if provided
    const url = new URL("/api/prompt/sse", window.location.origin);
    if (opts.model) {
      url.searchParams.set("model", opts.model);
    }

    try {
      const response = await fetch(url.toString(), {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
        signal,
      });

      if (!response.ok) {
        const errText = await response.text().catch(() => "unknown error");
        throw new Error(`SSE request failed: ${response.status} ${errText}`);
      }

      if (!response.body) {
        throw new Error("SSE response has no body");
      }

      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";
      let pendingEventType: string | null = null;

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split("\n");
        // Keep the last line in buffer (may be incomplete)
        buffer = lines.pop() ?? "";

        for (const line of lines) {
          const trimmed = line.trim();
          if (trimmed === "" || trimmed.startsWith(":")) continue;

          if (trimmed.startsWith("event:")) {
            // Custom event type (e.g., hermes.tool.progress)
            pendingEventType = trimmed.slice(6).trim();
          } else if (trimmed.startsWith("data:")) {
            const eventData = trimmed.slice(5).trim();

            // [DONE] marker
            if (eventData === "[DONE]") {
              break;
            }

            let envelope: SSEEnvelope | null = null;

            if (pendingEventType === "hermes.tool.progress") {
              // Custom Hermes tool progress event
              try {
                const parsed = JSON.parse(eventData);
                envelope = parseToolProgress(parsed, opts.sessionId);
              } catch {
                // Not JSON — skip
              }
            } else {
              // Standard chat.completion.chunk
              try {
                const parsed = JSON.parse(eventData);
                envelope = parseChunk(parsed, opts.sessionId);
              } catch {
                // Not JSON — treat as raw text delta
                envelope = {
                  session_id: opts.sessionId,
                  event_type: "assistant_delta",
                  payload: { text: eventData },
                };
              }
            }

            if (envelope) {
              this._emit(envelope);
            }

            pendingEventType = null;
          }
        }
      }
    } catch (err) {
      if (err instanceof Error && (err.name === "AbortError" || signal.aborted)) {
        return; // Clean disconnect
      }
      this.errorHandlers.forEach((h) => {
        try {
          h(err instanceof Error ? err : new Error(String(err)));
        } catch (_) {}
      });
    } finally {
      this._abortController = null;
    }
  }

  /** Abort an in-flight SSE stream. */
  disconnect(): void {
    if (this._abortController) {
      this._abortController.abort();
      this._abortController = null;
    }
  }

  /** Get current connection state. */
  isConnected(): boolean {
    return this._abortController !== null;
  }

  private _emit(envelope: SSEEnvelope): void {
    const specific = this.handlers.get(envelope.event_type);
    if (specific) {
      specific.forEach((h) => {
        try {
          h(envelope);
        } catch (e) {
          console.error("SSE handler threw", e);
        }
      });
    }
    const wildcard = this.handlers.get("*");
    if (wildcard) {
      wildcard.forEach((h) => {
        try {
          h(envelope);
        } catch (e) {
          console.error("SSE wildcard handler threw", e);
        }
      });
    }
  }
}
