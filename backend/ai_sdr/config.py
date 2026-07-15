"""Configuration owned by the independent AI SDR module."""

from __future__ import annotations

from functools import lru_cache
from urllib.parse import urlencode, urlsplit

from pydantic import AliasChoices, Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class AISDRSettings(BaseSettings):
    """Configuration owned by the AI SDR module."""

    model_config = SettingsConfigDict(
        env_file=(".env", "../.env"),
        env_file_encoding="utf-8",
        extra="ignore",
        populate_by_name=True,
    )

    enabled: bool = Field(default=True, validation_alias="AI_SDR_ENABLED")
    api_prefix: str = Field(default="/ai-sdr", validation_alias="AI_SDR_API_PREFIX")
    default_actor: str = Field(default="LeadForge AI SDR", validation_alias="AI_SDR_DEFAULT_ACTOR")
    max_contacts_per_import: int = Field(
        default=1000,
        ge=1,
        le=10_000,
        validation_alias="AI_SDR_MAX_CONTACTS_PER_IMPORT",
    )
    store_raw_payloads: bool = Field(default=True, validation_alias="AI_SDR_STORE_RAW_PAYLOADS")
    default_crm_stage: str = Field(default="new", validation_alias="AI_SDR_DEFAULT_CRM_STAGE")
    environment: str = Field(default="development", validation_alias="ENVIRONMENT")
    calling_enabled: bool = Field(default=True, validation_alias="AI_SDR_CALLING_ENABLED")
    calling_mode: str = Field(default="production", validation_alias="AI_SDR_CALLING_MODE")
    public_url: str = Field(
        default="http://localhost:8000",
        validation_alias=AliasChoices("PUBLIC_URL", "PUBLIC_BACKEND_URL"),
    )
    public_websocket_url: str = Field(default="", validation_alias="AI_SDR_PUBLIC_WEBSOCKET_URL")
    telephony_provider: str = Field(default="twilio", validation_alias="AI_SDR_TELEPHONY_PROVIDER")
    llm_provider: str = Field(default="gemini", validation_alias="AI_SDR_LLM_PROVIDER")
    speech_provider: str = Field(default="cartesia", validation_alias="AI_SDR_SPEECH_PROVIDER")
    call_from_number: str = Field(default="", validation_alias="AI_SDR_CALL_FROM_NUMBER")
    manual_call_owner_number: str = Field(
        default="",
        validation_alias=AliasChoices(
            "AI_SDR_MANUAL_CALL_OWNER_NUMBER",
            "AI_SDR_OWNER_PHONE_NUMBER",
            "LEADFORGE_OWNER_PHONE",
        ),
    )
    call_default_objective: str = Field(
        default="Qualify the business need, identify website or follow-up gaps, and book the best next step.",
        validation_alias="AI_SDR_CALL_DEFAULT_OBJECTIVE",
    )
    call_silence_timeout_seconds: float = Field(
        default=1.2,
        ge=0.2,
        le=8.0,
        validation_alias="AI_SDR_CALL_SILENCE_TIMEOUT_SECONDS",
    )
    call_max_duration_seconds: int = Field(
        default=1800,
        ge=30,
        le=7200,
        validation_alias="AI_SDR_CALL_MAX_DURATION_SECONDS",
    )
    twilio_account_sid: str = Field(default="", validation_alias="TWILIO_ACCOUNT_SID")
    twilio_auth_token: str = Field(default="", validation_alias="TWILIO_AUTH_TOKEN")
    twilio_validate_signature: bool = Field(default=True, validation_alias="TWILIO_VALIDATE_SIGNATURE")
    gemini_api_key: str = Field(default="", validation_alias="GEMINI_API_KEY")
    gemini_model: str = Field(
        default="gemini-2.5-flash",
        validation_alias=AliasChoices("AI_SDR_GEMINI_MODEL", "GEMINI_MODEL"),
    )
    cartesia_api_key: str = Field(default="", validation_alias="CARTESIA_API_KEY")
    cartesia_version: str = Field(default="2026-03-01", validation_alias="CARTESIA_VERSION")
    cartesia_tts_model: str = Field(default="sonic-3.5", validation_alias="CARTESIA_TTS_MODEL")
    cartesia_stt_model: str = Field(default="ink-whisper", validation_alias="CARTESIA_STT_MODEL")
    cartesia_voice_id: str = Field(default="", validation_alias="CARTESIA_VOICE_ID")
    cartesia_tts_sample_rate: int = Field(default=8000, validation_alias="CARTESIA_TTS_SAMPLE_RATE")
    cartesia_tts_encoding: str = Field(default="pcm_mulaw", validation_alias="CARTESIA_TTS_ENCODING")
    cartesia_stt_encoding: str = Field(default="pcm_mulaw", validation_alias="CARTESIA_STT_ENCODING")
    cartesia_stt_sample_rate: int = Field(default=8000, validation_alias="CARTESIA_STT_SAMPLE_RATE")
    cartesia_stt_ws_url: str = Field(
        default="wss://api.cartesia.ai/stt/websocket",
        validation_alias="CARTESIA_STT_WS_URL",
    )

    @field_validator("api_prefix")
    @classmethod
    def normalize_prefix(cls, value: str) -> str:
        prefix = value.strip() or "/ai-sdr"
        if not prefix.startswith("/"):
            prefix = f"/{prefix}"
        return prefix.rstrip("/") or "/ai-sdr"

    @field_validator("calling_mode", "telephony_provider", "llm_provider", "speech_provider")
    @classmethod
    def normalize_provider_name(cls, value: str) -> str:
        return value.strip().lower().replace("_", "-")

    @field_validator("public_url", "public_websocket_url")
    @classmethod
    def trim_url(cls, value: str) -> str:
        return value.strip().rstrip("/")

    def media_stream_url(self, call_id: str) -> str:
        base = self.public_websocket_url
        if not base:
            base = self.public_url.replace("https://", "wss://", 1).replace("http://", "ws://", 1)
        return _join_url(base, self.api_prefix, "calls/twilio/media")

    def voice_webhook_url(self, call_id: str) -> str:
        return _join_url(self.public_url, self.api_prefix, "calls/twilio/voice", query={"call_id": call_id})

    def status_callback_url(self, call_id: str) -> str:
        return _join_url(self.public_url, self.api_prefix, "calls/twilio/status", query={"call_id": call_id})

    def manual_bridge_webhook_url(self, call_id: str) -> str:
        return _join_url(self.public_url, self.api_prefix, "calls/twilio/manual-bridge", query={"call_id": call_id})

    def manual_bridge_status_callback_url(self, call_id: str) -> str:
        return _join_url(
            self.public_url,
            self.api_prefix,
            "calls/twilio/manual-bridge/status",
            query={"call_id": call_id},
        )

    @property
    def public_backend_url(self) -> str:
        return self.public_url

    def validate_calling_startup(self) -> None:
        if (
            not self.calling_enabled
            or self.calling_mode == "mock"
            or self.environment.lower() != "production"
        ):
            return
        if self.telephony_provider == "twilio":
            self._require_absolute_https_public_url("PUBLIC_URL", self.public_url)
            if self.public_websocket_url:
                self._require_absolute_wss_public_url("AI_SDR_PUBLIC_WEBSOCKET_URL", self.public_websocket_url)

    @staticmethod
    def _require_absolute_https_public_url(name: str, value: str) -> None:
        parsed = urlsplit(value)
        if parsed.scheme != "https" or not parsed.netloc or _is_local_hostname(parsed.hostname):
            raise RuntimeError(
                f"Invalid {name} for AI SDR calling: set {name} to an absolute public HTTPS URL "
                f"such as https://your-app.up.railway.app. Current value: {value or '<empty>'}"
            )

    @staticmethod
    def _require_absolute_wss_public_url(name: str, value: str) -> None:
        parsed = urlsplit(value)
        if parsed.scheme != "wss" or not parsed.netloc or _is_local_hostname(parsed.hostname):
            raise RuntimeError(
                f"Invalid {name} for AI SDR calling: set {name} to an absolute public WSS URL "
                f"such as wss://your-app.up.railway.app. Current value: {value or '<empty>'}"
            )

    def require_calling_credentials(self) -> None:
        if self.telephony_provider == "twilio":
            self._require_absolute_https_public_url("PUBLIC_URL", self.public_url)
            if self.public_websocket_url:
                self._require_absolute_wss_public_url("AI_SDR_PUBLIC_WEBSOCKET_URL", self.public_websocket_url)
        missing: list[str] = []
        if self.telephony_provider == "twilio":
            missing.extend(
                name
                for name, value in {
                    "TWILIO_ACCOUNT_SID": self.twilio_account_sid,
                    "TWILIO_AUTH_TOKEN": self.twilio_auth_token,
                    "AI_SDR_CALL_FROM_NUMBER": self.call_from_number,
                }.items()
                if not value
            )
        if self.llm_provider == "gemini" and not self.gemini_api_key:
            missing.append("GEMINI_API_KEY")
        if self.speech_provider == "cartesia":
            missing.extend(
                name
                for name, value in {
                    "CARTESIA_API_KEY": self.cartesia_api_key,
                    "CARTESIA_VOICE_ID": self.cartesia_voice_id,
                }.items()
                if not value
            )
        if missing:
            raise RuntimeError("Missing required AI SDR calling environment variables: " + ", ".join(missing))

    def require_manual_bridge_credentials(self, owner_number: str) -> None:
        if not self.calling_enabled:
            raise RuntimeError("AI SDR calling is disabled.")
        if self.telephony_provider == "twilio":
            self._require_absolute_https_public_url("PUBLIC_URL", self.public_url)
        missing: list[str] = []
        if self.telephony_provider == "twilio":
            missing.extend(
                name
                for name, value in {
                    "TWILIO_ACCOUNT_SID": self.twilio_account_sid,
                    "TWILIO_AUTH_TOKEN": self.twilio_auth_token,
                    "AI_SDR_CALL_FROM_NUMBER": self.call_from_number,
                }.items()
                if not value
            )
        if not owner_number.strip():
            missing.append("AI_SDR_MANUAL_CALL_OWNER_NUMBER or owner_phone")
        if missing:
            raise RuntimeError("Missing required manual SDR calling environment variables: " + ", ".join(missing))


@lru_cache(maxsize=1)
def get_ai_sdr_settings() -> AISDRSettings:
    return AISDRSettings()


def _join_url(base: str, *parts: str, query: dict[str, str] | None = None) -> str:
    path = "/".join(part.strip("/") for part in parts if part.strip("/"))
    url = f"{base.rstrip('/')}/{path}"
    if query:
        url = f"{url}?{urlencode(query)}"
    return url


def _is_local_hostname(hostname: str | None) -> bool:
    if not hostname:
        return True
    return hostname.lower() in {"localhost", "127.0.0.1", "0.0.0.0", "::1"}
