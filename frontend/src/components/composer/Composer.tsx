/**
 * Tektos-Ultima v1 — Composer (Redesigned)
 *
 * Workflow-centered input with:
 * - Context-aware placeholder text
 * - Smart keyboard shortcuts display
 * - Live token/context usage visualization
 * - File attachment support
 * - Streaming state feedback
 * - Minimal, focused design
 */

"use client";

import React, { useState, useRef, useEffect, useCallback } from "react";
import {
  PaperAirplaneIcon,
  StopIcon,
  ArrowUpOnSquareIcon,
  SparklesIcon,
} from "@heroicons/react/24/outline";

// ---------------------------------------------------------------------------
// Composer component
// ---------------------------------------------------------------------------

interface ComposerProps {
  isActive: boolean;
  isStreaming: boolean;
  sessionId?: string;
  model?: string;
  connectionState?: "disconnected" | "connecting" | "connected" | "reconnecting";
  onSendMessage: (message: string) => void;
  onInterrupt: () => void;
  onAttach?: (files: File[]) => void;
}

export function Composer({
  isActive,
  isStreaming,
  sessionId,
  model,
  connectionState = "disconnected",
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
  
  // Prompt history for up/down arrow navigation
  const [promptHistory, setPromptHistory] = useState<string[]>([]);
  const [historyIndex, setHistoryIndex] = useState(-1);

  const handleSubmit = useCallback(() => {
    const trimmed = value.trim();
    if (!trimmed || !isActive || isStreaming) return;

    // Add to history
    setPromptHistory(prev => {
      const newHistory = [...prev, trimmed];
      // Keep only last 50 messages
      return newHistory.slice(-50);
    });
    setHistoryIndex(-1); // Reset history navigation

    onSendMessage(trimmed);
    setValue("");
    setLineCount(1);
    setShowMetrics(false);
    textareaRef.current?.focus();
  }, [value, isActive, isStreaming, onSendMessage]);

  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
      // Up arrow: navigate back through history
      if (e.key === "ArrowUp" && !value) {
        e.preventDefault();
        if (promptHistory.length > 0) {
          setHistoryIndex(promptHistory.length - 1);
          setValue(promptHistory[promptHistory.length - 1]);
        }
        return;
      }
      // Down arrow: navigate forward through history
      if (e.key === "ArrowDown") {
        e.preventDefault();
        if (historyIndex < promptHistory.length - 1) {
          const nextIndex = historyIndex + 1;
          setHistoryIndex(nextIndex);
          setValue(promptHistory[nextIndex]);
        } else {
          // Reached the end, clear input
          setHistoryIndex(-1);
          setValue("");
        }
        return;
      }
      if (e.key === "Enter" && !e.shiftKey) {
        e.preventDefault();
        handleSubmit();
      }
      if ((e.ctrlKey || e.metaKey) && e.key === "d") {
        e.preventDefault();
        handleSubmit();
      }
      if ((e.ctrlKey || e.metaKey) && e.shiftKey && e.key === "M") {
        e.preventDefault();
        onInterrupt();
      }
    },
    [handleSubmit, onInterrupt, value, promptHistory, historyIndex]
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

  // Elapsed time counter
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
    e.target.value = "";
  };

  // Metrics
  const charCount = value.length;
  const wordCount = value.trim() ? value.trim().split(/\s+/).length : 0;
  const estTokenCount = wordCount ? Math.ceil(wordCount * 1.3) : 0;
  const estContextPct = estTokenCount > 0 ? Math.min((estTokenCount / 128000) * 100, 100) : 0;

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

  const showMetricsUI = isActive && (showMetrics || isStreaming) && (wordCount > 0 || isStreaming);

  // Context-aware placeholder
  const getPlaceholder = () => {
    if (!isActive) return "Create a session to start";
    if (isStreaming) return "AI is responding... Ctrl+Shift+M to interrupt";
    return "Describe what you want to build...";
  };

  return (
    <div className="composer">
      <div className="max-w-4xl mx-auto">
        {/* Streaming indicator */}
        {isStreaming && (
          <div className="flex items-center gap-2 mb-2 px-1">
            <div className="w-2 h-2 rounded-full bg-accent animate-pulse" />
            <span className="text-xs text-accent font-medium">AI is thinking</span>
            <span className="text-xs text-text-muted/50">·</span>
            <span className="text-xs text-text-muted/70">{formatElapsed(elapsedSec)}</span>
          </div>
        )}

        {/* Input wrapper */}
        <div className={`composer-input-wrapper ${isFocused ? "shadow-glow" : ""}`}>
          <input
            ref={fileInputRef}
            type="file"
            multiple
            className="hidden"
            onChange={handleFileChange}
          />

          {/* Placeholder overlay */}
          {!value && !isFocused && (
            <div className="absolute inset-x-4 top-3 pointer-events-none">
              <div className="flex items-center gap-3">
                <SparklesIcon className="w-4 h-4 text-accent/50 flex-shrink-0" />
                <p className="text-xs text-text-muted/60 leading-relaxed">
                  {getPlaceholder()}
                </p>
              </div>
            </div>
          )}

          <textarea
            ref={textareaRef}
            value={value}
            onChange={handleTextareaChange}
            onKeyDown={handleKeyDown}
            onFocus={() => setIsFocused(true)}
            onBlur={() => setIsFocused(false)}
            placeholder={getPlaceholder()}
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
              {/* File attachment */}
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

              {/* Model selector */}
              {model && (
                <span className="text-[10px] text-text-muted/60 px-1.5 py-0.5 rounded bg-bg-3/50">
                  {model}
                </span>
              )}

              {/* Context usage */}
              {isActive && estTokenCount > 0 && (
                <div className="flex items-center gap-2 ml-1">
                  <div className="w-16 h-1 rounded-full bg-bg-3 overflow-hidden">
                    <div
                      className={`h-full ${getUsageBarColor(estContextPct)} transition-all duration-200`}
                      style={{ width: `${estContextPct}%` }}
                    />
                  </div>
                  <span className={`text-[10px] ${getUsageColor(estContextPct)}`}>
                    {formatTokens(estTokenCount)}/128k tok
                  </span>
                </div>
              )}

              {/* Elapsed time when streaming */}
              {isStreaming && (
                <span className="text-[10px] text-accent/70 ml-1">
                  ⏱ {formatElapsed(elapsedSec)}
                </span>
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

              {/* Send/Interrupt */}
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

          {/* Persistent status bar — always visible when active */}
          {isActive && (
            <div className="flex items-center justify-between px-3 py-1.5 border-t border-text-muted/5">
              <div className="flex items-center gap-2">
                {/* Connection status */}
                <div className="flex items-center gap-1.5">
                  <div className={`w-1.5 h-1.5 rounded-full ${
                    connectionState === "connected" ? "bg-status-success" :
                    connectionState === "connecting" || connectionState === "reconnecting" ? "bg-status-warning animate-pulse" :
                    "bg-status-error"
                  }`} />
                  <span className="text-[10px] text-text-muted/50 capitalize">
                    {connectionState === "reconnecting" ? "reconnecting" : connectionState}
                  </span>
                </div>

                {/* Active session indicator */}
                {sessionId && (
                  <span className="text-[10px] text-text-muted/40">
                    {sessionId.slice(0, 8)}...
                  </span>
                )}
              </div>

              <div className="flex items-center gap-2">
                {/* Model + context */}
                {model && (
                  <span className="text-[10px] text-text-muted/40">
                    {model}
                  </span>
                )}
                {isStreaming && (
                  <>
                    <span className="text-[10px] text-text-muted/30">·</span>
                    <span className="text-[10px] text-accent/70">
                      ⏱ {formatElapsed(elapsedSec)}
                    </span>
                  </>
                )}
              </div>
            </div>
          )}
        </div>

        {/* Keyboard hints */}
        {!showMetricsUI && isActive && (
          <div className="text-center mt-2">
            <div className="flex items-center justify-center gap-3 text-[11px] text-text-muted/50">
              <span className="flex items-center gap-1">
                <kbd className="px-1.5 py-0.5 rounded bg-surface border border-border text-[10px]">
                  Enter
                </kbd>
                <span>send</span>
              </span>
              <span className="flex items-center gap-1">
                <kbd className="px-1.5 py-0.5 rounded bg-surface border border-border text-[10px]">
                  Shift+Enter
                </kbd>
                <span>newline</span>
              </span>
              <span className="flex items-center gap-1">
                <kbd className="px-1.5 py-0.5 rounded bg-surface border border-border text-[10px]">
                  Ctrl+D
                </kbd>
                <span>send</span>
              </span>
              <span className="flex items-center gap-1">
                <kbd className="px-1.5 py-0.5 rounded bg-surface border border-border text-[10px]">
                  Ctrl+Shift+M
                </kbd>
                <span>stop</span>
              </span>
            </div>
          </div>
        )}

        {/* Footer */}
        <div className="text-center mt-1">
          <p className="text-[10px] text-text-muted/30">
            Tektos-Ultima v1
          </p>
        </div>
      </div>
    </div>
  );
}
