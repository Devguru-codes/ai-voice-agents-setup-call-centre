"""
Local streaming Speech-to-Text service using Faster Whisper.

Uses Voice Activity Detection (VAD) via basic RMS energy thresholding.
Buffers PCM audio and runs inference when silence is detected.
"""
import asyncio
import logging
import numpy as np
from typing import Callable, Awaitable, Optional
from faster_whisper import WhisperModel

import config

logger = logging.getLogger(__name__)

# Global model instance for fast reuse across calls
_whisper_model: Optional[WhisperModel] = None


def get_whisper_model():
    global _whisper_model
    if _whisper_model is None:
        # Force CPU to avoid cublas64_12.dll runtime errors on Windows
        # The CUDA error only surfaces during transcription, not model loading,
        # so we can't rely on a try/catch at load time.
        device = "cpu"
        compute_type = "int8"
        logger.info("Loading Whisper model (%s) on %s...", config.WHISPER_MODEL, device)
        _whisper_model = WhisperModel(
            config.WHISPER_MODEL,
            device=device,
            compute_type=compute_type,
            cpu_threads=4,
        )
        logger.info("Whisper model loaded successfully on %s.", device)
    return _whisper_model


class STTService:
    """
    Local STT using Faster Whisper.

    Usage:
        stt = STTService(on_final=my_callback)
        await stt.start()
        await stt.send_audio(pcm_bytes)
        ...
        await stt.stop()
    """

    def __init__(
        self,
        on_final: Callable[[str], Awaitable[None]],
        on_interim: Optional[Callable[[str], Awaitable[None]]] = None,
    ) -> None:
        self._on_final = on_final
        self._on_interim = on_interim
        self._running = False

        self._audio_buffer = bytearray()
        self._silence_threshold = 600  # RMS threshold — below this is "silence"
        self._speech_detected = False

        # 16kHz mono 16-bit: each frame = 2 bytes
        # Trigger transcription after 1.5s of consecutive silence
        # (0.8s was too aggressive — splits sentences mid-pause)
        self._silence_limit = int(16000 * 1.5)  # frames
        self._current_silence = 0

        # Minimum audio to bother transcribing (0.3s)
        self._min_audio_bytes = int(16000 * 0.3 * 2)

        # Maximum buffer before forcing transcription (10s) — safety valve
        self._max_audio_bytes = int(16000 * 10 * 2)

        # Transcription lock to prevent overlapping Whisper calls
        self._transcribing = False

        # RMS logging counter (log every ~2s to avoid spam)
        self._rms_log_counter = 0

    async def start(self) -> None:
        """Start the local STT service."""
        # Warm up the model
        get_whisper_model()
        self._running = True
        self._audio_buffer.clear()
        self._current_silence = 0
        self._speech_detected = False
        self._transcribing = False
        self._loop = asyncio.get_running_loop()
        logger.info("Local Faster-Whisper STT started")

    async def send_audio(self, pcm_bytes: bytes) -> None:
        """Process incoming PCM audio chunks."""
        if not self._running:
            return

        self._audio_buffer.extend(pcm_bytes)

        # Calculate RMS energy for VAD
        arr = np.frombuffer(pcm_bytes, dtype=np.int16)
        if len(arr) == 0:
            return

        rms = np.sqrt(np.mean(arr.astype(np.float32) ** 2))

        # Log RMS periodically for debugging (~every 2 seconds)
        self._rms_log_counter += 1
        if self._rms_log_counter % 16 == 0:
            buf_secs = len(self._audio_buffer) / (16000 * 2)
            logger.debug(
                "VAD: rms=%.0f threshold=%d speech=%s silence_frames=%d buf=%.1fs",
                rms, self._silence_threshold, self._speech_detected,
                self._current_silence, buf_secs,
            )

        if rms < self._silence_threshold:
            self._current_silence += len(arr)
        else:
            self._current_silence = 0
            self._speech_detected = True

        # Trigger transcription if:
        #   (a) Enough silence after speech, OR
        #   (b) Buffer hit the max cap (safety valve)
        silence_triggered = (
            self._current_silence > self._silence_limit
            and len(self._audio_buffer) >= self._min_audio_bytes
            and self._speech_detected
        )
        max_buffer_triggered = len(self._audio_buffer) >= self._max_audio_bytes

        if (silence_triggered or max_buffer_triggered) and not self._transcribing:
            audio_data = bytes(self._audio_buffer)
            self._audio_buffer.clear()
            self._current_silence = 0
            self._speech_detected = False
            self._transcribing = True

            asyncio.create_task(self._transcribe(audio_data))

    async def _transcribe(self, audio_bytes: bytes) -> None:
        """Run Whisper inference in a thread pool."""
        def _run():
            model = get_whisper_model()
            audio_arr = np.frombuffer(audio_bytes, dtype=np.int16).astype(np.float32) / 32768.0
            
            # Vocabulary hints help Whisper recognize domain-specific words
            # Without this, "ChatGPT" gets transcribed as "charging" or "chad GPT"
            vocab_prompt = (
                "ChatGPT, GPT-4, OpenAI, AI assistant, machine learning, "
                "schedule a meeting, book a call, support agent, sales agent, "
                "CRM, demo, onboarding"
            )
            
            # Use vad_filter to drop silent/noisy segments before transcription
            segments, _ = model.transcribe(
                audio_arr, 
                language="en", 
                beam_size=1,
                vad_filter=True,
                vad_parameters=dict(min_silence_duration_ms=500),
                initial_prompt=vocab_prompt,
            )
            
            raw_text = " ".join([segment.text for segment in segments]).strip()
            
            # Filter out common Whisper hallucinations (when it transcribes static)
            hallucinations = ["you", "thank you", "thank you.", "you.", "bye.", "bye", "ok", "okay"]
            if raw_text.strip().lower() in hallucinations:
                return ""
                
            return raw_text

        try:
            text = await self._loop.run_in_executor(None, _run)
            if text:
                logger.info("STT final: %s", text)
                await self._on_final(text)
            else:
                logger.debug("STT: empty transcription result (silence/noise)")
        except Exception as e:
            logger.error("Local Whisper transcription error: %s", e)
        finally:
            self._transcribing = False

    async def stop(self) -> None:
        """Stop the STT service."""
        self._running = False

        # Flush whatever is left in the buffer
        if len(self._audio_buffer) >= self._min_audio_bytes and self._speech_detected:
            audio_data = bytes(self._audio_buffer)
            self._audio_buffer.clear()
            await self._transcribe(audio_data)

        logger.info("Local STT disconnected")
