"""Twilio telephony provider for AI SDR outbound calls and media streams."""

from __future__ import annotations

import base64
import logging
from typing import Any
from urllib.parse import urlsplit

from ai_sdr.calling.interfaces import (
    CallStatusUpdate,
    OutboundCallRequest,
    OutboundCallResult,
    ProviderConfigurationError,
    TelephonyMediaEvent,
    TelephonyProvider,
)
from ai_sdr.config import AISDRSettings


logger = logging.getLogger(__name__)


class TwilioTelephonyProvider(TelephonyProvider):
    """Twilio implementation of the swappable telephony provider contract."""

    name = "twilio"

    def __init__(self, settings: AISDRSettings) -> None:
        self.settings = settings
        self._client: Any | None = None

    async def start_outbound_call(self, request: OutboundCallRequest) -> OutboundCallResult:
        self._require_config()
        self._require_https_url("url", request.voice_webhook_url)
        self._require_https_url("status_callback", request.status_callback_url)
        client = self._twilio_client()
        logger.info("AI SDR Twilio client.calls.create url=%s", request.voice_webhook_url)
        create_kwargs: dict[str, Any] = {
            "to": request.to_number,
            "from_": request.from_number,
            "url": request.voice_webhook_url,
            "status_callback": request.status_callback_url,
            "status_callback_method": "POST",
            "status_callback_event": ["initiated", "ringing", "answered", "completed"],
        }
        if not request.metadata.get("manual_bridge"):
            create_kwargs.update({"machine_detection": "Enable", "async_amd": "true"})
        call = client.calls.create(**create_kwargs)
        return OutboundCallResult(
            provider_call_id=str(call.sid),
            status=str(getattr(call, "status", "queued") or "queued"),
            raw={
                "sid": str(call.sid),
                "status": str(getattr(call, "status", "queued") or "queued"),
                "to": request.to_number,
                "from": request.from_number,
            },
        )

    async def end_call(self, provider_call_id: str) -> None:
        self._require_config()
        self._twilio_client().calls(provider_call_id).update(status="completed")

    def build_voice_response(self, *, call_id: str, media_stream_url: str) -> str:
        try:
            from twilio.twiml.voice_response import Connect, Parameter, Stream, VoiceResponse
        except ImportError:
            return (
                '<?xml version="1.0" encoding="UTF-8"?>'
                "<Response><Connect><Stream url=\""
                f"{media_stream_url}\"><Parameter name=\"call_id\" value=\"{call_id}\" />"
                "</Stream></Connect></Response>"
            )

        response = VoiceResponse()
        connect = Connect()
        stream = Stream(url=media_stream_url)
        stream.append(Parameter(name="call_id", value=call_id))
        connect.append(stream)
        response.append(connect)
        return str(response)

    def build_manual_bridge_response(self, *, target_number: str, caller_id: str) -> str:
        try:
            from twilio.twiml.voice_response import Dial, Number, VoiceResponse
        except ImportError:
            return (
                '<?xml version="1.0" encoding="UTF-8"?>'
                f"<Response><Dial callerId=\"{caller_id}\"><Number>{target_number}</Number></Dial></Response>"
            )

        response = VoiceResponse()
        dial = Dial(caller_id=caller_id)
        dial.append(Number(target_number))
        response.append(dial)
        return str(response)

    def parse_status_update(self, payload: dict[str, Any]) -> CallStatusUpdate:
        provider_call_id = str(payload.get("CallSid") or payload.get("call_sid") or "")
        duration = payload.get("CallDuration") or payload.get("Duration")
        try:
            duration_seconds = int(duration) if duration not in (None, "") else None
        except (TypeError, ValueError):
            duration_seconds = None
        return CallStatusUpdate(
            provider_call_id=provider_call_id,
            status=str(payload.get("CallStatus") or payload.get("CallStatus".lower()) or "unknown"),
            duration_seconds=duration_seconds,
            reason=str(payload.get("ErrorMessage") or payload.get("AnsweredBy") or ""),
            raw=payload,
        )

    def parse_media_event(self, payload: dict[str, Any]) -> TelephonyMediaEvent:
        event_type = str(payload.get("event") or "")
        start = payload.get("start") or {}
        media = payload.get("media") or {}
        stop = payload.get("stop") or {}
        stream_id = str(payload.get("streamSid") or start.get("streamSid") or media.get("streamSid") or "")
        provider_call_id = str(start.get("callSid") or stop.get("callSid") or payload.get("callSid") or "")
        custom = start.get("customParameters") or {}
        call_id = str(custom.get("call_id") or payload.get("call_id") or "")
        audio = b""
        if event_type == "media":
            encoded = str(media.get("payload") or "")
            if encoded:
                audio = base64.b64decode(encoded)
        timestamp = media.get("timestamp")
        try:
            timestamp_ms = int(timestamp) if timestamp not in (None, "") else None
        except (TypeError, ValueError):
            timestamp_ms = None
        return TelephonyMediaEvent(
            event_type=event_type,
            call_id=call_id,
            provider_call_id=provider_call_id,
            stream_id=stream_id,
            audio=audio,
            timestamp_ms=timestamp_ms,
            raw=payload,
        )

    def outbound_audio_message(self, *, stream_id: str, audio: bytes) -> dict[str, Any]:
        return {
            "event": "media",
            "streamSid": stream_id,
            "media": {"payload": base64.b64encode(audio).decode("ascii")},
        }

    def clear_audio_message(self, *, stream_id: str) -> dict[str, Any]:
        return {"event": "clear", "streamSid": stream_id}

    def _twilio_client(self) -> Any:
        if self._client is None:
            try:
                from twilio.rest import Client
            except ImportError as exc:
                raise ProviderConfigurationError(
                    "Twilio provider selected but the twilio package is not installed."
                ) from exc
            self._client = Client(self.settings.twilio_account_sid, self.settings.twilio_auth_token)
        return self._client

    def _require_config(self) -> None:
        if not (self.settings.twilio_account_sid and self.settings.twilio_auth_token):
            raise ProviderConfigurationError(
                "Twilio provider requires TWILIO_ACCOUNT_SID and TWILIO_AUTH_TOKEN."
            )

    @staticmethod
    def _require_https_url(parameter_name: str, value: str) -> None:
        parsed = urlsplit(value)
        if parsed.scheme != "https" or not parsed.netloc:
            raise ProviderConfigurationError(
                f"Twilio {parameter_name} must be an absolute HTTPS URL. Current value: {value or '<empty>'}"
            )
