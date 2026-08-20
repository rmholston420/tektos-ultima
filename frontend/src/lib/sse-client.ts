"use client";

/**
 * SSE Client — REST fallback for WebSocket streaming.
 *
 * When the WebSocket connection is unavailable (or the ProtocolClient
 * queue is exhausted), this client hits the /api/prompt/sse endpoint
 * and consumes Server-Sent Events to render assistant deltas inline.
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
            // Next data line follows immediately
          } else if (trimmed.startsWith("data:")) {
            const eventData = trimmed.slice(5).trim();
            let eventType = "system_message";
            // Peek at next non-empty line for event type
            // (We handle this in the next iteration, but for simplicity
            //  we parse the full SSE block below)
            try {
              const parsed = JSON.parse(eventData);
              // event_type field is in the JSON envelope
              const envelope: SSEEnvelope = {
                session_id: parsed.session_id ?? opts.sessionId,
                event_type: (parsed.event_type ?? "system_message") as SSEEventType,
                payload: parsed.payload ?? parsed,
                seq: parsed.seq,
                protocol_version: parsed.protocol_version,
              };
              this._emit(envelope);
            } catch {
              // Not JSON — treat as raw text delta
              const envelope: SSEEnvelope = {
                session_id: opts.sessionId,
                event_type: "assistant_delta",
                payload: { text: eventData },
              };
              this._emit(envelope);
            }
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
