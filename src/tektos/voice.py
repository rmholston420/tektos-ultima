"""Tektos-Ultima v1 — Voice module (ears and voice).

Provides:
- Speech-to-text (STT) via faster-whisper (CPU, large-v3-turbo)
- Text-to-speech (TTS) via edge-tts (Microsoft Edge neural voices)
- Wake-word detection for "Tektos" using simple energy-based VAD + keyword spotting

Architecture:
  Mic → VAD → Wake-word → STT → Tektos → TTS → Speaker
"""

from __future__ import annotations

import asyncio
import io
import logging
import os
import wave
from dataclasses import dataclass, field
from pathlib import Path
from typing import AsyncGenerator

import edge_tts
import numpy as np
from faster_whisper import WhisperModel
from pydub import AudioSegment
from pydub.silence import split_on_silence

log = logging.getLogger("tektos.voice")

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

# Whisper model — CPU mode (GPU is full with llama-server)
_WHISPER_MODEL_NAME = os.getenv("TEKTOS_WHISPER_MODEL", "large-v3-turbo")
_WHISPER_DEVICE = os.getenv("TEKTOS_WHISPER_DEVICE", "cpu")
_WHISPER_COMPUTE_TYPE = os.getenv("TEKTOS_WHISPER_COMPUTE_TYPE", "float16")

# TTS voice — Microsoft Edge neural voice
# en-IN-PrabhatNeural: male Indian English — closest to a wise elder from NW India/Kashmir
_TTS_VOICE = os.getenv("TEKTOS_TTS_VOICE", "en-IN-PrabhatNeural")
# Slightly slower, measured pace for a wise/elderly tone
_TTS_RATE = os.getenv("TEKTOS_TTS_RATE", "-10%")

# Wake-word settings
_WAKE_WORD = "tektos"
_WAKE_WORD_SENSITIVITY = float(os.getenv("TEKTOS_WAKE_SENSITIVITY", "0.6"))

# Audio settings
_SAMPLE_RATE = 16000  # Hz for Whisper
_CHANNELS = 1
_SAMPLE_WIDTH = 2   # 16-bit


# ---------------------------------------------------------------------------
# STT — Speech-to-Text
# ---------------------------------------------------------------------------

class STTEngine:
    """Wraps faster-whisper for CPU transcription."""

    _model: WhisperModel | None = field(default=None)

    def __init__(self) -> None:
        self._model = None

    async def initialize(self) -> None:
        """Load the Whisper model (lazy, on first use)."""
        if self._model is not None:
            return
        log.info(
            "Loading Whisper %s on %s (%s) — this may take a moment…",
            _WHISPER_MODEL_NAME,
            _WHISPER_DEVICE,
            _WHISPER_COMPUTE_TYPE,
        )
        self._model = WhisperModel(
            _WHISPER_MODEL_NAME,
            device=_WHISPER_DEVICE,
            compute_type=_WHISPER_COMPUTE_TYPE,
            num_workers=4,
            cpu_threads=os.cpu_count() or 4,
        )
        log.info("Whisper model loaded successfully")

    async def transcribe(self, audio_bytes: bytes) -> str:
        """Transcribe audio bytes (WAV/MP3) to text."""
        await self.initialize()
        assert self._model is not None

        # Convert to temp file for faster-whisper
        tmp = Path("/tmp/tektos_stt_input.wav")
        audio = AudioSegment.from_file(io.BytesIO(audio_bytes))
        audio = audio.set_frame_rate(_SAMPLE_RATE).set_channels(_CHANNELS).set_sample_width(_SAMPLE_WIDTH)
        audio.export(str(tmp), format="wav")

        segments, info = self._model.transcribe(str(tmp), beam_size=5)
        text = " ".join(seg.text for seg in segments).strip()
        log.info("STT: detected language=%s, transcribed %d chars", info.language, len(text))
        return text


# ---------------------------------------------------------------------------
# TTS — Text-to-Speech
# ---------------------------------------------------------------------------

class TTSVoice:
    """Wraps edge-tts for neural voice synthesis."""

    async def synthesize(self, text: str) -> bytes:
        """Synthesize text to MP3 bytes."""
        log.debug("TTS: synthesizing %d chars", len(text))
        communicate = edge_tts.Communicate(text, _TTS_VOICE, rate=_TTS_RATE)
        audio_data = b""
        async for chunk in communicate.stream():
            if chunk.get("type") == "audio":
                audio_data += chunk.get("data", b"")
        log.debug("TTS: generated %d bytes", len(audio_data))
        return audio_data

    async def synthesize_stream(self, text: str) -> AsyncGenerator[bytes, None]:
        """Stream TTS audio chunks (for real-time playback)."""
        communicate = edge_tts.Communicate(text, _TTS_VOICE, rate=_TTS_RATE)
        async for chunk in communicate.stream():
            if chunk.get("type") == "audio":
                yield chunk.get("data", b"")


# ---------------------------------------------------------------------------
# VAD — Voice Activity Detection (simple energy-based)
# ---------------------------------------------------------------------------

class VoiceActivityDetector:
    """Simple energy-based VAD for wake-word detection."""

    def __init__(self, threshold: float = 0.01) -> None:
        self._threshold = threshold
        self._is_speaking = False

    def detect(self, audio_data: bytes) -> bool:
        """Return True if speech is detected in the audio chunk."""
        # Convert to numpy array (16-bit PCM)
        samples = np.frombuffer(audio_data, dtype=np.int16).astype(np.float64)
        # Normalize to [-1, 1]
        samples = samples / 32768.0
        # Compute RMS energy
        rms = np.sqrt(np.mean(samples ** 2))
        return rms > self._threshold


# ---------------------------------------------------------------------------
# Wake-Word Detection
# ---------------------------------------------------------------------------

class WakeWordDetector:
    """Simple keyword spotting for 'Tektos' in transcribed text."""

    def __init__(self, sensitivity: float = 0.6) -> None:
        self._sensitivity = sensitivity

    def check(self, text: str) -> bool:
        """Check if the wake word is in the text."""
        lower = text.lower().strip()
        # Check for "tektos" as a word boundary match
        import re
        pattern = r'\b' + _WAKE_WORD + r'\b'
        return bool(re.search(pattern, lower))


# ---------------------------------------------------------------------------
# VoiceManager — orchestrates STT, TTS, and wake-word
# ---------------------------------------------------------------------------

@dataclass
class VoiceState:
    """Current voice interaction state."""
    is_listening: bool = False
    is_speaking: bool = False
    is_wake_word_detected: bool = False
    last_transcript: str = ""
    last_tts_text: str = ""


class VoiceManager:
    """Central voice coordinator."""

    def __init__(self) -> None:
        self.stt = STTEngine()
        self.tts = TTSVoice()
        self.vad = VoiceActivityDetector()
        self.wake_word = WakeWordDetector(_WAKE_WORD_SENSITIVITY)
        self.state = VoiceState()

    async def initialize(self) -> None:
        """Initialize all voice components."""
        await self.stt.initialize()
        log.info("Voice system initialized (STT: %s, TTS: %s)", _WHISPER_MODEL_NAME, _TTS_VOICE)

    async def transcribe(self, audio_bytes: bytes) -> str:
        """Transcribe audio and check for wake word."""
        self.state.is_listening = True
        try:
            text = await self.stt.transcribe(audio_bytes)
            self.state.last_transcript = text
            self.state.is_wake_word_detected = self.wake_word.check(text)
            return text
        finally:
            self.state.is_listening = False

    async def speak(self, text: str) -> bytes:
        """Synthesize text to audio."""
        self.state.is_speaking = True
        try:
            self.state.last_tts_text = text
            return await self.tts.synthesize(text)
        finally:
            self.state.is_speaking = False

    async def speak_stream(self, text: str) -> AsyncGenerator[bytes, None]:
        """Stream TTS audio for real-time playback."""
        self.state.is_speaking = True
        try:
            self.state.last_tts_text = text
            async for chunk in self.tts.synthesize_stream(text):
                yield chunk
        finally:
            self.state.is_speaking = False

    def get_state(self) -> dict:
        """Return current voice state as dict."""
        return {
            "is_listening": self.state.is_listening,
            "is_speaking": self.state.is_speaking,
            "is_wake_word_detected": self.state.is_wake_word_detected,
            "last_transcript": self.state.last_transcript,
            "last_tts_text": self.state.last_tts_text,
        }


# ---------------------------------------------------------------------------
# Singleton instance
# ---------------------------------------------------------------------------

_voice_manager: VoiceManager | None = None


def get_voice_manager() -> VoiceManager:
    """Get or create the global VoiceManager singleton."""
    global _voice_manager
    if _voice_manager is None:
        _voice_manager = VoiceManager()
    return _voice_manager