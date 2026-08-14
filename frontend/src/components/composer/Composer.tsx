/**
 * Tektos-Ultima v1 — Composer
 *
 * Rich input area for sending prompts to the active session.
 * Supports multi-line input, keyboard shortcuts, and streaming state.
 *
 * Exemplar pattern: Controlled input with keyboard shortcuts and state feedback.
 */

"use client";

import React, { useState, useRef, useEffect, useCallback } from "react";
import {
  PaperAirplaneIcon,
  StopIcon,
  ArrowUpOnSquareIcon,
} from "@heroicons/react/24/outline";

// ---------------------------------------------------------------------------
// Composer component
// ---------------------------------------------------------------------------

interface ComposerProps {
  isActive: boolean;
  isStreaming: boolean;
  sessionId?: string;
  model?: string;
  onSendMessage: (message: string) => void;
  onInterrupt: () => void;
  onAttach?: (files: File[]) => void;
}

export function Composer({
  isActive,
  isStreaming,
  sessionId,
  model,
  onSendMessage,
  onInterrupt,
  onAttach,
}: ComposerProps) {
  const [value, setValue] = useState("");
  const [isFocused, setIsFocused] = useState(false);
  const [lineCount, setLineCount] = useState(1);
  const [elapsedSec, setElapsedSec] = useState(0);
  const [showMetrics, setShowMetrics] = useState(false);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const handleSubmit = useCallback(() => {
    const trimmed = value.trim();
    if (!trimmed || !isActive || isStreaming) return;

    onSendMessage(trimmed);
    setValue("");
    setLineCount(1);
    setShowMetrics(false);
    textareaRef.current?.focus();
  }, [value, isActive, isStreaming, onSendMessage]);

  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
      // Enter to send (unless Shift+Enter for new line)
      if (e.key === "Enter" && !e.shiftKey) {
        e.preventDefault();
        handleSubmit();
      }
      // Ctrl+D to send
      if ((e.ctrlKey || e.metaKey) && e.key === "d") {
        e.preventDefault();
        handleSubmit();
      }
      // Ctrl+Shift+M to interrupt
      if ((e.ctrlKey || e.metaKey) && e.shiftKey && e.key === "M") {
        e.preventDefault();
        onInterrupt();
      }
    },
    [handleSubmit, onInterrupt]
  );

  // Auto-resize textarea
  useEffect(() => {
    if (textareaRef.current) {
      textareaRef.current.style.height = "auto";
      textareaRef.current.style.height = Math.min(
        textareaRef.current.scrollHeight,
        200
      ) + "px";
    }
  }, [value]);

  // Elapsed time counter during streaming
  useEffect(() => {
    if (!isStreaming) {
      setElapsedSec(0);
      return;
    }
    const interval = setInterval(() => {
      setElapsedSec((prev) => prev + 1);
    }, 1000);
    return () => clearInterval(interval);
  }, [isStreaming]);

  // Format elapsed seconds to mm:ss
  const formatElapsed = (sec: number): string => {
    const m = Math.floor(sec / 60);
    const s = sec % 60;
    return `${m}:${s.toString().padStart(2, "0")}`;
  };

  const handleTextareaChange = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
    setValue(e.target.value);
    const lines = e.target.value.split("\n").length;
    setLineCount(lines);
    setShowMetrics(true);
  };

  const handleFileClick = () => {
    fileInputRef.current?.click();
  };

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = Array.from(e.target.files || []);
    if (files.length > 0 && onAttach) {
      onAttach(files);
    }
    // Reset input
    e.target.value = "";
  };

  // Metrics display helpers
  const formatTokens = (count: number): string => {
    if (count >= 1000) return `${(count / 1000).toFixed(1)}k`;
    return `${count}`;
  };

  const getUsageColor = (pct: number): string => {
    if (pct < 50) return "text-text-muted";
    if (pct < 75) return "text-status-warning";
    return "text-status-error";
  };

  const getUsageBarColor = (pct: number): string => {
    if (pct < 50) return "bg-status-success";
    if (pct < 75) return "bg-status-warning";
    return "bg-status-error";
  };

  // Calculate live metrics from textarea content
  const charCount = value.length;
  const wordCount = value.trim() ? value.trim().split(/\s+/).length : 0;
  const estTokenCount = wordCount ? Math.ceil(wordCount * 1.3) : 0;
  const estContextPct = estTokenCount > 0 ? Math.min((estTokenCount / 128000) * 100, 100) : 0;

  // Show metrics when focused and has content, or when streaming
  const showMetricsUI = isActive && (showMetrics || isStreaming) && (wordCount > 0 || isStreaming);

  return (
    <div className="composer">
      <div className="max-w-4xl mx-auto">
        {/* Status indicator */}
        {isStreaming && (
          <div className="flex items-center gap-2 mb-2 px-1">
            <div className="w-2 h-2 rounded-full bg-status-success animate-pulse" />
            <span className="text-xs text-text-muted">AI is thinking...</span>
          </div>
        )}

        {/* Input wrapper */}
        <div className={`composer-input-wrapper ${isFocused ? "shadow-glow" : ""}`}>
          {/* File attachment */}
          <input
            ref={fileInputRef}
            type="file"
            multiple
            className="hidden"
            onChange={handleFileChange}
          />

          {/* Placeholder overlay (shown when empty and not focused) */}
          {!value && !isFocused && (
            <div className="absolute inset-x-4 top-3 pointer-events-none">
              <p className="text-xs text-text-muted leading-relaxed">
                Paste or upload a{" "}
                <span className="text-accent font-medium">spec</span>, describe
                what you want to{" "}
                <span className="text-accent font-semibold">build</span>, or
                select a session to begin
              </p>
            </div>
          )}

          <textarea
            ref={textareaRef}
            value={value}
            onChange={handleTextareaChange}
            onKeyDown={handleKeyDown}
            onFocus={() => setIsFocused(true)}
            onBlur={() => setIsFocused(false)}
            placeholder={
              isStreaming
                ? "AI is responding... press Ctrl+Shift+M to interrupt"
                : "Describe what you want to build..."
            }
            disabled={!isActive || (isStreaming && false)}
            rows={Math.min(lineCount, 8)}
            className={`w-full bg-transparent border-none text-text-primary text-sm
                       resize-none focus:ring-0 placeholder-text-muted
                       px-4 py-3 min-h-[2.75rem]
                       ${!value && !isFocused ? "pt-6" : ""}`}
          />

          {/* Bottom bar */}
          <div className="flex items-center justify-between px-3 py-2 border-t border-text-muted/10">
            <div className="flex items-center gap-2">
              {/* Attachment button */}
              {onAttach && (
                <button
                  onClick={handleFileClick}
                  disabled={!isActive || isStreaming}
                  className="w-7 h-7 rounded-md flex items-center justify-center
                             text-text-muted hover:text-text-primary hover:bg-surface-hover/50
                             transition-colors disabled:opacity-30 disabled:cursor-not-allowed"
                  title="Attach file"
                >
                  <ArrowUpOnSquareIcon className="w-4 h-4" />
                </button>
              )}

              {/* Model selector (only when text entered) */}
              {model && wordCount > 0 && (
                <span className="text-[10px] text-text-muted/60 px-1.5 py-0.5 rounded bg-bg-3/50">
                  {model}
                </span>
              )}

              {/* Context usage bar (only when text entered) */}
              {isActive && estTokenCount > 0 && (
                <div className="flex items-center gap-2 ml-1">
                  <div className="w-12 h-0.5 rounded-full bg-bg-3 overflow-hidden">
                    <div
                      className={`h-full ${getUsageBarColor(estContextPct)} transition-all duration-200`}
                      style={{ width: `${estContextPct}%` }}
                    />
                  </div>
                  <span className={`text-[10px] ${getUsageColor(estContextPct)}`}>
                    {formatTokens(estTokenCount)} tok
                  </span>
                </div>
              )}
            </div>

            <div className="flex items-center gap-3">
              {/* Metrics display */}
              {showMetricsUI && (
                <div className="flex items-center gap-2 text-xs text-text-muted/70">
                  {wordCount > 0 && (
                    <>
                      <span>{wordCount} words</span>
                      <span className="text-text-muted/30">·</span>
                    </>
                  )}
                  {estTokenCount > 0 && (
                    <>
                      <span>{formatTokens(estTokenCount)} tokens</span>
                      <span className="text-text-muted/30">·</span>
                    </>
                  )}
                  {charCount > 0 && <span>{charCount} chars</span>}
                  {isStreaming && (
                    <>
                      <span className="text-text-muted/30">·</span>
                      <span className="text-accent">{formatElapsed(elapsedSec)}</span>
                    </>
                  )}
                </div>
              )}

              {/* Send/Interrupt button */}
              {isStreaming ? (
                <button
                  onClick={onInterrupt}
                  className="w-7 h-7 rounded-md flex items-center justify-center
                             bg-status-error/20 text-status-error hover:bg-status-error/30
                             transition-colors"
                  title="Stop generation"
                >
                  <StopIcon className="w-4 h-4" />
                </button>
              ) : (
                <button
                  onClick={handleSubmit}
                  disabled={!isActive || !value.trim()}
                  className="w-7 h-7 rounded-md flex items-center justify-center
                             bg-accent text-white hover:bg-accent-hover
                             transition-colors disabled:opacity-30 disabled:cursor-not-allowed
                             disabled:hover:bg-accent"
                  title="Send message"
                >
                  <PaperAirplaneIcon className="w-4 h-4 rotate-90" />
                </button>
              )}
            </div>
          </div>
        </div>

        {/* Keyboard hints (only when active, no metrics) */}
        {!showMetricsUI && isActive && (
          <div className="text-center mt-2">
            <p className="text-[11px] text-text-muted/50">
              Enter to send · Shift+Enter for newline · Ctrl+D to send
            </p>
          </div>
        )}

        {/* Footer version (always visible) */}
        <div className="text-center mt-1">
          <p className="text-[10px] text-text-muted/30">
            Tektos-Ultima v1
          </p>
        </div>
      </div>
    </div>
  );
}
