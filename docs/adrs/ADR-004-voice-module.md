# ADR-004: Voice Module (Ears and Voice)

**Status:** Accepted  
**Date:** 2026-08-24  
**Deciders:** Karl (rmholston)

## Context

Tektos needed the ability to interact with users through voice — both to listen (speech-to-text) and to speak (text-to-speech). This would enable a more natural, JARVIS-like interaction model.

## Decision

We implemented a voice module with the following components:

### Backend (Python/FastAPI)
- **STT (Speech-to-Text):** Uses `faster-whisper` with the `large-v3-turbo` model running on CPU (GPU is occupied by llama-server)
- **TTS (Text-to-Speech):** Uses `edge-tts` (Microsoft Edge neural voices, free, no API keys)
- **Wake-word detection:** Simple keyword spotting for "Tektos" in transcribed text
- **VoiceManager singleton:** Orchestrates STT, TTS, and wake-word detection

### Frontend (Next.js/React)
- **MicButton:** Records audio from the microphone using Web Audio API, displays real-time waveform visualization, sends audio to backend for transcription
- **TTSPlayer:** Plays TTS audio responses, supports auto-play when assistant responds
- **Integration:** MicButton wired into the Composer component, voice transcript triggers message send

### API Endpoints
- `GET /api/voice/state` — Returns current voice system state
- `POST /api/voice/stt` — Transcribes audio to text (multipart form with 'audio' file)
- `POST /api/voice/tts` — Synthesizes text to speech (JSON body with 'text' field, returns MP3 stream)

## Consequences

### Positive
- Natural voice interaction with Tektos
- Real-time waveform visualization provides feedback during recording
- Wake-word detection enables hands-free interaction
- Free TTS (edge-tts) with no API key requirements
- CPU-based STT works well with 16-core system

### Negative
- Whisper on CPU is slower than GPU (but acceptable for interactive use)
- edge-tts requires internet connection (Microsoft Edge TTS service)
- Wake-word detection is simple keyword spotting (not robust to accents/background noise)
- No streaming TTS yet (full text is synthesized before playback)

### Future Improvements
- GPU-accelerated Whisper (requires freeing GPU VRAM or using smaller model)
- Streaming TTS for real-time playback
- More robust wake-word detection (e.g., Porcupine or Snowboy)
- Voice activity detection (VAD) for automatic recording start/stop
- Multiple TTS voice options
- TTS volume/pitch/rate controls

## Alternatives Considered

1. **OpenAI Whisper API:** Cloud-based, higher accuracy, but per-minute cost and requires internet
2. **Coqui TTS:** Fully local TTS, but heavier and more complex to set up
3. **Google Cloud TTS:** High quality, but requires API key and has costs
4. **Piper TTS:** Fully local, fast, but lower quality than edge-tts

## Implementation Details

### Files Created
- `src/tektos/voice.py` — Voice module (STT, TTS, wake-word, VAD)
- `frontend/src/components/composer/MicButton.tsx` — Mic button with waveform
- `frontend/src/components/composer/TTSPlayer.tsx` — TTS audio player
- `tests/test_voice.py` — Backend tests for voice module
- `frontend/src/components/composer/__tests__/MicButton.test.tsx` — Frontend tests

### Dependencies Added
- `faster-whisper` — Whisper speech recognition (CPU)
- `edge-tts` — Microsoft Edge TTS (free)
- `pydub` — Audio processing

### Configuration
- `TEKTOS_WHISPER_MODEL` — Whisper model name (default: `large-v3-turbo`)
- `TEKTOS_WHISPER_DEVICE` — Device for Whisper (default: `cpu`)
- `TEKTOS_WHISPER_COMPUTE_TYPE` — Compute type (default: `float16`)
- `TEKTOS_TTS_VOICE` — TTS voice name (default: `en-IN-PrabhatNeural`, male Indian English)
- `TEKTOS_TTS_RATE` — TTS speech rate (default: `-10%`, slightly slower for measured delivery)
- `TEKTOS_WAKE_SENSITIVITY` — Wake-word sensitivity (default: `0.6`)
