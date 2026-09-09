"use client";

import { useStore } from "@nanostores/react";
import { $toolCalls } from "@/lib/stores/session";
import type { AssistantMessage } from "@/lib/stores/session";
import { Markdown } from "./Markdown";
import { cn } from "@/lib/cn";
import { ToolCallCard } from "@/components/assistant-ui/tool-visualizers/ToolCallCard";

interface Props {
  message: AssistantMessage;
}

/**
 * One assistant/user/system message. Assistant messages that have
 * attached tool calls render them inline in order.
 */
export function MessageBubble({ message }: Props) {
  const tools = useStore($toolCalls);
  const isAssistant = message.role === "assistant";
  const isSystem = message.role === "system";

  return (
    <article
      data-role={message.role}
      data-completed={message.completed}
      className={cn(
        "group flex flex-col gap-2 py-4",
        isSystem && "text-text-muted text-12",
      )}
    >
      <header className="flex items-center gap-2 text-11 text-text-faint">
        <span
          className={cn(
            "inline-flex items-center gap-1.5 tabular",
            isAssistant && "text-primary",
          )}
        >
          {message.role}
          {!message.completed && isAssistant && (
            <span className="inline-block h-1.5 w-1.5 rounded-full bg-agent animate-tektos-pulse" />
          )}
        </span>
        {message.usage?.total !== undefined && (
          <span className="tabular">
            {message.usage.total} tok
          </span>
        )}
      </header>

      {message.text.length > 0 && <Markdown>{message.text}</Markdown>}

      {message.tool_call_ids.length > 0 && (
        <div className="flex flex-col gap-2 pl-3">
          {message.tool_call_ids.map((id) =>
            tools[id] ? <ToolCallCard key={id} tool={tools[id]} /> : null,
          )}
        </div>
      )}

      {message.reasoning && message.reasoning.length > 0 && (
        <details className="mt-1 text-11 text-text-muted">
          <summary className="cursor-pointer select-none">reasoning</summary>
          <pre className="mt-1 whitespace-pre-wrap font-mono text-11 text-text-muted">
            {message.reasoning}
          </pre>
        </details>
      )}
    </article>
  );
}
