/**
 * Tektos-Ultima v1 — TTSPlayer
 *
 * Plays TTS audio responses from the backend.
 * Supports auto-play when assistant responds.
 */

"use client";

import React, { useState, useRef, useEffect, useCallback } from "react";

interface TTSPlayerProps {
  backendUrl?: string;
  autoPlay?: boolean;
  onText?: (text: string) => void;
}

export function TTSPlayer({
  backendUrl = process.env.NEXT_PUBLIC_TEKTOS_HOST || "localhost",
  autoPlay = true,
  onText,
}: TTSPlayerProps) {
  const [isPlaying, setIsPlaying] = useState(false);
  const [isSynthesizing, setIsSynthesizing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const audioRef = useRef<HTMLAudioElement | null>(null);
  const audioUrlRef = useRef<string | null>(null);

  // Cleanup audio URL on unmount
  useEffect(() => {
    return () => {
      if (audioUrlRef.current) {
        URL.revokeObjectURL(audioUrlRef.current);
        audioUrlRef.current = null;
      }
    };
  }, []);

  const synthesizeAndPlay = useCallback(async (text: string) => {
    if (!text) return;

    // Cancel any current playback
    if (audioRef.current) {
      audioRef.current.pause();
      audioRef.current.currentTime = 0;
    }
    if (audioUrlRef.current) {
      URL.revokeObjectURL(audioUrlRef.current);
      audioUrlRef.current = null;
    }

    setIsSynthesizing(true);
    setError(null);

    try {
      const response = await fetch(`http://${backendUrl}:8020/api/voice/tts`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text }),
      });

      if (!response.ok) {
        throw new Error(`TTS synthesis failed: ${response.status}`);
      }

      const audioBlob = await response.blob();
      const audioUrl = URL.createObjectURL(audioBlob);
      audioUrlRef.current = audioUrl;

      if (onText) {
        onText(text);
      }

      if (autoPlay) {
        const audio = new Audio(audioUrl);
        audioRef.current = audio;

        audio.onplay = () => setIsPlaying(true);
        audio.onpause = () => setIsPlaying(false);
        audio.onended = () => {
          setIsPlaying(false);
          if (audioUrlRef.current) {
            URL.revokeObjectURL(audioUrlRef.current);
            audioUrlRef.current = null;
          }
        };
        audio.onerror = () => {
          setError("Audio playback failed");
          setIsPlaying(false);
        };

        await audio.play();
      }
    } catch (err) {
      console.error("TTS error:", err);
      setError(err instanceof Error ? err.message : "TTS synthesis failed");
    } finally {
      setIsSynthesizing(false);
    }
  }, [backendUrl, autoPlay, onText]);

  const stop = useCallback(() => {
    if (audioRef.current) {
      audioRef.current.pause();
      audioRef.current.currentTime = 0;
    }
    if (audioUrlRef.current) {
      URL.revokeObjectURL(audioUrlRef.current);
      audioUrlRef.current = null;
    }
    setIsPlaying(false);
  }, []);

  return (
    <div className="flex items-center gap-2">
      {/* Play/Pause button */}
      <button
        onClick={() => {
          if (isPlaying) {
            audioRef.current?.pause();
          } else {
            audioRef.current?.play();
          }
        }}
        disabled={!isPlaying && !isSynthesizing}
        className={`
          w-8 h-8 rounded-full flex items-center justify-center
          transition-all duration-200
          ${isPlaying
            ? "bg-green-500 hover:bg-green-600"
            : isSynthesizing
              ? "bg-yellow-500 hover:bg-yellow-600"
              : "bg-gray-700 hover:bg-gray-600"
          }
          ${!isPlaying && !isSynthesizing ? "opacity-50 cursor-not-allowed" : "cursor-pointer"}
        `}
        title={isPlaying ? "Pause" : isSynthesizing ? "Synthesizing..." : "Play"}
      >
        {isSynthesizing ? (
          <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="currentColor" className="w-4 h-4 text-white">
            <path d="M12 2a10 10 0 1 0 10 10A10 10 0 0 0 12 2Zm0 18a8 8 0 1 1 8-8 8 8 0 0 1-8 8Z" />
            <path d="M12 6a1 1 0 0 1 1 1v4a1 1 0 0 1-2 0V7a1 1 0 0 1 1-1Zm0 6a1 1 0 0 1 1 1v2a1 1 0 0 1-2 0v-2a1 1 0 0 1 1-1Z" />
          </svg>
        ) : isPlaying ? (
          <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="currentColor" className="w-4 h-4 text-white">
            <path d="M6 4h4v16H6V4Zm8 0h4v16h-4V4Z" />
          </svg>
        ) : (
          <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="currentColor" className="w-4 h-4 text-white">
            <path d="M8 5v14l11-7L8 5Z" />
          </svg>
        )}
      </button>

      {/* Stop button */}
      {isPlaying && (
        <button
          onClick={stop}
          className="w-6 h-6 rounded-full bg-red-500 hover:bg-red-600 flex items-center justify-center"
          title="Stop"
        >
          <div className="w-2 h-2 rounded-sm bg-white" />
        </button>
      )}

      {/* Error message */}
      {error && (
        <div className="text-xs text-red-400">{error}</div>
      )}
    </div>
  );
}
