/**
 * Tektos-Ultima v1 — MicButton with waveform visualization
 *
 * Records audio from the microphone and displays a real-time waveform.
 * When recording stops, the audio is sent to the backend for transcription.
 */

"use client";

import React, { useState, useRef, useCallback, useEffect } from "react";

interface MicButtonProps {
  isActive?: boolean;
  onTranscript?: (text: string) => void;
  backendUrl?: string;
}

export function MicButton({
  isActive = true,
  onTranscript,
  backendUrl = process.env.NEXT_PUBLIC_TEKTOS_HOST || "localhost",
}: MicButtonProps) {
  const [isRecording, setIsRecording] = useState(false);
  const [waveformData, setWaveformData] = useState<number[]>([]);
  const [isTranscribing, setIsTranscribing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const audioChunksRef = useRef<Blob[]>([]);
  const analyserRef = useRef<AnalyserNode | null>(null);
  const animationFrameRef = useRef<number | null>(null);
  const streamRef = useRef<MediaStream | null>(null);

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      stopRecording();
    };
  }, []);

  const stopRecording = useCallback(() => {
    if (animationFrameRef.current) {
      cancelAnimationFrame(animationFrameRef.current);
      animationFrameRef.current = null;
    }
    if (streamRef.current) {
      streamRef.current.getTracks().forEach((track) => track.stop());
      streamRef.current = null;
    }
    if (mediaRecorderRef.current && mediaRecorderRef.current.state !== "inactive") {
      mediaRecorderRef.current.stop();
    }
    setIsRecording(false);
    setWaveformData([]);
  }, []);

  const startRecording = useCallback(async () => {
    if (!isActive) return;

    try {
      setError(null);
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      streamRef.current = stream;

      const audioContext = new AudioContext();
      const source = audioContext.createMediaStreamSource(stream);
      const analyser = audioContext.createAnalyser();
      analyser.fftSize = 256;
      source.connect(analyser);
      analyserRef.current = analyser;

      const mediaRecorder = new MediaRecorder(stream);
      mediaRecorderRef.current = mediaRecorder;
      audioChunksRef.current = [];

      mediaRecorder.ondataavailable = (event) => {
        if (event.data.size > 0) {
          audioChunksRef.current.push(event.data);
        }
      };

      mediaRecorder.onstop = async () => {
        const audioBlob = new Blob(audioChunksRef.current, { type: "audio/webm" });
        audioChunksRef.current = [];

        // Send to backend for transcription
        setIsTranscribing(true);
        try {
          const formData = new FormData();
          formData.append("audio", audioBlob, "recording.webm");

          const response = await fetch(`http://${backendUrl}:8020/api/voice/stt`, {
            method: "POST",
            body: formData,
          });

          if (!response.ok) {
            throw new Error(`Transcription failed: ${response.status}`);
          }

          const data = await response.json();
          if (data.text && onTranscript) {
            onTranscript(data.text);
          }
        } catch (err) {
          console.error("Transcription error:", err);
          setError(err instanceof Error ? err.message : "Transcription failed");
        } finally {
          setIsTranscribing(false);
        }
      };

      mediaRecorder.start();
      setIsRecording(true);

      // Start waveform visualization
      const bufferLength = analyser.frequencyBinCount;
      const dataArray = new Uint8Array(bufferLength);

      const drawWaveform = () => {
        if (!analyserRef.current) return;

        analyserRef.current.getByteFrequencyData(dataArray);

        // Normalize to 0-100 range for display
        const normalized = Array.from(dataArray).map((value) => (value / 255) * 100);
        setWaveformData(normalized);

        animationFrameRef.current = requestAnimationFrame(drawWaveform);
      };

      drawWaveform();
    } catch (err) {
      console.error("Microphone access error:", err);
      setError("Microphone access denied or unavailable");
    }
  }, [isActive, backendUrl, onTranscript]);

  const toggleRecording = useCallback(() => {
    if (isRecording) {
      if (mediaRecorderRef.current && mediaRecorderRef.current.state !== "inactive") {
        mediaRecorderRef.current.stop();
      }
      stopRecording();
    } else {
      startRecording();
    }
  }, [isRecording, startRecording, stopRecording]);

  // Waveform visualization
  const waveformBars = 32;
  const barHeights = waveformData.slice(0, waveformBars).map((value) => Math.max(4, value));

  return (
    <div className="flex flex-col items-center gap-2">
      {/* Waveform visualization */}
      {isRecording && (
        <div className="flex items-center gap-0.5 h-8 px-2">
          {barHeights.map((height, i) => (
            <div
              key={i}
              className="w-1 bg-green-500 rounded-full transition-all duration-75"
              style={{ height: `${height}%` }}
            />
          ))}
        </div>
      )}

      {/* Error message */}
      {error && (
        <div className="text-xs text-red-400 px-2">{error}</div>
      )}

      {/* Record button */}
      <button
        onClick={toggleRecording}
        disabled={!isActive || isTranscribing}
        aria-label={isRecording ? "Stop recording" : isTranscribing ? "Transcribing..." : "Record voice"}
        className={`
          relative w-10 h-10 rounded-full flex items-center justify-center
          transition-all duration-200
          ${isRecording
            ? "bg-red-500 hover:bg-red-600 animate-pulse"
            : isTranscribing
              ? "bg-yellow-500 hover:bg-yellow-600"
              : "bg-gray-700 hover:bg-gray-600"
          }
          ${!isActive ? "opacity-50 cursor-not-allowed" : "cursor-pointer"}
        `}
        title={isRecording ? "Stop recording" : isTranscribing ? "Transcribing..." : "Record voice"}
      >
        {isTranscribing ? (
          <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="currentColor" className="w-5 h-5 text-white">
            <path d="M12 2a10 10 0 1 0 10 10A10 10 0 0 0 12 2Zm0 18a8 8 0 1 1 8-8 8 8 0 0 1-8 8Z" />
            <path d="M12 6a1 1 0 0 1 1 1v4a1 1 0 0 1-2 0V7a1 1 0 0 1 1-1Zm0 6a1 1 0 0 1 1 1v2a1 1 0 0 1-2 0v-2a1 1 0 0 1 1-1Z" />
          </svg>
        ) : (
          <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="currentColor" className="w-5 h-5 text-white">
            <path d="M12 14a3 3 0 0 0 3-3V5a3 3 0 0 0-6 0v6a3 3 0 0 0 3 3Zm-5-6a5 5 0 0 0 5 5 5 5 0 0 0 5-5V5a5 5 0 0 0-10 0v3Zm11 7a7 7 0 0 1-14 0H4a9 9 0 0 0 8 8.94V21a1 1 0 0 0 2 0v-2.06A9 9 0 0 0 20 15h-2Z" />
          </svg>
        )}
      </button>

      {/* Recording indicator */}
      {isRecording && (
        <div className="flex items-center gap-1 text-xs text-red-400">
          <div className="w-2 h-2 rounded-full bg-red-500 animate-pulse" />
          <span>Recording...</span>
        </div>
      )}
    </div>
  );
}
