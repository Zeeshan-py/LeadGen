# API Reference

Base URL in local development: `http://localhost:8000`.

Production authentication: Basic Auth is required when `ENVIRONMENT=production`, except health endpoints.

## Common Errors

| Status | Meaning |
|---|---|
| 400 | Invalid request or configuration. |
| 401 | Missing/invalid production Basic Auth. |
| 404 | Resource not found. |
| 503 | Database/integration/module unavailable. |

## Health

| Method | Route | Description |
|---|---|---|
| GET | `/health` | Liveness check. |
| GET | `/health/live` | Liveness check. |
| GET | `/health/ready` | Database readiness check. |
| GET | `/health/google` | Google Sheets credential/spreadsheet check. |

Example:

```bash
curl http://localhost:8000/health/ready
```

## Lead Generation

### POST `/generate-leads`

Starts a background lead generation job.

Request:

```json
{
  "continent": "North America",
  "country": "United States",
  "city": "Austin",
  "business_type": "Dental Services",
  "website_mode": "withWebsite",
  "max_leads": 25
}
```

Response:

```json
{
  "job_id": "uuid",
  "status": "queued",
  "events_url": "/generate-leads/uuid/events"
}
```

### GET `/generate-leads/latest`

Returns the latest job snapshot or `null`.

### GET `/generate-leads/{job_id}`

Returns job status, pipeline, counters, progress, campaign ID, and errors.

### GET `/generate-leads/{job_id}/events`

Streams server-sent events with job snapshots and progress.

## Leads

| Method | Route | Description |
|---|---|---|
| GET | `/get-leads` | List leads. Supports `search`, `status`, `outreach_status`, `campaign_id`, `scope`, `country`, `business_type`, `contact`, `sort`, `limit`, `offset`. |
| PATCH | `/get-leads/{lead_id}` | Update lead fields. |
| GET | `/get-leads/export.csv` | Export CSV by latest/all/campaign scope. |

Example:

```bash
curl "http://localhost:8000/get-leads?search=dental&limit=50"
```

## Campaigns

| Method | Route | Description |
|---|---|---|
| GET | `/get-campaigns` | List campaigns. |
| POST | `/get-campaigns` | Create campaign. |

Request:

```json
{
  "name": "Austin Dentists",
  "city": "Austin",
  "state": "TX",
  "country": "United States",
  "business_type": "Dental Services",
  "max_leads": 50
}
```

## Outreach

| Method | Route | Description |
|---|---|---|
| GET | `/outreach` | List outreach drafts. Supports `lead_id` and `status`. |
| POST | `/outreach/{lead_id}/regenerate` | Regenerate AI outreach for a lead. |
| POST | `/send-email` | Send selected outreach version through Gmail. |
| POST | `/send-email/sync-statuses` | Sync Gmail replies and auto-replies. |
| GET | `/email/open/{tracking_id}.png` | Tracking pixel endpoint. |

Send request:

```json
{
  "outreach_id": "uuid",
  "version": "cold_email"
}
```

## Analytics

| Method | Route | Description |
|---|---|---|
| GET | `/get-analytics` | Returns lead, outreach, opportunity, conversion, chart, and activity summaries. |

## Settings

| Method | Route | Description |
|---|---|---|
| GET | `/settings` | Read settings summary and configured integration flags. |
| PUT | `/settings` | Save runtime settings overrides. |

Request:

```json
{
  "gemini_api_key": "secret",
  "default_lead_limit": 50,
  "google_sheets_id": "spreadsheet-id"
}
```

## CRM

| Method | Route | Description |
|---|---|---|
| GET | `/crm/users` | List active CRM users. |
| POST | `/crm/users` | Create CRM user. |
| GET | `/crm/leads` | List CRM leads with filters and stage counts. |
| GET | `/crm/leads/{lead_id}` | Get full CRM lead detail. |
| PATCH | `/crm/leads/{lead_id}` | Update CRM fields/stage/assignee/follow-up. |
| POST | `/crm/leads/{lead_id}/notes` | Add CRM note. |
| PUT | `/crm/leads/{lead_id}/tags` | Replace tags. |
| POST | `/crm/leads/{lead_id}/sync-gmail` | Sync Gmail messages for lead. |

CRM list filters include `search`, `stage`, `country`, `industry`, `assigned_user_id`, `created_from`, `created_to`, `last_contacted_from`, `last_contacted_to`, `limit`, and `offset`.

## AI SDR

| Method | Route | Description |
|---|---|---|
| GET | `/ai-sdr/health` | AI SDR module health. |
| GET | `/ai-sdr/sources` | Source descriptors. |
| GET | `/ai-sdr/dashboard` | Metrics, contacts, filters. |
| GET | `/ai-sdr/contacts/{contact_id}` | Single AI SDR CRM contact profile. |
| POST | `/ai-sdr/contacts/bulk-delete` | Archive contacts from dashboard. |
| POST | `/ai-sdr/contacts/export.csv` | Export selected/default contact rows. |
| POST | `/ai-sdr/imports` | Generic import. |
| GET | `/ai-sdr/imports` | List import batches. |
| GET | `/ai-sdr/imports/{batch_id}` | Import detail with records. |
| POST | `/ai-sdr/contacts/manual` | Manual contact ingestion. |
| POST | `/ai-sdr/contacts` | REST contact ingestion. |
| GET | `/ai-sdr/conversation/states` | Conversation state machine states. |
| POST | `/ai-sdr/conversations` | Start conversation session. |
| GET | `/ai-sdr/conversations/{session_id}` | Get session state/events. |
| POST | `/ai-sdr/conversations/{session_id}/turn` | Add customer message and receive AI reply. |
| POST | `/ai-sdr/calls/outbound` | Start an outbound production AI SDR call. |
| GET | `/ai-sdr/calls` | List process-local call sessions. |
| GET | `/ai-sdr/calls/{call_id}` | Get live call session, transcript, AI Brain, and outcome. |
| POST | `/ai-sdr/calls/{call_id}/control` | Mute, unmute, pause/resume AI, transfer, hang up, or generate summary. |
| POST | `/ai-sdr/calls/{call_id}/transcript` | Inject a transcript line for tests/provider-free QA. |
| POST | `/ai-sdr/calls/{call_id}/complete` | Generate/store final call outcome. |
| GET/POST | `/ai-sdr/calls/twilio/voice` | Twilio TwiML callback. |
| POST | `/ai-sdr/calls/twilio/status` | Twilio call status callback. |
| WS | `/ai-sdr/calls/twilio/media` | Twilio Media Streams WebSocket. |

Import request:

```json
{
  "source_type": "rest_api",
  "contacts": [
    {
      "company_name": "Northstar Dental Studio",
      "contact_name": "Maya Shah",
      "email": "maya@example.com",
      "phone": "+1 555 0100",
      "website": "https://northstar.example",
      "city": "Austin",
      "industry": "Dental Services"
    }
  ],
  "configuration": {
    "source": "partner-api"
  },
  "created_by": "REST API"
}
```

Conversation start:

```json
{
  "contact_id": "crm-lead-id"
}
```

Conversation turn:

```json
{
  "message": "Yes, I have a minute."
}
```

Conversation response includes:

- `session_id`
- `contact_id`
- `state`
- `reply`
- `memory`
- `events`

Outbound call request:

```json
{
  "contact_id": "crm-lead-id",
  "objective": "Qualify need and book a practical website conversion review.",
  "actor": "LeadForge user"
}
```

Call control request:

```json
{
  "action": "pause_ai",
  "actor": "LeadForge user"
}
```

Supported call actions: `mute`, `unmute`, `pause_ai`, `resume_ai`, `transfer_to_owner`, `hang_up`, and `generate_summary`.

Call completion stores transcript, summary, qualification score, interested/not interested, reason, objections, website problems, recommended services, and next follow-up in CRM.

## cURL Examples

```bash
curl -X POST http://localhost:8000/ai-sdr/conversations \
  -H "Content-Type: application/json" \
  -d '{"company":{"business_name":"Acme Clinic","industry":"Healthcare","city":"Austin"},"owner":{"name":"Taylor"}}'
```

```bash
curl -X POST http://localhost:8000/ai-sdr/conversations/{session_id}/turn \
  -H "Content-Type: application/json" \
  -d '{"message":"Are you AI?"}'
```
