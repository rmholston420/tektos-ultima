/**
 * Tektos-Ultima v1 — Composer (Hermes Agent ChatBar clone)
 *
 * Matches Hermes Agent desktop:
 * - Textarea with inline status
 * - Model pill on left (showing model name, not icon)
 * - Send/stop button on right (solid circle, arrow-up)
 * - CSS custom properties for sizing: --composer-control-size, --composer-control-gap
 */

"use client";

import React, { useState, useRef, useCallback } from "react";
import {
  ChevronDownIcon,
} from "@heroicons/react/24/outline";
import { useAuiState } from "@assistant-ui/react";
import { TektosExternalStoreAdapter } from "@/lib/tektos-store-adapter";

// CSS for composer controls — matches Hermes Agent desktop PRIMARY_ICON_BTN exactly
const COMPOSER_CSS = `
  .composer-send-btn {
    width: 1.625rem;
    height: 1.625rem;
    flex-shrink: 0;
    border-radius: 50%;
    padding: 0;
    display: flex;
    align-items: center;
    justify-content: center;
    border: none;
    cursor: pointer;
    transition: opacity 0.15s;
    background: var(--text-primary);
    color: var(--bg-primary);
  }
  .composer-send-btn:hover:not(:disabled) {
    opacity: 0.85;
  }
  .composer-send-btn:disabled {
    background: color-mix(in srgb, var(--text-primary) 30%, transparent);
    color: var(--bg-primary);
    opacity: 0.4;
    cursor: not-allowed;
  }
  .composer-model-pill {
    height: 1.5rem;
    max-width: 10rem;
    flex-shrink: 0;
    border-radius: 0.375rem;
    padding: 0 0.5rem;
    display: flex;
    align-items: center;
    gap: 0.25rem;
    font-size: 0.75rem;
    font-weight: 400;
    color: var(--text-muted-tertiary);
    background: transparent;
    cursor: pointer;
    border: none;
    transition: background-color 0.15s, color 0.15s;
  }
  .composer-model-pill:hover {
    background: var(--chrome-action-hover);
    color: var(--text-primary);
  }
  .composer-model-pill:disabled {
    opacity: 0.3;
    cursor: not-allowed;
    background: transparent;
  }
`;

interface ComposerProps {
  isActive?: boolean;
  sessionId?: string;
  model?: string;
  onModelChange?: (modelId: string) => void;
  connectionState?: "disconnected" | "connecting" | "connected" | "reconnecting";
  adapter: TektosExternalStoreAdapter;
  onSendMessage?: (message: string) => Promise<void>;
  onInterrupt?: () => void;
  onAttachFiles?: (files: File[]) => void;
  onVisionAnalyze?: (imageBase64: string, prompt: string) => void;
  visionAvailable?: boolean;
  visionModel?: string;
  onNewSession?: () => void;
}

export function Composer({
  isActive,
  sessionId,
  model,
  onModelChange,
  connectionState = "disconnected",
  adapter,
  onSendMessage,
  onInterrupt,
  onAttachFiles,
  onVisionAnalyze,
  visionAvailable = false,
  visionModel,
  onNewSession,
}: ComposerProps) {
  const isStreaming = useAuiState(
    (s) => s.thread.isRunning && s.thread.messages.some((m) => m.role === "assistant")
  );

  const [value, setValue] = useState("");
  const [isFocused, setIsFocused] = useState(false);
  const [attachedImage, setAttachedImage] = useState<string | null>(null);
  const [visionPrompt, setVisionPrompt] = useState("");
  const [isVisionMode, setIsVisionMode] = useState(false);
  const [queuedMessages, setQueuedMessages] = useState<string[]>([]);
  const [promptHistory, setPromptHistory] = useState<string[]>([]);
  const [historyIndex, setHistoryIndex] = useState(-1);

  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const visionInputRef = useRef<HTMLInputElement>(null);

  // Status
  const isConnecting = connectionState !== "connected";
  const statusColor = isConnecting
    ? connectionState === "reconnecting"
      ? "text-yellow-500"
      : connectionState === "connecting"
        ? "text-yellow-500"
        : "text-status-error"
    : "text-status-success";

  const statusText = (() => {
    if (!isActive) return "";
    if (isStreaming) return "";
    if (queuedMessages.length > 0) return `${queuedMessages.length} queued`;
    if (connectionState === "reconnecting") return "Reconnecting…";
    if (connectionState === "connecting") return "Connecting…";
    if (!isConnecting) return "";
    return "Disconnected";
  })();

  // Handlers
  const handleSubmit = useCallback(async () => {
    const trimmed = value.trim();
    if (!trimmed || isStreaming && !value.trim() && queuedMessages.length === 0) return;

    setPromptHistory(prev => [...prev, trimmed].slice(-50));
    setHistoryIndex(-1);

    // Queue if streaming and have text
    if (isStreaming && trimmed) {
      if (queuedMessages.length < 10) {
        setQueuedMessages(prev => [...prev, trimmed]);
      }
      setValue("");
      textareaRef.current?.focus();
      return;
    }

    // Send via page.tsx handler (which does adapter.sendMessage + protocolClient.sendPrompt)
    if (onSendMessage && trimmed) {
      await onSendMessage(trimmed);
    } else {
      // Fallback: send through adapter directly
      await adapter.sendMessage(trimmed);
    }
    setValue("");
    textareaRef.current?.focus();
  }, [value, isStreaming, queuedMessages, onSendMessage, adapter]);

  const handleDrainQueue = useCallback(async () => {
    if (queuedMessages.length === 0) return;
    const next = queuedMessages[0];
    setQueuedMessages(prev => prev.slice(1));
    if (onSendMessage) {
      await onSendMessage(next);
    } else {
      await adapter.sendMessage(next);
    }
  }, [queuedMessages, onSendMessage, adapter]);

  const handleInterrupt = useCallback(() => {
    if (onInterrupt) {
      onInterrupt();
    } else {
      adapter.interrupt();
    }
  }, [onInterrupt, adapter]);

  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
      // Up arrow: history
      if (e.key === "ArrowUp" && !value) {
        e.preventDefault();
        if (promptHistory.length > 0) {
          setHistoryIndex(promptHistory.length - 1);
          setValue(promptHistory[promptHistory.length - 1]);
        }
        return;
      }
      if (e.key === "ArrowDown") {
        e.preventDefault();
        if (historyIndex < promptHistory.length - 1) {
          setHistoryIndex(historyIndex + 1);
          setValue(promptHistory[historyIndex + 1]);
        } else {
          setHistoryIndex(-1);
          setValue("");
        }
        return;
      }
      // Ctrl+Enter: queue message
      if (e.key === "Enter" && e.ctrlKey && !e.shiftKey && isStreaming && value.trim()) {
        e.preventDefault();
        setQueuedMessages(prev => [...prev, value.trim()]);
        setValue("");
        return;
      }
      // Enter: send or drain queue
      if (e.key === "Enter" && !e.shiftKey) {
        e.preventDefault();
        if (isStreaming && !value.trim() && queuedMessages.length > 0) {
          handleDrainQueue();
          return;
        }
        handleSubmit();
        return;
      }
      // Ctrl+C: interrupt
      if ((e.ctrlKey || e.metaKey) && e.key === "c" && isStreaming) {
        e.preventDefault();
        handleInterrupt();
        return;
      }
      // Ctrl+Shift+K: drain queue
      if ((e.ctrlKey || e.metaKey) && e.shiftKey && e.key === "K") {
        e.preventDefault();
        handleDrainQueue();
        return;
      }
      // Escape: interrupt
      if (e.key === "Escape" && isStreaming) {
        e.preventDefault();
        handleInterrupt();
        return;
      }
    },
    [handleSubmit, handleDrainQueue, handleInterrupt, value, promptHistory, historyIndex, isStreaming, queuedMessages]
  );

  const handleResize = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
    e.target.style.height = "auto";
    e.target.style.height = e.target.scrollHeight + "px";
    setValue(e.target.value);
  };

  const handleVisionImageChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = Array.from(e.target.files || []);
    if (files.length === 0) return;
    const file = files[0];
    if (!file.type.startsWith("image/")) return;
    const reader = new FileReader();
    reader.onload = () => setAttachedImage(reader.result as string);
    reader.readAsDataURL(file);
    e.target.value = "";
  };

  const handleVisionAnalyzeLocal = () => {
    if (!attachedImage || !visionPrompt || !onVisionAnalyze) return;
    onVisionAnalyze(attachedImage, visionPrompt);
    setVisionPrompt("");
    setAttachedImage(null);
  };

  const toggleVisionMode = () => {
    setIsVisionMode(!isVisionMode);
    setAttachedImage(null);
    setVisionPrompt("");
  };

  const clearImage = () => setAttachedImage(null);

  const hasText = value.trim().length > 0;
  const hasAttachment = attachedImage !== null;
  const canSend = hasText || isStreaming;
  const isStreamingOrQueued = isStreaming || queuedMessages.length > 0;

  // Short model name for display (strip paths, keep just the model)
  const modelName = model
    ? model.split('/').pop()?.split('-').slice(0, 2).join('-') || model
    : '';

  return (
    <div className="composer" style={{ 
      '--composer-control-size': '1.5rem', 
      '--composer-control-gap': '0.25rem', 
      '--composer-control-primary-size': '1.625rem', 
      '--composer-surface-pad-x': '0.5rem', 
      '--composer-surface-pad-y': '0.3125rem', 
      '--composer-row-gap': '0.25rem', 
      '--composer-input-min-height': '1.625rem', 
      '--composer-input-max-height': '9.375rem',
      '--composer-fill': 'rgba(0, 0, 0, 0.2)',
      '--dt-input': 'rgba(0, 0, 0, 0.3)',
      '--ui-chat-surface-background': '#0a0a0a',
      '--ui-base': '#ffffff',
      '--text-primary': '#e5e5e5',
      '--bg-primary': '#111111',
      '--text-muted-tertiary': '#737373',
      '--chrome-action-hover': 'rgba(255, 255, 255, 0.08)',
    } as React.CSSProperties} data-slot="composer-root">
      <style>{COMPOSER_CSS}</style>
      <div className="max-w-4xl mx-auto">
        {/* Queue pills — only show when actually queued */}
        {queuedMessages.length > 0 && (
          <div className="flex flex-wrap items-center gap-1.5 px-[5px] pb-1.5">
            <button
              onClick={handleDrainQueue}
              className="inline-flex h-[1.5rem] shrink-0 cursor-pointer items-center gap-1.5 rounded-full px-2.5 text-xs font-normal text-muted-foreground border border-border/65 bg-surface/80 backdrop-blur-[0.5rem] hover:bg-surface-hover transition-colors"
            >
              <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 16 16" fill="currentColor" className="w-3 h-3"><path d="M7.25 1.75a.75.75 0 0 1 1.5 0v7.19l3.47-3.47a.75.75 0 1 1 1.06 1.06l-4.75 4.75a.75.75 0 0 1-1.06 0l-4.75-4.75a.75.75 0 1 1 1.06-1.06l3.47 3.47V1.75Z" transform="rotate(180 8 8)"/></svg>
              <span>Send queued ({queuedMessages.length})</span>
            </button>
          </div>
        )}

        {/* Composer surface — matches Hermes Agent: rounded-2xl, glass border, subtle background */}
        <div className="group/composer relative w-full overflow-visible rounded-2xl">
          <div
            className="group/composer-surface relative z-4 isolate grid grid-rows-[auto_1fr] overflow-hidden rounded-[inherit] border border-[color-mix(in_srgb,var(--ui-base)_calc(18%*1),var(--dt-input))] bg-[var(--composer-fill,var(--ui-chat-surface-background))] backdrop-blur-sm transition-[background-color] duration-150 ease-out"
            data-slot="composer-surface"
          >
            {/* Glass fill layer (pointer-events-none overlay) */}
            <div
              aria-hidden
              className="pointer-events-none absolute inset-0 -z-10 rounded-[inherit] bg-[var(--composer-fill,var(--ui-chat-surface-background))]"
            />
            <div
              className="relative z-1 flex min-h-0 w-full flex-col gap-[var(--composer-row-gap)] overflow-hidden rounded-[inherit] px-[var(--composer-surface-pad-x)] py-[var(--composer-surface-pad-y)] transition-opacity duration-200 ease-out"
              data-slot="composer-fade"
            >
              {/* Main input row: 3-column grid — [model] [input] [controls] */}
              <div className="grid w-full grid-cols-[auto_1fr_auto] items-center gap-[var(--composer-control-gap)]">
                {/* Left: model pill */}
                <div className="flex translate-y-[3px] items-start gap-[var(--composer-control-gap)] self-start">
                  {onModelChange && model && isActive && (
                    <button
                      onClick={() => onModelChange(model)}
                      disabled={!isActive}
                      className="composer-model-pill"
                      type="button"
                    >
                      <span className="truncate">{modelName}</span>
                      <ChevronDownIcon className="w-2.5 h-2.5 shrink-0 opacity-50" />
                    </button>
                  )}
                </div>

                {/* Center: textarea */}
                <div className="min-w-0 relative">
                  <textarea
                    ref={textareaRef}
                    value={value}
                    onChange={handleResize}
                    onKeyDown={handleKeyDown}
                    placeholder={statusText}
                    disabled={!isActive && connectionState === "disconnected"}
                    className="w-full resize-none bg-transparent py-1 pr-1 text-foreground outline-none disabled:cursor-not-allowed text-[0.875rem] leading-normal placeholder:text-muted-foreground/60 min-h-[var(--composer-input-min-height)] max-h-[var(--composer-input-max-height)] overflow-y-auto"
                    rows={1}
                  />
                  {/* Inline status: dot + text overlay */}
                  <div className="pointer-events-none absolute inset-y-1 left-0 flex items-center pl-0">
                    <span className={`w-1.5 h-1.5 rounded-full ${statusColor} mr-1.5`}></span>
                    <span className={`text-[11px] ${statusColor} truncate`}>{statusText}</span>
                  </div>
                </div>

                {/* Right: send/stop — solid circle button matching PRIMARY_ICON_BTN */}
                <div className="flex items-center justify-end gap-[var(--composer-control-gap)]">
                  {/* File upload button */}
                  <button
                    onClick={() => fileInputRef.current?.click()}
                    disabled={!isActive}
                    className="composer-send-btn"
                    type="button"
                    title="Attach file"
                  >
                    <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 16 16" fill="currentColor" className="w-4 h-4"><path d="M1.5 0h11.586a1.5 1.5 0 0 1 1.06.44l1.415 1.414A1.5 1.5 0 0 1 16 2.914V14.5a1.5 1.5 0 0 1-1.5 1.5h-13A1.5 1.5 0 0 1 0 14.5v-13A1.5 1.5 0 0 1 1.5 0ZM11 2H2v12h12V2Zm-1 1v5.586l2.293-2.293a.5.5 0 1 1 .707.707l-3 3a.5.5 0 0 1-.707 0l-3-3a.5.5 0 1 1 .707-.707L5 8.586V3a1 1 0 1 1 2 0Z" /></svg>
                  </button>
                  <input
                    ref={fileInputRef}
                    type="file"
                    multiple
                    accept="image/*,.pdf,.txt,.md,.json,.csv"
                    className="hidden"
                    onChange={(e) => {
                      const files = Array.from(e.target.files || []);
                      if (files.length > 0 && onAttachFiles) {
                        onAttachFiles(files);
                      }
                      e.target.value = "";
                    }}
                  />
                  {isStreaming ? (
                    <button
                      onClick={handleInterrupt}
                      className="composer-send-btn"
                      type="submit"
                      title="Stop"
                    >
                      <span className="block size-2.5 rounded-[0.1875rem] bg-current" />
                    </button>
                  ) : (
                    <button
                      onClick={handleSubmit}
                      disabled={!canSend}
                      className="composer-send-btn"
                      type="submit"
                      title="Send"
                    >
                      <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 16 16" fill="currentColor" className="w-4 h-4"><path d="M7.25 1.75a.75.75 0 0 1 1.5 0v7.19l3.47-3.47a.75.75 0 1 1 1.06 1.06l-4.75 4.75a.75.75 0 0 1-1.06 0l-4.75-4.75a.75.75 0 1 1 1.06-1.06l3.47 3.47V1.75Z" transform="rotate(180 8 8)"/></svg>
                    </button>
                  )}
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
