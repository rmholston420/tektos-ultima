"""Tests for Tektos voice module (STT, TTS, wake-word)."""

import io
import json
import os
import sys
import wave
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))


# ---------------------------------------------------------------------------
# STT Engine Tests
# ---------------------------------------------------------------------------

class TestSTTEngine:
    """Tests for the STTEngine class."""

    @pytest.mark.asyncio
    async def test_initialize_lazy_loads_model(self):
        """Test that model is loaded on first transcribe call."""
        from tektos.voice import STTEngine

        with patch("tektos.voice.WhisperModel") as MockWhisper:
            mock_model = MagicMock()
            MockWhisper.return_value = mock_model

            engine = STTEngine()
            assert engine._model is None

            await engine.initialize()
            MockWhisper.assert_called_once()
            assert engine._model is not None

    @pytest.mark.asyncio
    async def test_transcribe_calls_whisper(self):
        """Test that transcribe passes audio to Whisper."""
        from tektos.voice import STTEngine

        engine = STTEngine()

        with patch.object(engine, "initialize", new_callable=AsyncMock):
            mock_model = MagicMock()
            mock_segments = [MagicMock(text="hello world")]
            mock_info = MagicMock(language="en")
            mock_model.transcribe.return_value = (mock_segments, mock_info)
            engine._model = mock_model

            wav_bytes = self._create_dummy_wav()
            text = await engine.transcribe(wav_bytes)

            assert text == "hello world"
            mock_model.transcribe.assert_called_once()

    @staticmethod
    def _create_dummy_wav(duration_sec=1.0, sample_rate=16000):
        """Create a simple WAV file in memory."""
        buf = io.BytesIO()
        with wave.open(buf, "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(sample_rate)
            # Write silence
            samples = b"\x00\x00" * int(sample_rate * duration_sec)
            wf.writeframes(samples)
        buf.seek(0)
        return buf.read()


# ---------------------------------------------------------------------------
# TTS Voice Tests
# ---------------------------------------------------------------------------

class TestTTSVoice:
    """Tests for the TTSVoice class."""

    @pytest.mark.asyncio
    async def test_synthesize_returns_bytes(self):
        """Test that synthesize returns MP3 bytes."""
        from tektos.voice import TTSVoice

        tts = TTSVoice()

        async def mock_stream():
            yield {"type": "audio", "data": b"\x00\x01\x02\x03"}

        with patch("tektos.voice.edge_tts.Communicate") as MockComm:
            mock_comm = MagicMock()
            mock_comm.stream = mock_stream
            MockComm.return_value = mock_comm

            audio = await tts.synthesize("test text")
            assert isinstance(audio, bytes)
            assert len(audio) > 0

    @pytest.mark.asyncio
    async def test_synthesize_stream_yields_chunks(self):
        """Test that synthesize_stream yields audio chunks."""
        from tektos.voice import TTSVoice

        tts = TTSVoice()

        async def mock_stream():
            yield {"type": "audio", "data": b"\x00\x01"}
            yield {"type": "audio", "data": b"\x02\x03"}

        with patch("tektos.voice.edge_tts.Communicate") as MockComm:
            mock_comm = MagicMock()
            mock_comm.stream = mock_stream
            MockComm.return_value = mock_comm

            chunks = []
            async for chunk in tts.synthesize_stream("test"):
                chunks.append(chunk)

            assert len(chunks) == 2
            assert b"\x00\x01" in chunks
            assert b"\x02\x03" in chunks


# ---------------------------------------------------------------------------
# VAD Tests
# ---------------------------------------------------------------------------

class TestVoiceActivityDetector:
    """Tests for the VoiceActivityDetector class."""

    def test_detect_silence(self):
        """Test that silence returns False."""
        from tektos.voice import VoiceActivityDetector

        vad = VoiceActivityDetector(threshold=0.01)
        silence = b"\x00\x00" * 100  # 16-bit silence
        result = vad.detect(silence)
        assert result is False or result == False

    def test_detect_speech(self):
        """Test that speech returns True."""
        from tektos.voice import VoiceActivityDetector

        vad = VoiceActivityDetector(threshold=0.01)
        # Create a simple sine wave pattern
        import numpy as np
        samples = np.sin(np.linspace(0, 100, 200)).astype(np.float32)
        audio = (samples * 10000).astype(np.int16).tobytes()
        result = vad.detect(audio)
        assert result is True or result == True


# ---------------------------------------------------------------------------
# Wake-Word Detector Tests
# ---------------------------------------------------------------------------

class TestWakeWordDetector:
    """Tests for the WakeWordDetector class."""

    def test_detects_wake_word(self):
        """Test that wake word is detected."""
        from tektos.voice import WakeWordDetector

        detector = WakeWordDetector()
        assert detector.check("Tektos, what time is it?") is True
        assert detector.check("tektos, help me") is True
        assert detector.check("TEKTOS!") is True

    def test_no_false_positive(self):
        """Test that similar words don't trigger."""
        from tektos.voice import WakeWordDetector

        detector = WakeWordDetector()
        assert detector.check("Hello, how are you?") is False
        assert detector.check("The text is long") is False  # "text" != "tektos"
        assert detector.check("I like totes") is False  # "totes" != "tektos"


# ---------------------------------------------------------------------------
# VoiceManager Tests
# ---------------------------------------------------------------------------

class TestVoiceManager:
    """Tests for the VoiceManager class."""

    @pytest.mark.asyncio
    async def test_get_state_returns_dict(self):
        """Test that get_state returns a dict with expected keys."""
        from tektos.voice import VoiceManager

        manager = VoiceManager()
        state = manager.get_state()

        assert isinstance(state, dict)
        assert "is_listening" in state
        assert "is_speaking" in state
        assert "is_wake_word_detected" in state
        assert "last_transcript" in state
        assert "last_tts_text" in state

    @pytest.mark.asyncio
    async def test_transcribe_sets_wake_word(self):
        """Test that transcribe checks for wake word."""
        from tektos.voice import VoiceManager

        manager = VoiceManager()

        with patch.object(manager.stt, "initialize", new_callable=AsyncMock):
            mock_model = MagicMock()
            mock_segments = [MagicMock(text="Tektos, help me")]
            mock_info = MagicMock(language="en")
            mock_model.transcribe.return_value = (mock_segments, mock_info)
            manager.stt._model = mock_model

            wav_bytes = TestSTTEngine._create_dummy_wav()
            text = await manager.transcribe(wav_bytes)

            assert text == "Tektos, help me"
            assert manager.state.is_wake_word_detected is True

    @pytest.mark.asyncio
    async def test_speak_calls_tts(self):
        """Test that speak calls TTS."""
        from tektos.voice import VoiceManager

        manager = VoiceManager()

        async def mock_synthesize(text):
            # Check state during synthesis
            assert manager.state.is_speaking is True
            assert manager.state.last_tts_text == "hello world"
            return b"\x00\x01\x02\x03"

        with patch.object(manager.tts, "synthesize", mock_synthesize):
            audio = await manager.speak("hello world")

            assert audio == b"\x00\x01\x02\x03"
            # is_speaking is reset in finally block, so check last_tts_text instead
            assert manager.state.last_tts_text == "hello world"


# ---------------------------------------------------------------------------
# Singleton Tests
# ---------------------------------------------------------------------------

class TestVoiceManagerSingleton:
    """Tests for the get_voice_manager singleton."""

    def test_singleton_returns_same_instance(self):
        """Test that get_voice_manager returns the same instance."""
        from tektos.voice import get_voice_manager

        manager1 = get_voice_manager()
        manager2 = get_voice_manager()

        assert manager1 is manager2
