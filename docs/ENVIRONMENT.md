# Environment Variables

Environment variables are the deployment defaults. Some values can be overridden at runtime through the Settings page and stored in the `settings` table.

## Core Deployment

| Variable | Purpose | Default | Required | Security Notes |
|---|---|---|---|---|
| `POSTGRES_PASSWORD` | Docker Compose PostgreSQL password. | none | Docker | Secret; use long random value. |
| `APP_URL` | Public application URL. | `http://localhost:8000` | Production | Must be HTTPS in production. |
| `APP_PORT` | Host port for app container. | `8000` | No | Avoid public DB exposure. |
| `IMAGE_TAG` | Docker image tag. | `latest` | No | Pin versions for releases. |
| `NEXT_PUBLIC_API_URL` | Browser-visible API URL baked into the static frontend. Leave empty for combined container. | empty | Split frontend hosting | Public value, not secret. |
| `DATABASE_URL` | SQLAlchemy database URL. | local Postgres default | Yes | Secret if it embeds credentials. |
| `FRONTEND_ORIGIN` | Allowed frontend CORS origin. | `http://localhost:8000` | Yes | Must match deployed frontend URL. |
| `PUBLIC_BACKEND_URL` | Public backend URL used in links/tracking. | `http://localhost:8000` | Yes | Use HTTPS publicly. |
| `DATABASE_POOL_SIZE` | SQLAlchemy pool size. | `5` | No | Tune for DB limits. |
| `DATABASE_MAX_OVERFLOW` | SQLAlchemy overflow connections. | `10` | No | Tune for DB limits. |
| `FORWARDED_ALLOW_IPS` | Trusted proxy IPs. | `127.0.0.1` | Production | Avoid `*` unless controlled. |
| `BASIC_AUTH_USERNAME` | Production Basic Auth username. | empty | Production | Secret. |
| `BASIC_AUTH_PASSWORD` | Production Basic Auth password. | empty | Production | Secret. |

## Lead Discovery and AI

| Variable | Purpose | Default | Required | Security Notes |
|---|---|---|---|---|
| `APIFY_API_TOKEN` | Apify API access. | empty | Lead generation | Secret. |
| `APIFY_ACTOR_ID` | Google Maps actor ID. | `compass/crawler-google-places` | No | Provider config. |
| `APIFY_WEB_ACTOR_ID` | Website crawler actor ID. | `apify/website-content-crawler` | No | Provider config. |
| `GEMINI_API_KEY` | Gemini API access. | empty | AI analysis/outreach | Secret. |
| `GEMINI_MODEL` | Gemini model name. | `gemini-2.5-flash` | No | Cost/performance lever. |
| `ANTHROPIC_API_KEY` | Future/legacy Anthropic access. | empty | No | Secret if used. |
| `LEAD_FETCH_TIMEOUT_SECONDS` | HTTP fetch timeout. | `20` | No | Operational tuning. |
| `LEAD_MAX_WEBSITE_PAGES` | Max pages per website scrape. | `5` | No | Cost/time control. |
| `DEFAULT_LEAD_LIMIT` | Default generation limit. | `50` | No | Product tuning. |
| `ENABLE_SCREENSHOT_CAPTURE` | Enables screenshot capture. | `true` | No | May increase storage. |
| `SCREENSHOTS_DIR` | Screenshot storage path. | `./storage/screenshots` | No | Ensure persistent volume if needed. |

## Google Sheets

| Variable | Purpose | Default | Required | Security Notes |
|---|---|---|---|---|
| `GOOGLE_SHEETS_SPREADSHEET_ID` | Target spreadsheet ID. | empty | Sheets sync | Treat as internal identifier. |
| `GOOGLE_SHEETS_SHEET_NAME` | Sheet/tab name. | `LeadForgeLeads` | No | Non-secret. |
| `GOOGLE_SERVICE_ACCOUNT_JSON` | Complete service account JSON. | empty | Sheets sync | Secret; store as single-line env var. |

Example:

```dotenv
GOOGLE_SERVICE_ACCOUNT_JSON={"type":"service_account","project_id":"..."}
```

## Gmail OAuth

| Variable | Purpose | Default | Required | Security Notes |
|---|---|---|---|---|
| `GMAIL_CLIENT_ID` | OAuth client ID. | empty | Gmail sending | Secret-adjacent. |
| `GMAIL_CLIENT_SECRET` | OAuth client secret. | empty | Gmail sending | Secret. |
| `GMAIL_REFRESH_TOKEN` | OAuth refresh token. | empty | Gmail sending/sync | Secret. |
| `GMAIL_SENDER_EMAIL` | Sender account email. | empty | Gmail sending | PII. |
| `GMAIL_REPLY_SYNC_INTERVAL_SECONDS` | Background reply sync interval. | `60` | No | Operational tuning. |
| `AUTO_REPLY_ENABLED` | Sends threaded auto-reply on inbound reply. | `true` | No | Review before production use. |
| `AUTO_REPLY_BODY` | Auto-reply content. | default text | No | Customer-facing copy. |

## AI SDR

| Variable | Purpose | Default | Required | Security Notes |
|---|---|---|---|---|
| `AI_SDR_ENABLED` | Enables AI SDR module. | `true` | No | Feature flag. |
| `AI_SDR_API_PREFIX` | AI SDR route prefix. | `/ai-sdr` | No | Keep stable for frontend. |
| `AI_SDR_DEFAULT_ACTOR` | Default actor for activity records. | `LeadForge AI SDR` | No | Audit label. |
| `AI_SDR_MAX_CONTACTS_PER_IMPORT` | Import size limit. | `1000` | No | Abuse control. |
| `AI_SDR_STORE_RAW_PAYLOADS` | Store raw input payloads. | `true` | No | May include PII. |
| `AI_SDR_DEFAULT_CRM_STAGE` | CRM stage for new SDR contacts. | `new` | No | Workflow tuning. |

## AI SDR Calling

| Variable | Purpose | Default | Required | Security Notes |
|---|---|---|---|---|
| `AI_SDR_CALLING_ENABLED` | Enables the outbound calling runtime. | `true` | No | Disable to prevent calls. |
| `AI_SDR_CALLING_MODE` | `production` or `mock`. | `production` | No | Use `mock` for local demos/tests. |
| `AI_SDR_PUBLIC_WEBSOCKET_URL` | Public WebSocket base URL for Twilio Media Streams. | derived from `PUBLIC_BACKEND_URL` | Production voice | Must be `wss://` publicly, including Railway. |
| `AI_SDR_TELEPHONY_PROVIDER` | Telephony provider implementation. | `twilio` | No | Swappable provider role. |
| `AI_SDR_LLM_PROVIDER` | LLM provider implementation. | `gemini` | No | Swappable provider role. |
| `AI_SDR_SPEECH_PROVIDER` | Speech provider implementation. | `cartesia` | No | Swappable provider role. |
| `AI_SDR_CALL_FROM_NUMBER` | Twilio caller ID number. | empty | Production voice | Use an approved Twilio number. |
| `TWILIO_ACCOUNT_SID` | Twilio API account SID. | empty | Production voice | Secret-adjacent. |
| `TWILIO_AUTH_TOKEN` | Twilio API token and webhook signature secret. | empty | Production voice | Secret. |
| `TWILIO_VALIDATE_SIGNATURE` | Validates Twilio webhook signatures. | `true` | Production | Keep enabled publicly. |
| `AI_SDR_GEMINI_MODEL` | AI SDR calling model. | `gemini-2.5-flash` | No | Cost/latency lever. |
| `CARTESIA_API_KEY` | Cartesia API key. | empty | Production voice | Secret. |
| `CARTESIA_VOICE_ID` | Cartesia voice ID for AI SDR speech. | empty | Production voice | Treat as provider config. |
| `CARTESIA_TTS_MODEL` | Cartesia TTS model. | `sonic-3.5` | No | Provider config. |
| `CARTESIA_STT_MODEL` | Cartesia STT model. | `ink-whisper` | No | Provider config. |
| `CARTESIA_TTS_ENCODING` | TTS audio encoding for telephony. | `pcm_mulaw` | No | Match Twilio media. |
| `CARTESIA_STT_ENCODING` | STT audio encoding from telephony. | `pcm_mulaw` | No | Match Twilio media. |
| `AI_SDR_CALL_SILENCE_TIMEOUT_SECONDS` | Silence window before finalizing utterances. | `1.2` | No | Tune for latency vs interruptions. |
| `AI_SDR_CALL_MAX_DURATION_SECONDS` | Maximum planned call duration. | `1800` | No | Cost and abuse control. |

## Security Guidance

- Never commit `.env`, service account JSON, or OAuth secrets.
- Rotate credentials after demos or public recordings.
- Use platform secret stores in Railway/Netlify/GitHub.
- Avoid logging secret values.
