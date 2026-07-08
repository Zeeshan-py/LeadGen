"""Audio silence detection helpers for live AI SDR calls."""

from __future__ import annotations

from datetime import datetime, timezone

from ai_sdr.calling.interfaces import SpeechProvider


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class SilenceDetector:
    """Tracks speech/silence transitions for telephony audio frames."""

    def __init__(self, speech: SpeechProvider, *, timeout_seconds: float) -> None:
        self.speech = speech
        self.timeout_seconds = timeout_seconds
        self.last_voice_at: datetime | None = None
        self.in_utterance = False
        self._finalized_for_current_utterance = False

    def observe(self, audio: bytes) -> tuple[bool, bool]:
        """Observe one frame and return `(is_voice, should_finalize)`."""

        now = utc_now()
        is_voice = not self.speech.is_silence(audio)
        if is_voice:
            self.last_voice_at = now
            self.in_utterance = True
            self._finalized_for_current_utterance = False
            return True, False
        if not self.in_utterance or not self.last_voice_at or self._finalized_for_current_utterance:
            return False, False
        silence_seconds = (now - self.last_voice_at).total_seconds()
        if silence_seconds >= self.timeout_seconds:
            self._finalized_for_current_utterance = True
            self.in_utterance = False
            return False, True
        return False, False
