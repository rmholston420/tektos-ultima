"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { useStore } from "@nanostores/react";
import { Send, Square } from "lucide-react";
import { cn } from "@/lib/cn";
import { $connectionState } from "@/lib/stores/connection";
import {
  $activeToolIds,
  $messages,
  $messageOrder,
} from "@/lib/stores/session";
import { getProtocolClient } from "@/lib/hooks/useProtocol";

/**
 * Composer: single textarea + submit/interrupt. Autosize up to ~40vh.
 *
 * Enter submits; Shift+Enter inserts a newline. Interrupt is available
 * while any tool is running or an assistant message is streaming.
 */
export function Composer() {
  const [text, setText] = useState("");
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const state = useStore($connectionState);
  const activeToolIds = useStore($activeToolIds);
  const messagesById = useStore($messages);
  const order = useStore($messageOrder);

  const lastMessage = order.length ? messagesById[order[order.length - 1]] : null;
  const streaming =
    activeToolIds.length > 0 || (lastMessage?.role === "assistant" && !lastMessage.completed);

  const autosize = useCallback(() => {
    const el = textareaRef.current;
    if (!el) return;
    el.style.height = "auto";
    el.style.height = Math.min(el.scrollHeight, window.innerHeight * 0.4) + "px";
  }, []);

  useEffect(() => {
    autosize();
  }, [text, autosize]);

  const canSend = text.trim().length > 0 && state === "connected" && !streaming;

  const submit = useCallback(() => {
    const trimmed = text.trim();
    if (!trimmed) return;
    const client = getProtocolClient();
    // Optimistic user message so the transcript reflects submit immediately.
    const now = new Date().toISOString();
    const id = `local-user-${crypto.randomUUID()}`;
    $messages.setKey(id, {
      id,
      role: "user",
      text: trimmed,
      created_at: now,
      completed: true,
      tool_call_ids: [],
    });
    $messageOrder.set([...$messageOrder.get(), id]);
    client.sendPrompt(trimmed);
    setText("");
  }, [text]);

  const interrupt = useCallback(() => {
    const client = getProtocolClient();
    client.sendInterrupt();
  }, []);

  const onKeyDown = useCallback(
    (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
      if (e.key === "Enter" && !e.shiftKey) {
        e.preventDefault();
        if (canSend) submit();
      }
    },
    [canSend, submit],
  );

  return (
    <form
      onSubmit={(e) => {
        e.preventDefault();
        if (canSend) submit();
      }}
      className="w-full"
      aria-label="Composer"
    >
      <div
        className={cn(
          "hairline flex items-end gap-2 rounded bg-surface-3 p-2",
          "focus-within:shadow-card",
        )}
      >
        <textarea
          ref={textareaRef}
          value={text}
          onChange={(e) => setText(e.target.value)}
          onKeyDown={onKeyDown}
          placeholder={
            state === "connected"
              ? "Ask Tektos to build, refactor, explain..."
              : `Waiting for gateway (${state})...`
          }
          rows={1}
          disabled={state !== "connected"}
          className={cn(
            "min-h-[36px] flex-1 resize-none bg-transparent outline-none",
            "text-13 leading-relaxed text-text-base placeholder:text-text-faint",
            "disabled:cursor-not-allowed disabled:opacity-60",
          )}
          data-testid="composer-input"
        />
        {streaming ? (
          <button
            type="button"
            onClick={interrupt}
            className={cn(
              "inline-flex h-8 items-center justify-center rounded px-3 gap-1",
              "text-11 text-text-base bg-surface-6 hover:bg-surface-7",
              "transition-colors duration-fast ease",
            )}
            title="Interrupt (Esc)"
            data-testid="composer-interrupt"
          >
            <Square className="h-3 w-3" fill="currentColor" />
            stop
          </button>
        ) : (
          <button
            type="submit"
            disabled={!canSend}
            className={cn(
              "inline-flex h-8 items-center justify-center rounded px-3 gap-1",
              "text-11 font-medium",
              canSend
                ? "bg-primary text-surface-0 hover:bg-primary-hover"
                : "bg-surface-6 text-text-faint cursor-not-allowed",
              "transition-colors duration-fast ease",
            )}
            title="Send (Enter)"
            data-testid="composer-send"
          >
            <Send className="h-3 w-3" />
            send
          </button>
        )}
      </div>
      <div className="mt-1.5 px-1 text-10 text-text-faint">
        Enter to send \u00b7 Shift+Enter for newline \u00b7 Esc to interrupt
      </div>
    </form>
  );
}
