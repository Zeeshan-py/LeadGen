"""Regression tests for the independent AI SDR backend module."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import asyncio
import unittest

from sqlalchemy import create_engine, select
from sqlalchemy.dialects import postgresql
from sqlalchemy.orm import Session

from ai_sdr.calling.interfaces import OutboundCallRequest, ProviderConfigurationError
from ai_sdr.calling.orchestrator import AISDRCallingOrchestrator
from ai_sdr.calling.providers.factory import CallingProviderStack
from ai_sdr.calling.providers.mock_provider import MockLLMProvider, MockSpeechProvider, MockTelephonyProvider
from ai_sdr.calling.providers.twilio_provider import TwilioTelephonyProvider
from ai_sdr.calling.session_manager import AISDRCallSessionRegistry
from ai_sdr.config import AISDRSettings
from ai_sdr.conversation import AISDRConversationManager, ConversationState
from ai_sdr.conversation.memory_manager import ConversationMemoryManager
from ai_sdr.models import AISDRContactBatch, AISDRContactRecord
from ai_sdr.schemas import AISDRContactInput, AISDRImportCreate, AISDRSourceType
from ai_sdr.services.dashboard import AISDRDashboardService
from ai_sdr.services.ingestion import AISDRIngestionService
from app.database import Base
from app.models import Lead, LeadActivity


class AISDRTests(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = create_engine("sqlite+pysqlite:///:memory:")
        Base.metadata.create_all(self.engine)

    def test_rest_contacts_are_normalized_and_stored_in_crm(self) -> None:
        with Session(self.engine) as db:
            response = AISDRIngestionService(db).ingest_contacts(
                AISDRImportCreate(
                    source_type=AISDRSourceType.REST_API,
                    contacts=[
                        AISDRContactInput(
                            company_name=" Acme Dental  ",
                            contact_name="Jordan Lee",
                            email="JORDAN@ACME.example",
                            website="acme.example/",
                            industry="Healthcare",
                            country="United States",
                            tags=["Priority"],
                        )
                    ],
                    created_by="REST API",
                )
            )

            self.assertEqual(response.batch.status, "completed")
            self.assertEqual(response.batch.stored_count, 1)
            self.assertEqual(response.records[0].status, "stored")

            lead = db.get(Lead, response.records[0].crm_lead_id)
            self.assertIsNotNone(lead)
            assert lead is not None
            self.assertEqual(lead.business_name, "Acme Dental")
            self.assertEqual(lead.email, "jordan@acme.example")
            self.assertEqual(lead.website, "https://acme.example")
            self.assertEqual(lead.crm_stage, "new")
            self.assertIn("AI SDR", lead.tags)

            activity = db.scalar(select(LeadActivity).where(LeadActivity.lead_id == lead.id))
            self.assertIsNotNone(activity)
            assert activity is not None
            self.assertEqual(activity.event_type, "tags_updated")

    def test_existing_crm_lead_is_merged_instead_of_recreated(self) -> None:
        with Session(self.engine) as db:
            lead = Lead(
                dedupe_key="domain:acme.example",
                business_name="Acme Dental",
                email="owner@acme.example",
                website="https://acme.example",
                source="apify_google_maps",
            )
            db.add(lead)
            db.commit()

            response = AISDRIngestionService(db).ingest_contacts(
                AISDRImportCreate(
                    source_type=AISDRSourceType.MANUAL_ENTRY,
                    contacts=[
                        AISDRContactInput(
                            company="Acme Dental",
                            contactName="Jordan Lee",
                            email="owner@acme.example",
                            title="Owner",
                        )
                    ],
                    created_by="LeadForge user",
                )
            )

            self.assertEqual(response.batch.duplicate_count, 1)
            self.assertEqual(response.records[0].status, "duplicate")
            self.assertEqual(response.records[0].crm_lead_id, lead.id)
            self.assertEqual(db.scalar(select(Lead).where(Lead.email == "owner@acme.example")).id, lead.id)

    def test_ai_sdr_python_files_do_not_import_lead_generation_module(self) -> None:
        module_root = Path(__file__).parents[1] / "ai_sdr"
        forbidden = ("lead_automation", "LeadPersistenceService", "run_generation_job")
        for path in module_root.rglob("*.py"):
            text = path.read_text(encoding="utf-8")
            for token in forbidden:
                self.assertNotIn(token, text, f"{path} imports or references {token}")

    def test_invalid_contact_is_tracked_without_crm_write(self) -> None:
        with Session(self.engine) as db:
            response = AISDRIngestionService(db).ingest_contacts(
                AISDRImportCreate(
                    source_type=AISDRSourceType.CSV,
                    contacts=[AISDRContactInput(raw={"empty": True})],
                )
            )

            self.assertEqual(response.batch.status, "failed")
            self.assertEqual(response.batch.failed_count, 1)
            self.assertEqual(response.records[0].status, "failed")
            self.assertIsNone(response.records[0].crm_lead_id)
            self.assertEqual(db.scalar(select(AISDRContactBatch)).id, response.batch.id)
            self.assertEqual(db.scalar(select(AISDRContactRecord)).errors[0], "Contact must include company, contact, email, phone, or website.")

    def test_dashboard_returns_sdr_metrics_and_contact_rows(self) -> None:
        with Session(self.engine) as db:
            response = AISDRIngestionService(db).ingest_contacts(
                AISDRImportCreate(
                    source_type=AISDRSourceType.EXCEL,
                    contacts=[
                        AISDRContactInput(
                            company_name="Northstar Clinic",
                            contact_name="Nora Patel",
                            phone="+1 415 555 0110",
                            email="nora@northstar.example",
                            city="San Francisco",
                            industry="Healthcare",
                        ),
                        AISDRContactInput(
                            company_name="Pioneer Labs",
                            contact_name="Sam Carter",
                            email="sam@pioneer.example",
                            city="Austin",
                            industry="Biotech",
                        ),
                    ],
                )
            )
            first_lead = db.get(Lead, response.records[0].crm_lead_id)
            assert first_lead is not None
            first_lead.crm_stage = "interested"
            first_lead.lead_status = "interested"
            db.commit()

            dashboard = AISDRDashboardService(db).dashboard(industry="Healthcare")

            self.assertEqual(dashboard.stats.total_contacts, 2)
            self.assertEqual(dashboard.stats.ready_to_call, 1)
            self.assertEqual(dashboard.stats.interested, 1)
            self.assertEqual(dashboard.total, 1)
            self.assertEqual(dashboard.contacts[0].company, "Northstar Clinic")
            self.assertEqual(dashboard.contacts[0].source, "excel")
            self.assertIn("Healthcare", dashboard.filters.industries)
            self.assertIn("San Francisco", dashboard.filters.cities)

    def test_dashboard_uses_latest_contact_record_timestamp_for_uuid_ids(self) -> None:
        with Session(self.engine) as db:
            lead = Lead(
                dedupe_key="domain:uuid-latest.example",
                business_name="UUID Latest Co",
                source="ai_sdr",
            )
            batch = AISDRContactBatch(source_type="manual_entry", status="completed")
            db.add_all([lead, batch])
            db.flush()

            older = AISDRContactRecord(
                batch_id=batch.id,
                crm_lead_id=lead.id,
                source_type="csv",
                status="stored",
                created_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
                updated_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
            )
            newer = AISDRContactRecord(
                batch_id=batch.id,
                crm_lead_id=lead.id,
                source_type="rest_api",
                status="stored",
                created_at=datetime(2026, 1, 2, tzinfo=timezone.utc),
                updated_at=datetime(2026, 1, 2, tzinfo=timezone.utc),
            )
            db.add_all([older, newer])
            db.commit()

            service = AISDRDashboardService(db)
            compiled = str(service._base_query().compile(dialect=postgresql.dialect())).lower()
            profile = service.get_contact(lead.id)

            self.assertNotIn("max(", compiled)
            self.assertIsNotNone(profile)
            assert profile is not None
            self.assertEqual(profile.source, "rest_api")
            self.assertEqual(profile.source_record_id, newer.id)

    def test_ai_sdr_public_url_builds_absolute_twilio_callback_urls(self) -> None:
        settings = AISDRSettings(
            _env_file=None,
            public_url="https://leadforage.up.railway.app/",
            api_prefix="/ai-sdr/",
        )

        self.assertEqual(
            settings.voice_webhook_url("call-123"),
            "https://leadforage.up.railway.app/ai-sdr/calls/twilio/voice?call_id=call-123",
        )
        self.assertEqual(
            settings.status_callback_url("call-123"),
            "https://leadforage.up.railway.app/ai-sdr/calls/twilio/status?call_id=call-123",
        )
        self.assertEqual(
            settings.media_stream_url("call-123"),
            "wss://leadforage.up.railway.app/ai-sdr/calls/twilio/media",
        )

    def test_ai_sdr_rejects_invalid_production_public_url(self) -> None:
        settings = AISDRSettings(
            _env_file=None,
            environment="production",
            public_url="http://localhost:8000",
            public_websocket_url="wss://leadforage.up.railway.app",
        )

        with self.assertRaisesRegex(RuntimeError, "Invalid PUBLIC_URL"):
            settings.validate_calling_startup()

    def test_twilio_provider_logs_exact_calls_create_url(self) -> None:
        class FakeCalls:
            def __init__(self) -> None:
                self.kwargs: dict[str, object] = {}

            def create(self, **kwargs: object) -> object:
                self.kwargs = kwargs
                return type("FakeCall", (), {"sid": "CA123", "status": "queued"})()

        class FakeClient:
            def __init__(self) -> None:
                self.calls = FakeCalls()

        fake_client = FakeClient()
        provider = TwilioTelephonyProvider(
            AISDRSettings(
                _env_file=None,
                public_url="https://leadforage.up.railway.app",
                twilio_account_sid="AC123",
                twilio_auth_token="secret",
            )
        )
        provider._client = fake_client
        request = OutboundCallRequest(
            call_id="call-123",
            contact_id="lead-123",
            to_number="+14155550123",
            from_number="+13322864743",
            voice_webhook_url="https://leadforage.up.railway.app/ai-sdr/calls/twilio/voice?call_id=call-123",
            status_callback_url="https://leadforage.up.railway.app/ai-sdr/calls/twilio/status?call_id=call-123",
            media_stream_url="wss://leadforage.up.railway.app/ai-sdr/calls/twilio/media",
        )

        with self.assertLogs("ai_sdr.calling.providers.twilio_provider", level="INFO") as logs:
            result = asyncio.run(provider.start_outbound_call(request))

        self.assertEqual(result.provider_call_id, "CA123")
        self.assertEqual(fake_client.calls.kwargs["url"], request.voice_webhook_url)
        self.assertIn(f"url={request.voice_webhook_url}", "\n".join(logs.output))

    def test_twilio_provider_rejects_non_https_calls_create_url(self) -> None:
        provider = TwilioTelephonyProvider(
            AISDRSettings(
                _env_file=None,
                twilio_account_sid="AC123",
                twilio_auth_token="secret",
            )
        )
        request = OutboundCallRequest(
            call_id="call-123",
            contact_id="lead-123",
            to_number="+14155550123",
            from_number="+13322864743",
            voice_webhook_url="http://localhost:8000/ai-sdr/calls/twilio/voice?call_id=call-123",
            status_callback_url="https://leadforage.up.railway.app/ai-sdr/calls/twilio/status?call_id=call-123",
            media_stream_url="wss://leadforage.up.railway.app/ai-sdr/calls/twilio/media",
        )

        with self.assertRaisesRegex(ProviderConfigurationError, "absolute HTTPS URL"):
            asyncio.run(provider.start_outbound_call(request))

    def test_twilio_voice_response_uses_stream_parameter_for_call_id(self) -> None:
        provider = TwilioTelephonyProvider(AISDRSettings(_env_file=None))

        twiml = provider.build_voice_response(
            call_id="call-123",
            media_stream_url="wss://leadforage.up.railway.app/ai-sdr/calls/twilio/media",
        )

        self.assertIn('url="wss://leadforage.up.railway.app/ai-sdr/calls/twilio/media"', twiml)
        self.assertNotIn("?call_id=", twiml)
        self.assertIn('name="call_id"', twiml)
        self.assertIn('value="call-123"', twiml)

    def test_bulk_delete_archives_contacts_out_of_default_dashboard(self) -> None:
        with Session(self.engine) as db:
            response = AISDRIngestionService(db).ingest_contacts(
                AISDRImportCreate(
                    source_type=AISDRSourceType.MANUAL_ENTRY,
                    contacts=[
                        AISDRContactInput(
                            company_name="Archive Me",
                            contact_name="Alex Doe",
                            phone="+1 303 555 0155",
                        )
                    ],
                )
            )
            lead_id = response.records[0].crm_lead_id
            assert lead_id is not None

            result = AISDRDashboardService(db).archive_contacts([lead_id], actor="QA")
            dashboard = AISDRDashboardService(db).dashboard()
            archived = db.get(Lead, lead_id)

            self.assertEqual(result.requested, 1)
            self.assertEqual(result.updated, 1)
            self.assertEqual(result.contact_ids, [lead_id])
            self.assertEqual(dashboard.stats.total_contacts, 0)
            self.assertEqual(dashboard.contacts, [])
            self.assertIsNotNone(archived)
            assert archived is not None
            self.assertEqual(archived.crm_stage, "archived")
            self.assertEqual(archived.lead_status, "archived")

    def test_get_contact_returns_single_sdr_profile(self) -> None:
        with Session(self.engine) as db:
            response = AISDRIngestionService(db).ingest_contacts(
                AISDRImportCreate(
                    source_type=AISDRSourceType.REST_API,
                    contacts=[
                        AISDRContactInput(
                            company_name="Single Profile Co",
                            contact_name="Casey Smith",
                            phone="+1 212 555 0181",
                            email="casey@single.example",
                            industry="SaaS",
                        )
                    ],
                )
            )
            lead_id = response.records[0].crm_lead_id
            assert lead_id is not None

            profile = AISDRDashboardService(db).get_contact(lead_id)

            self.assertIsNotNone(profile)
            assert profile is not None
            self.assertEqual(profile.company, "Single Profile Co")
            self.assertEqual(profile.contact, "Casey Smith")

    def test_conversation_engine_starts_with_contact_context_and_memory(self) -> None:
        with Session(self.engine) as db:
            lead = Lead(
                dedupe_key="domain:northstar.example",
                business_name="Northstar Dental Studio",
                contact_name="Maya Shah",
                website="https://northstar.example",
                city="Austin",
                state="TX",
                business_type="Dental Services",
                notes="Maya previously asked for a practical review of mobile booking friction.",
                source="ai_sdr",
            )
            db.add(lead)
            db.add(
                LeadActivity(
                    lead=lead,
                    event_type="note_added",
                    title="Previous note",
                    description="Customer prefers concise follow-up.",
                    actor="QA",
                )
            )
            db.commit()

            manager = AISDRConversationManager(memory_manager=ConversationMemoryManager())
            started = manager.start_for_contact(db, lead.id)

            self.assertIsNotNone(started)
            assert started is not None
            self.assertEqual(started["state"], ConversationState.PERMISSION.value)
            self.assertIn("Northstar Dental Studio", started["reply"])
            self.assertIn("Dental Services", started["reply"])
            self.assertIn("Austin", started["reply"])
            self.assertIn("previously asked", started["reply"])
            self.assertGreaterEqual(len(started["events"]), 3)

            session_id = started["session_id"]
            response = manager.receive_customer_message(session_id, "Yes, I have a minute.")

            self.assertIsNotNone(response)
            assert response is not None
            self.assertEqual(response["state"], ConversationState.DISCOVERY.value)
            self.assertIn("Northstar Dental Studio", response["reply"])
            self.assertTrue(any(event["event_type"] == "customer_message" for event in response["events"]))
            self.assertTrue(any(event["event_type"] == "qualification_updated" for event in response["events"]))

    def test_conversation_engine_answers_ai_identity_honestly(self) -> None:
        manager = AISDRConversationManager(memory_manager=ConversationMemoryManager())
        started = manager.start_from_context(
            company_payload={
                "business_name": "Pioneer Fitness",
                "industry": "Fitness",
                "city": "Denver",
                "website": "https://pioneer.example",
            },
            owner_payload={"name": "Jordan"},
        )

        response = manager.receive_customer_message(started["session_id"], "Are you AI?")

        self.assertIsNotNone(response)
        assert response is not None
        self.assertIn("Yes, I am an AI assistant", response["reply"])
        self.assertIn("Pioneer Fitness", response["reply"])
        self.assertTrue(
            any(
                event["event_type"] == "identity_disclosure"
                and event["metadata"].get("honest_ai_disclosure") is True
                for event in response["events"]
            )
        )

    def test_conversation_engine_detects_objections_and_advances_pricing(self) -> None:
        manager = AISDRConversationManager(memory_manager=ConversationMemoryManager())
        started = manager.start_from_context(
            company_payload={
                "business_name": "Acme Clinic",
                "industry": "Healthcare",
                "city": "Chicago",
                "website": "https://acme-clinic.example",
            },
            owner_payload={"name": "Casey"},
        )

        permission = manager.receive_customer_message(started["session_id"], "Sure, go ahead.")
        assert permission is not None
        discovery = manager.receive_customer_message(
            started["session_id"],
            "We get website traffic, but appointment booking is inconsistent.",
        )
        assert discovery is not None
        pricing = manager.receive_customer_message(started["session_id"], "What does this cost?")

        self.assertIsNotNone(pricing)
        assert pricing is not None
        self.assertEqual(pricing["state"], ConversationState.PRICING.value)
        self.assertIn("Pricing depends", pricing["reply"])
        self.assertIn("Pricing concern", pricing["memory"]["objections"])
        self.assertIn("booking friction", pricing["memory"]["discovered_needs"])
        self.assertTrue(any(event["event_type"] == "objection_detected" for event in pricing["events"]))

    def test_calling_orchestrator_stores_transcript_and_outcome_in_crm(self) -> None:
        with Session(self.engine) as db:
            lead = Lead(
                dedupe_key="domain:calling.example",
                business_name="Calling Dental Studio",
                contact_name="Morgan Owner",
                phone="+14155550123",
                email="morgan@calling.example",
                website="https://calling.example",
                city="Austin",
                business_type="Dental Services",
                source="ai_sdr",
            )
            db.add(lead)
            db.commit()

            settings = AISDRSettings(
                _env_file=None,
                calling_mode="mock",
                twilio_validate_signature=False,
            )
            orchestrator = AISDRCallingOrchestrator(
                settings=settings,
                providers=CallingProviderStack(
                    telephony=MockTelephonyProvider(),
                    llm=MockLLMProvider(),
                    speech=MockSpeechProvider(),
                ),
                registry=AISDRCallSessionRegistry(),
            )

            async def run_call() -> str:
                started = await orchestrator.start_outbound_call(db, contact_id=lead.id, actor="QA")
                await orchestrator.inject_transcript(
                    db,
                    call_id=started.id,
                    role="customer",
                    text="Yes, I am open to seeing a couple of useful follow-up times tomorrow.",
                    actor="QA",
                )
                completed = await orchestrator.complete_call(db, call_id=started.id, actor="QA")
                return completed.id

            call_id = asyncio.run(run_call())
            db.refresh(lead)

            self.assertEqual(lead.crm_stage, "interested")
            self.assertIn("AI SDR Called", lead.tags)
            self.assertTrue((lead.raw or {}).get("ai_sdr", {}).get("last_call"))
            last_call = lead.raw["ai_sdr"]["last_call"]
            self.assertEqual(last_call["call_id"], call_id)
            self.assertTrue(last_call["outcome"]["interested"])
            self.assertGreaterEqual(len(last_call["transcript"]), 2)
            activity_types = [
                row.event_type
                for row in db.scalars(select(LeadActivity).where(LeadActivity.lead_id == lead.id)).all()
            ]
            self.assertIn("ai_sdr_call_started", activity_types)
            self.assertIn("ai_sdr_call_transcript", activity_types)
            self.assertIn("ai_sdr_call_completed", activity_types)


if __name__ == "__main__":
    unittest.main()
