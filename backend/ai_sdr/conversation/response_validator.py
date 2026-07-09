"""Validation helpers for spoken AI SDR responses."""

from __future__ import annotations

import re


MAX_SPOKEN_WORDS = 40
MAX_SENTENCES = 3


class ResponseValidator:
    """Keeps live call responses short, plain, and speakable."""

    def __init__(self, *, max_words: int = MAX_SPOKEN_WORDS, max_sentences: int = MAX_SENTENCES) -> None:
        self.max_words = max_words
        self.max_sentences = max_sentences

    def validate(self, text: str, *, fallback: str = "Can I ask one quick question?") -> str:
        cleaned = self._plain_text(text) or fallback
        cleaned = self._limit_sentences(cleaned)
        cleaned = self._limit_words(cleaned)
        return cleaned.strip() or fallback

    def word_count(self, text: str) -> int:
        return len(re.findall(r"\b[\w']+\b", text))

    @staticmethod
    def sentence_count(text: str) -> int:
        return len([part for part in re.split(r"(?<=[.!?])\s+", text.strip()) if part.strip()])

    @staticmethod
    def _plain_text(text: str) -> str:
        lines: list[str] = []
        for line in str(text or "").replace("\r", "\n").split("\n"):
            line = re.sub(r"^\s*[-*+]\s+", "", line)
            line = re.sub(r"^\s*\d+[.)]\s+", "", line)
            lines.append(line.strip())
        cleaned = " ".join(line for line in lines if line)
        cleaned = re.sub(r"[*_`#>\[\]{}]", "", cleaned)
        return re.sub(r"\s+", " ", cleaned).strip()

    def _limit_sentences(self, text: str) -> str:
        sentences = [part.strip() for part in re.split(r"(?<=[.!?])\s+", text) if part.strip()]
        if not sentences:
            return text
        return " ".join(sentences[: self.max_sentences])

    def _limit_words(self, text: str) -> str:
        tokens = re.findall(r"\S+", text)
        if len(tokens) <= self.max_words:
            return text
        shortened = " ".join(tokens[: self.max_words]).rstrip(",;:")
        if shortened[-1:] not in ".!?":
            shortened += "."
        return shortened
