"""
Edge-TTS streaming Text-to-Speech service.

Synthesizes text with Edge-TTS → saves MP3 → converts to PCM via ffmpeg
→ yields raw PCM bytes via callback.

Uses temp files instead of pipe-based subprocess to avoid Windows
asyncio.create_subprocess_exec issues with uvicorn --reload.
"""
import asyncio
import logging
import os
import subprocess
import tempfile
from typing import Callable, Awaitable, Optional

import edge_tts

import config

logger = logging.getLogger(__name__)


class TTSService:
    """
    Streams text to Edge-TTS, converts to PCM using ffmpeg,
    and provides chunks via a callback.
    """

    def __init__(
        self,
        on_audio: Callable[[bytes], Awaitable[None]],
        voice_id: Optional[str] = None,
    ) -> None:
        self._on_audio = on_audio
        self._voice_id = voice_id or config.EDGE_TTS_VOICE
        self._running = False
        self._text_buffer = ""
        self._loop = asyncio.get_running_loop()

        # Queue for sequential sentence processing
        self._queue: asyncio.Queue[Optional[str]] = asyncio.Queue()
        self._worker_task: Optional[asyncio.Task] = None

    def set_voice(self, voice_id: str) -> None:
        """Update the voice on the fly."""
        self._voice_id = voice_id
        logger.info(f"TTS voice changed to {voice_id}")

    async def start(self) -> None:
        self._running = True
        self._worker_task = asyncio.create_task(self._process_queue())
        logger.info("Edge-TTS connected (voice: %s)", self._voice_id)

    async def send_text(self, text: str) -> None:
        """Buffer text. We usually receive words/tokens."""
        if not self._running:
            return

        self._text_buffer += text

        # Chunking: trigger synthesis on punctuation
        if any(p in self._text_buffer for p in [".", "!", "?", "\n"]):
            text_to_speak = self._text_buffer.strip()
            self._text_buffer = ""
            if text_to_speak:
                await self._queue.put(text_to_speak)

    async def flush(self) -> None:
        """Flush the remaining text buffer to the queue."""
        if not self._running:
            return
        text_to_speak = self._text_buffer.strip()
        self._text_buffer = ""
        if text_to_speak:
            await self._queue.put(text_to_speak)

    async def _process_queue(self) -> None:
        """Background worker to process TTS sequentially to avoid interleaved audio."""
        while self._running:
            try:
                text = await self._queue.get()
                if text is None:  # Shutdown signal
                    break

                await self._synthesize_and_send(text)
                self._queue.task_done()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("TTS Worker Error: %s", e)

    def _ffmpeg_convert(self, mp3_path: str, pcm_path: str) -> bool:
        """Convert MP3 to raw PCM using ffmpeg (runs in thread pool)."""
        try:
            result = subprocess.run(
                [
                    "ffmpeg", "-y",
                    "-i", mp3_path,
                    "-f", "s16le",
                    "-ac", "1",
                    "-ar", "16000",
                    pcm_path,
                ],
                capture_output=True,
                timeout=15,
            )
            return result.returncode == 0
        except Exception as e:
            logger.error("ffmpeg conversion error: %s", e)
            return False

    async def _synthesize_and_send(self, text: str) -> None:
        """Synthesize text with Edge-TTS, convert via FFmpeg, send PCM chunks."""
        mp3_path = None
        pcm_path = None
        try:
            # 1. Generate MP3 with Edge-TTS into a temp file
            mp3_fd, mp3_path = tempfile.mkstemp(suffix=".mp3")
            os.close(mp3_fd)

            communicate = edge_tts.Communicate(text, self._voice_id, rate="+15%")
            await communicate.save(mp3_path)

            if not self._running:
                return

            # 2. Convert MP3 → PCM via ffmpeg in a thread
            pcm_fd, pcm_path = tempfile.mkstemp(suffix=".pcm")
            os.close(pcm_fd)

            success = await self._loop.run_in_executor(
                None, self._ffmpeg_convert, mp3_path, pcm_path
            )
            if not success or not self._running:
                return

            # 3. Read PCM file and send chunks to the frontend
            def _read_pcm():
                chunks = []
                with open(pcm_path, "rb") as f:
                    while True:
                        chunk = f.read(4096)
                        if not chunk:
                            break
                        chunks.append(chunk)
                return chunks

            pcm_chunks = await self._loop.run_in_executor(None, _read_pcm)

            for chunk in pcm_chunks:
                if not self._running:
                    break
                await self._on_audio(chunk)

        except Exception as e:
            logger.error("TTSService error: %s", e)
        finally:
            # Cleanup temp files
            for path in (mp3_path, pcm_path):
                if path:
                    try:
                        os.unlink(path)
                    except Exception:
                        pass

    async def stop(self) -> None:
        """Gracefully close the TTS service."""
        if not self._running:
            return

        self._running = False

        # Send shutdown signal to worker and wait
        await self._queue.put(None)
        if self._worker_task:
            try:
                await asyncio.wait_for(self._worker_task, timeout=2.0)
            except (asyncio.TimeoutError, asyncio.CancelledError):
                self._worker_task.cancel()

        logger.info("Edge-TTS disconnected")

