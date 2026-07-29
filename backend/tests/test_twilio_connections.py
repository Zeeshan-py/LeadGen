"""Regression tests for per-user Twilio and voice settings."""

from __future__ import annotations

import asyncio
import unittest
from unittest.mock import patch

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from ai_sdr.calling.interfaces import OutboundCallRequest, OutboundCallResult
from ai_sdr.calling.orchestrator import AISDRCallingOrchestrator
from ai_sdr.calling.providers.factory import CallingProviderStack
from ai_sdr.calling.providers.mock_provider import MockLLMProvider, MockSpeechProvider, MockTelephonyProvider
from ai_sdr.calling.session_manager import AISDRCallSessionRegistry
from ai_sdr.config import AISDRSettings
from app.config import Settings
from app.database import Base
from app.models import Lead, TwilioConnection
from app.twilio_connections import (
    TwilioPhoneNumber,
    TwilioPhoneSelectionRequired,
    ai_sdr_settings_for_user,
    decrypt_twilio_auth_token,
    encrypt_twilio_auth_token,
    upsert_twilio_connection,
    upsert_voice_settings,
)


class TwilioConnectionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = create_engine("sqlite+pysqlite:///:memory:")
        Base.metadata.create_all(self.engine)
        self.platform_settings = Settings(_env_file=None, JWT_SECRET_KEY="test-secret-key-for-fernet")

    def test_twilio_auth_token_is_encrypted_and_decrypted_per_user(self) -> None:
        with Session(self.engine) as db:
            connection = upsert_twilio_connection(
                db,
                self.platform_settings,
                user_id="00000000-0000-0000-0000-000000000001",
                account_sid="AC11111111111111111111111111111111",
                auth_token="twilio-secret-a",
                account_status="active",
                phone_numbers=[
                    TwilioPhoneNumber(
                        phone_sid="PN111",
                        phone_number="+14155550111",
                        friendly_name="Sales Line",
                    )
                ],
            )
            db.commit()

            self.assertNotEqual(connection.auth_token_encrypted, "twilio-secret-a")
            self.assertEqual(
                decrypt_twilio_auth_token(self.platform_settings, connection.auth_token_encrypted),
                "twilio-secret-a",
            )
            self.assertEqual(connection.phone_number, "+14155550111")

    def test_multiple_twilio_numbers_require_selection_before_saving(self) -> None:
        with Session(self.engine) as db:
            with self.assertRaises(TwilioPhoneSelectionRequired) as raised:
                upsert_twilio_connection(
                    db,
                    self.platform_settings,
                    user_id="00000000-0000-0000-0000-000000000001",
                    account_sid="AC11111111111111111111111111111111",
                    auth_token="twilio-secret-a",
                    account_status="active",
                    phone_numbers=[
                        TwilioPhoneNumber(phone_sid="PN111", phone_number="+14155550111"),
                        TwilioPhoneNumber(phone_sid="PN222", phone_number="+14155550222"),
                    ],
                )

            self.assertEqual([number.phone_sid for number in raised.exception.numbers], ["PN111", "PN222"])
            self.assertEqual(db.query(TwilioConnection).count(), 0)

    def test_ai_sdr_settings_use_user_twilio_and_voice_preferences(self) -> None:
        with Session(self.engine) as db:
            upsert_twilio_connection(
                db,
                self.platform_settings,
                user_id="00000000-0000-0000-0000-000000000001",
                account_sid="AC11111111111111111111111111111111",
                auth_token="twilio-secret-a",
                account_status="active",
                phone_numbers=[TwilioPhoneNumber(phone_sid="PN111", phone_number="+14155550111")],
            )
            upsert_voice_settings(
                db,
                self.platform_settings,
                user_id="00000000-0000-0000-0000-000000000001",
                voice_id="voice-user-a",
                speaking_speed="faster",
                language="en",
                ai_greeting="Hi, this is {assistant_name} with {assistant_business_name}.",
                business_name="User A Studio",
                assistant_name="Mira",
                cartesia_api_key="cartesia-user-a",
            )
            db.commit()

            base = AISDRSettings(
                _env_file=None,
                public_url="https://leadforge.up.railway.app",
                twilio_account_sid="ACGLOBAL",
                twilio_auth_token="global-token",
                call_from_number="+19999999999",
                cartesia_api_key="global-cartesia",
                cartesia_voice_id="global-voice",
                gemini_api_key="gemini",
            )
            user_settings = ai_sdr_settings_for_user(
                db,
                self.platform_settings,
                base,
                user_id="00000000-0000-0000-0000-000000000001",
            )

            self.assertEqual(user_settings.twilio_account_sid, "AC11111111111111111111111111111111")
            self.assertEqual(user_settings.twilio_auth_token, "twilio-secret-a")
            self.assertEqual(user_settings.call_from_number, "+14155550111")
            self.assertEqual(user_settings.cartesia_api_key, "cartesia-user-a")
            self.assertEqual(user_settings.cartesia_voice_id, "voice-user-a")
            self.assertEqual(user_settings.cartesia_tts_speed, "faster")
            self.assertEqual(user_settings.assistant_name, "Mira")
            self.assertEqual(user_settings.assistant_business_name, "User A Studio")

    def test_orchestrator_places_call_from_authenticated_users_twilio_number(self) -> None:
        class CapturingTelephony:
            name = "twilio"

            def __init__(self) -> None:
                self.requests: list[OutboundCallRequest] = []

            async def start_outbound_call(self, request: OutboundCallRequest) -> OutboundCallResult:
                self.requests.append(request)
                return OutboundCallResult(provider_call_id="CA111", status="queued")

            async def end_call(self, provider_call_id: str) -> None:
                return None

            def build_voice_response(self, *, call_id: str, media_stream_url: str) -> str:
                return "<Response />"

            def parse_status_update(self, payload: dict[str, object]):  # pragma: no cover
                raise NotImplementedError

            def parse_media_event(self, payload: dict[str, object]):  # pragma: no cover
                raise NotImplementedError

            def outbound_audio_message(self, *, stream_id: str, audio: bytes) -> dict[str, object]:
                return {}

            def clear_audio_message(self, *, stream_id: str) -> dict[str, object]:
                return {}

        with Session(self.engine) as db:
            lead = Lead(
                user_id="00000000-0000-0000-0000-000000000001",
                dedupe_key="domain:twilio-user-a.example",
                business_name="Twilio User A",
                phone="+14155550999",
                source="ai_sdr",
            )
            db.add(lead)
            upsert_twilio_connection(
                db,
                self.platform_settings,
                user_id="00000000-0000-0000-0000-000000000001",
                account_sid="AC11111111111111111111111111111111",
                auth_token="twilio-secret-a",
                account_status="active",
                phone_numbers=[TwilioPhoneNumber(phone_sid="PN111", phone_number="+14155550111")],
            )
            db.commit()

            telephony = CapturingTelephony()
            built_settings: list[AISDRSettings] = []

            def fake_build(settings: AISDRSettings) -> CallingProviderStack:
                built_settings.append(settings)
                return CallingProviderStack(
                    telephony=telephony,
                    llm=MockLLMProvider(),
                    speech=MockSpeechProvider(),
                )

            base = AISDRSettings(
                _env_file=None,
                public_url="https://leadforge.up.railway.app",
                cartesia_api_key="cartesia",
                cartesia_voice_id="voice",
                gemini_api_key="gemini",
            )
            orchestrator = AISDRCallingOrchestrator(
                settings=base,
                providers=CallingProviderStack(
                    telephony=MockTelephonyProvider(),
                    llm=MockLLMProvider(),
                    speech=MockSpeechProvider(),
                ),
                registry=AISDRCallSessionRegistry(),
            )

            with (
                patch("ai_sdr.calling.orchestrator.get_platform_settings", return_value=self.platform_settings),
                patch("ai_sdr.calling.orchestrator.build_calling_provider_stack", side_effect=fake_build),
            ):
                asyncio.run(
                    orchestrator.start_outbound_call(
                        db,
                        contact_id=lead.id,
                        actor="QA",
                        user_id="00000000-0000-0000-0000-000000000001",
                    )
                )

            self.assertEqual(built_settings[0].twilio_auth_token, "twilio-secret-a")
            self.assertEqual(telephony.requests[0].from_number, "+14155550111")
            self.assertEqual(telephony.requests[0].to_number, "+14155550999")


if __name__ == "__main__":
    unittest.main()
