"""Tests for voice.py — STTEngine, TTSVoice, VoiceActivityDetector, WakeWordDetector, VoiceManager."""

import asyncio
import io
import tempfile
import wave
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from tektos.voice import (
    STTEngine,
    TTSVoice,
    VoiceActivityDetector,
    WakeWordDetector,
    VoiceManager,
    VoiceState,
    get_voice_manager,
)


class TestVoiceState:
    """Tests for VoiceState dataclass."""

    def test_default_state(self):
        state = VoiceState()
        assert state.is_listening is False
        assert state.is_speaking is False
        assert state.is_wake_word_detected is False
        assert state.last_transcript == ""
        assert state.last_tts_text == ""

    def test_update_state(self):
        state = VoiceState(
            is_listening=True,
            is_speaking=True,
            is_wake_word_detected=True,
            last_transcript="hello tektos",
            last_tts_text="Hello there",
        )
        assert state.is_listening is True
        assert state.is_wake_word_detected is True
        assert state.last_transcript == "hello tektos"


class TestVoiceActivityDetector:
    """Tests for VoiceActivityDetector."""

    def test_detect_silence(self):
        vad = VoiceActivityDetector(threshold=0.01)
        # All zeros = silence
        import numpy as np
        silence = np.zeros(100, dtype=np.int16).tobytes()
        assert vad.detect(silence) == False

    def test_detect_speech(self):
        vad = VoiceActivityDetector(threshold=0.01)
        # High amplitude = speech
        import numpy as np
        samples = np.array([32767] * 100, dtype=np.int16)
        assert vad.detect(samples.tobytes()) == True

    def test_detect_low_volume(self):
        vad = VoiceActivityDetector(threshold=0.01)
        # Low amplitude = below threshold
        import numpy as np
        samples = np.array([100] * 100, dtype=np.int16)
        assert vad.detect(samples.tobytes()) == False

    def test_detect_high_volume(self):
        vad = VoiceActivityDetector(threshold=0.01)
        import numpy as np
        samples = np.array([16000] * 100, dtype=np.int16)
        assert vad.detect(samples.tobytes()) == True

    def test_custom_threshold(self):
        vad = VoiceActivityDetector(threshold=0.5)
        import numpy as np
        samples = np.array([1000] * 100, dtype=np.int16)
        assert vad.detect(samples.tobytes()) == False


class TestWakeWordDetector:
    """Tests for WakeWordDetector."""

    def test_wake_word_present(self):
        detector = WakeWordDetector()
        assert detector.check("tektos, what time is it?") is True
        assert detector.check("Hey tektos, run the tests") is True
        assert detector.check("TEKTOS, stop") is True

    def test_wake_word_absent(self):
        detector = WakeWordDetector()
        assert detector.check("hello world") is False
        assert detector.check("what is the weather") is False
        assert detector.check("tektos is great") is True  # "tektos" is a word

    def test_wake_word_partial_match(self):
        detector = WakeWordDetector()
        # "tektos" should match as a word boundary
        assert detector.check("tektos") is True
        assert detector.check("tektos.") is True
        assert detector.check("tektos!") is True

    def test_wake_word_not_a_word(self):
        detector = WakeWordDetector()
        # "tektos" should NOT match inside another word
        assert detector.check("tektosify") is False
        assert detector.check("mytektos") is False

    def test_custom_sensitivity(self):
        detector = WakeWordDetector(sensitivity=0.9)
        assert detector.check("tektos, run") is True


class TestSTTEngine:
    """Tests for STTEngine."""

    def test_init(self):
        stt = STTEngine()
        assert stt._model is None

    @pytest.mark.asyncio
    async def test_initialize_lazy(self):
        stt = STTEngine()
        assert stt._model is None

        with patch("tektos.voice.WhisperModel") as mock_whisper:
            mock_whisper.return_value = MagicMock()
            await stt.initialize()
            assert stt._model is not None
            mock_whisper.assert_called_once()

    @pytest.mark.asyncio
    async def test_initialize_already_loaded(self):
        stt = STTEngine()
        stt._model = MagicMock()

        with patch("tektos.voice.WhisperModel") as mock_whisper:
            await stt.initialize()
            mock_whisper.assert_not_called()  # Should not reload

    @pytest.mark.asyncio
    async def test_transcribe(self):
        stt = STTEngine()

        with patch("tektos.voice.WhisperModel") as mock_whisper:
            mock_model = MagicMock()
            mock_segment = MagicMock()
            mock_segment.text = "hello world"
            mock_model.transcribe.return_value = ([mock_segment], MagicMock(language="en"))
            mock_whisper.return_value = mock_model
            stt._model = mock_model

            # Create a minimal WAV file
            wav_buffer = io.BytesIO()
            with wave.open(wav_buffer, "wb") as wf:
                wf.setnchannels(1)
                wf.setsampwidth(2)
                wf.setframerate(16000)
                wf.writeframes(b"\x00\x00" * 100)

            text = await stt.transcribe(wav_buffer.getvalue())
            assert text == "hello world"


class TestTTSVoice:
    """Tests for TTSVoice."""

    @pytest.mark.asyncio
    async def test_synthesize(self):
        tts = TTSVoice()

        async def mock_stream():
            yield {"type": "audio", "data": b"fake_audio_data"}

        with patch("tektos.voice.edge_tts.Communicate") as mock_comm:
            mock_comm.return_value = MagicMock(stream=mock_stream)

            audio = await tts.synthesize("hello world")
            assert audio == b"fake_audio_data"

    @pytest.mark.asyncio
    async def test_synthesize_stream(self):
        tts = TTSVoice()

        async def mock_stream():
            yield {"type": "audio", "data": b"chunk1"}
            yield {"type": "audio", "data": b"chunk2"}

        with patch("tektos.voice.edge_tts.Communicate") as mock_comm:
            mock_comm.return_value = MagicMock(stream=mock_stream)

            chunks = []
            async for chunk in tts.synthesize_stream("hello"):
                chunks.append(chunk)
            assert len(chunks) == 2
            assert chunks[0] == b"chunk1"
            assert chunks[1] == b"chunk2"


class TestVoiceManager:
    """Tests for VoiceManager."""

    def test_init(self):
        vm = VoiceManager()
        assert vm.stt is not None
        assert vm.tts is not None
        assert vm.vad is not None
        assert vm.wake_word is not None
        assert vm.state is not None

    def test_get_state(self):
        vm = VoiceManager()
        state = vm.get_state()
        assert state["is_listening"] is False
        assert state["is_speaking"] is False
        assert state["is_wake_word_detected"] is False
        assert state["last_transcript"] == ""
        assert state["last_tts_text"] == ""

    @pytest.mark.asyncio
    async def test_speak(self):
        vm = VoiceManager()

        with patch.object(vm.tts, "synthesize", return_value=b"audio") as mock_synthesize:
            audio = await vm.speak("hello")
            assert audio == b"audio"
            mock_synthesize.assert_called_once_with("hello")
            assert vm.state.is_speaking is False  # Reset after speak

    @pytest.mark.asyncio
    async def test_speak_stream(self):
        vm = VoiceManager()

        async def mock_stream(text):
            yield b"chunk1"
            yield b"chunk2"

        with patch.object(vm.tts, "synthesize_stream", mock_stream):
            chunks = []
            async for chunk in vm.speak_stream("hello"):
                chunks.append(chunk)
            assert len(chunks) == 2
            assert vm.state.is_speaking is False

    @pytest.mark.asyncio
    async def test_transcribe(self):
        vm = VoiceManager()

        with patch.object(vm.stt, "transcribe", return_value="hello tektos") as mock_transcribe:
            text = await vm.transcribe(b"audio")
            assert text == "hello tektos"
            assert vm.state.last_transcript == "hello tektos"
            assert vm.state.is_listening is False  # Reset after transcribe

    @pytest.mark.asyncio
    async def test_transcribe_wake_word(self):
        vm = VoiceManager()

        with patch.object(vm.stt, "transcribe", return_value="tektos run tests") as mock_transcribe:
            text = await vm.transcribe(b"audio")
            assert vm.state.is_wake_word_detected is True

    @pytest.mark.asyncio
    async def test_transcribe_no_wake_word(self):
        vm = VoiceManager()

        with patch.object(vm.stt, "transcribe", return_value="hello world") as mock_transcribe:
            text = await vm.transcribe(b"audio")
            assert vm.state.is_wake_word_detected is False

    @pytest.mark.asyncio
    async def test_initialize(self):
        vm = VoiceManager()

        with patch.object(vm.stt, "initialize") as mock_init:
            await vm.initialize()
            mock_init.assert_called_once()


class TestGetVoiceManager:
    """Tests for get_voice_manager singleton."""

    def test_singleton(self):
        vm1 = get_voice_manager()
        vm2 = get_voice_manager()
        assert vm1 is vm2
