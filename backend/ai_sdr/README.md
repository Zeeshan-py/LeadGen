# AI SDR Backend Module

The `backend/ai_sdr` package is an independent AI SDR architecture module. It does not import from `backend/lead_automation` or any lead-generation service.

## Boundaries

Allowed shared dependencies:

- `app.database` for the shared SQLAlchemy session and metadata
- `app.models.Lead` as the shared CRM contact record
- `app.services.crm` for CRM activities and tag management

Not allowed:

- imports from `lead_automation`
- imports from lead generation routes, runners, pipelines, or persistence services
- direct data access to the Lead Generator module

## API

- `GET /ai-sdr/health`
- `GET /ai-sdr/sources`
- `GET /ai-sdr/conversation/states`
- `POST /ai-sdr/conversations`
- `GET /ai-sdr/conversations/{session_id}`
- `POST /ai-sdr/conversations/{session_id}/turn`
- `POST /ai-sdr/imports`
- `GET /ai-sdr/imports`
- `GET /ai-sdr/imports/{batch_id}`
- `GET /ai-sdr/dashboard`
- `GET /ai-sdr/contacts/{contact_id}`
- `POST /ai-sdr/contacts/manual`
- `POST /ai-sdr/contacts`
- `POST /ai-sdr/contacts/bulk-delete`
- `POST /ai-sdr/contacts/export.csv`
- `POST /ai-sdr/calls/outbound`
- `GET /ai-sdr/calls`
- `GET /ai-sdr/calls/{call_id}`
- `POST /ai-sdr/calls/{call_id}/control`
- `POST /ai-sdr/calls/{call_id}/transcript`
- `POST /ai-sdr/calls/{call_id}/complete`
- `GET|POST /ai-sdr/calls/twilio/voice`
- `POST /ai-sdr/calls/twilio/status`
- `WS /ai-sdr/calls/twilio/media`

All source adapters feed the same import contract:

```json
{
  "source_type": "csv",
  "contacts": [
    {
      "company_name": "Acme Health",
      "contact_name": "Taylor Reed",
      "email": "taylor@acme.example",
      "website": "acme.example",
      "industry": "Healthcare"
    }
  ],
  "configuration": {
    "source_file": "contacts.csv"
  }
}
```

## Sources

The module has first-class source types for:

- CSV
- Excel
- Google Sheets
- Manual Entry
- REST API
- CRM
- Future integrations

Manual Entry and REST API are live ingestion paths. CSV, Excel, Google Sheets, CRM, and future integrations are adapter-ready: connector code should extract rows and submit dictionaries to `POST /ai-sdr/imports`.

## Normalization Flow

1. Source adapter emits raw contact dictionaries.
2. `AISDRIngestionService` creates an SDR import batch.
3. `normalize_contact` maps source-specific fields to the canonical contact shape.
4. `AISDRCRMGateway` upserts the normalized contact into CRM.
5. The module records batch, record, CRM lead, and activity metadata.

## Database

The SDR owns:

- `ai_sdr_contact_batches`
- `ai_sdr_contact_records`

CRM storage remains in the shared `leads` table.

## Conversation Engine

The AI SDR conversation engine lives in `backend/ai_sdr/conversation` and is independent from telephony.

Modules:

- `conversation_manager.py` coordinates sessions, events, and state transitions
- `memory_manager.py` stores in-memory session history, transcript events, objections, needs, and qualification data
- `sales_strategy.py` generates natural SDR wording
- `objection_handler.py` detects objections and answers "Are you AI?" honestly
- `qualification.py` scores fit and identifies missing qualification signals
- `closing_strategy.py` handles closing, follow-up, and goodbye language
- `company_information.py` builds business context from CRM or payload data
- `owner_information.py` builds owner/contact context

State machine:

1. Greeting
2. Permission
3. Discovery
4. Qualification
5. Website Discussion
6. AI Automation Discussion
7. Pricing
8. Objection Handling
9. Closing
10. Follow-up
11. Goodbye

Every customer turn returns structured events, the current state, the AI reply, and an in-memory session summary. The engine references business name, industry, website, city, and previous CRM interactions when available. It does not place calls, use Twilio, stream audio, or persist conversation sessions yet.

## Production Calling Stack

The `backend/ai_sdr/calling` package adds a provider-based calling runtime:

- `TelephonyProvider` is implemented by Twilio.
- `LLMProvider` is implemented by Gemini 2.5 Flash through `google-genai`.
- `SpeechProvider` is implemented by Cartesia for streaming STT/TTS.
- Mock providers are available with `AI_SDR_CALLING_MODE=mock` for local testing.

Calling flow:

1. `POST /ai-sdr/calls/outbound` starts a CRM contact call.
2. Twilio fetches `/ai-sdr/calls/twilio/voice` and receives TwiML that connects to `/ai-sdr/calls/twilio/media`.
3. Cartesia streams customer speech recognition.
4. Gemini generates the next natural AI response and live AI Brain state.
5. Cartesia synthesizes the response back to Twilio.
6. Interruptions clear queued AI audio; silence detection finalizes customer utterances.
7. On completion, Gemini generates the structured CRM outcome.

CRM storage:

- Every transcript line is stored as a `lead_activities` CRM event.
- Final summary, qualification score, interested/not interested, reason, objections, website problems, recommended services, and next follow-up are stored in CRM activity metadata and `lead.raw["ai_sdr"]["last_call"]`.
- CRM stage, tags, follow-up, website problems, and service recommendations are updated through shared CRM helpers.

The AI SDR calling stack still does not import or call Lead Generation. All contact context and persistence are handled through CRM models/services only.
