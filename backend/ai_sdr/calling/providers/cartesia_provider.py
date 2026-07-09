"""Cartesia speech provider for AI SDR speech recognition and synthesis."""

from __future__ import annotations

import asyncio
import json
import math
import threading
from collections.abc import AsyncIterator
from typing import Any
from urllib.parse import urlencode

from ai_sdr.calling.interfaces import (
    ProviderConfigurationError,
    SpeechProvider,
    SpeechRecognitionSession,
    TranscriptSegment,
)
from ai_sdr.config import AISDRSettings


class CartesiaSpeechProvider(SpeechProvider):
    """Cartesia implementation of speech recognition, TTS, and silence checks."""

    name = "cartesia"

    def __init__(self, settings: AISDRSettings) -> None:
        self.settings = settings

    async def create_recognition_session(self, *, call_id: str) -> SpeechRecognitionSession:
        if not self.settings.cartesia_api_key:
            raise ProviderConfigurationError("Cartesia speech provider requires CARTESIA_API_KEY.")
        session = CartesiaRecognitionSession(self.settings, call_id=call_id)
        await session.connect()
        return session

    async def synthesize_stream(self, *, text: str, call_id: str) -> AsyncIterator[bytes]:
        if not self.settings.cartesia_api_key or not self.settings.cartesia_voice_id:
            raise ProviderConfigurationError(
                "Cartesia synthesis requires CARTESIA_API_KEY and CARTESIA_VOICE_ID."
            )

        loop = asyncio.get_running_loop()
        queue: asyncio.Queue[bytes | BaseException | None] = asyncio.Queue()

        def worker() -> None:
            try:
                for chunk in self._synthesize_sync(text):
                    loop.call_soon_threadsafe(queue.put_nowait, chunk)
            except BaseException as exc:
                loop.call_soon_threadsafe(queue.put_nowait, exc)
            finally:
                loop.call_soon_threadsafe(queue.put_nowait, None)

        threading.Thread(target=worker, name=f"cartesia-tts-{call_id}", daemon=True).start()
        while True:
            item = await queue.get()
            if item is None:
                break
            if isinstance(item, BaseException):
                raise item
            yield item

    def is_silence(self, audio: bytes) -> bool:
        if not audio:
            return True
        if self.settings.cartesia_stt_encoding == "pcm_mulaw":
            return self._mulaw_rms(audio) < 0.03
        values = [abs(byte - 128) for byte in audio[:320]]
        return (sum(values) / max(1, len(values))) < 4

    def _synthesize_sync(self, text: str) -> list[bytes]:
        try:
            from cartesia import Cartesia
        except ImportError as exc:
            raise ProviderConfigurationError(
                "Cartesia provider selected but cartesia[websockets] is not installed."
            ) from exc

        client = Cartesia(
            api_key=self.settings.cartesia_api_key,
            default_headers={"cartesia-version": self.settings.cartesia_version},
        )
        output_format = {
            "container": "raw",
            "encoding": self.settings.cartesia_tts_encoding,
            "sample_rate": self.settings.cartesia_tts_sample_rate,
        }
        chunks: list[bytes] = []
        with client.tts.websocket_connect() as websocket:
            context = websocket.context(
                model_id=self.settings.cartesia_tts_model,
                voice={"mode": "id", "id": self.settings.cartesia_voice_id},
                output_format=output_format,
            )
            context.push(text)
            context.no_more_inputs()
            for event in context.receive():
                audio = getattr(event, "audio", None)
                if getattr(event, "type", "") == "chunk" and audio:
                    chunks.append(audio)
        return chunks

    @staticmethod
    def _mulaw_rms(audio: bytes) -> float:
        if not audio:
            return 0.0
        total = 0.0
        for byte in audio:
            sample = _decode_mulaw(byte) / 32768.0
            total += sample * sample
        return math.sqrt(total / len(audio))


class CartesiaRecognitionSession(SpeechRecognitionSession):
    """Streaming Cartesia STT session backed by a provider WebSocket."""

    def __init__(self, settings: AISDRSettings, *, call_id: str) -> None:
        self.settings = settings
        self.call_id = call_id
        self._websocket: Any | None = None
        self._queue: asyncio.Queue[TranscriptSegment | None] = asyncio.Queue()
        self._receiver_task: asyncio.Task[None] | None = None
        self._closed = False

    async def connect(self) -> None:
        try:
            import websockets
        except ImportError as exc:
            raise ProviderConfigurationError(
                "Cartesia streaming recognition requires the websockets package."
            ) from exc

        query = urlencode(
            {
                "model": self.settings.cartesia_stt_model,
                "encoding": self.settings.cartesia_stt_encoding,
                "sample_rate": self.settings.cartesia_stt_sample_rate,
                "cartesia_version": self.settings.cartesia_version,
            }
        )
        headers = {
            "X-API-Key": self.settings.cartesia_api_key,
            "Cartesia-Version": self.settings.cartesia_version,
        }
        self._websocket = await websockets.connect(
            f"{self.settings.cartesia_stt_ws_url}?{query}",
            additional_headers=headers,
        )
        self._receiver_task = asyncio.create_task(self._receive_loop())

    async def send_audio(self, audio: bytes) -> None:
        if self._closed or self._websocket is None:
            return
        await self._websocket.send(audio)

    async def receive_segments(self) -> AsyncIterator[TranscriptSegment]:
        while not self._closed:
            segment = await self._queue.get()
            if segment is None:
                break
            yield segment

    async def finalize_utterance(self) -> None:
        if self._closed or self._websocket is None:
            return
        await self._websocket.send(json.dumps({"type": "finalize"}))

    async def close(self) -> None:
        self._closed = True
        if self._websocket is not None:
            await self._websocket.close()
        if self._receiver_task:
            self._receiver_task.cancel()
        await self._queue.put(None)

    async def _receive_loop(self) -> None:
        assert self._websocket is not None
        try:
            async for message in self._websocket:
                payload = self._parse_message(message)
                text = str(
                    payload.get("text")
                    or payload.get("transcript")
                    or payload.get("final")
                    or payload.get("partial")
                    or ""
                ).strip()
                if not text:
                    continue
                is_final = bool(payload.get("is_final") or payload.get("final") or payload.get("type") == "final")
                confidence = payload.get("confidence")
                await self._queue.put(
                    TranscriptSegment(
                        role="customer",
                        text=text,
                        is_final=is_final,
                        confidence=float(confidence) if confidence is not None else None,
                        provider_event_id=str(payload.get("id") or ""),
                        raw=payload,
                    )
                )
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            await self._queue.put(
                TranscriptSegment(
                    role="system",
                    text=f"Cartesia recognition stream closed: {exc}",
                    is_final=True,
                    raw={"error": str(exc)},
                )
            )
        finally:
            await self._queue.put(None)

    @staticmethod
    def _parse_message(message: Any) -> dict[str, Any]:
        if isinstance(message, bytes):
            try:
                message = message.decode("utf-8")
            except UnicodeDecodeError:
                return {}
        if isinstance(message, str):
            try:
                value = json.loads(message)
            except json.JSONDecodeError:
                return {"text": message}
            return value if isinstance(value, dict) else {}
        return {}


def _decode_mulaw(byte: int) -> int:
    mu_law = ~byte & 0xFF
    sign = mu_law & 0x80
    exponent = (mu_law >> 4) & 0x07
    mantissa = mu_law & 0x0F
    sample = ((mantissa << 3) + 0x84) << exponent
    sample -= 0x84
    return -sample if sign else sample
