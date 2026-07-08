# Security Documentation

## Authentication

Production uses HTTP Basic Auth enforced by middleware when `ENVIRONMENT=production`. Health endpoints remain public for platform readiness checks.

Future SaaS releases should replace Basic Auth with organization-aware user authentication.

## Authorization

Current release does not implement role-based authorization. All authenticated production users can access the platform.

Recommended future roles:

- Admin
- Sales Manager
- SDR
- Viewer
- Integration Bot

## Secrets

Secrets include:

- Database URL/password.
- Apify token.
- Gemini key.
- Google service account JSON.
- Gmail OAuth client secret and refresh token.
- Basic Auth password.
- Twilio auth token.
- Cartesia API key.

Rules:

- Never commit `.env`.
- Store secrets in deployment secret managers.
- Rotate after demos.
- Mask secrets in logs and settings responses.

## API Keys

Provider API keys are backend-only. The frontend should only receive `NEXT_PUBLIC_API_URL`, which is not secret.

AI SDR calling provider keys must remain server-side:

- Twilio callbacks bypass Basic Auth so Twilio can reach them, then validate `X-Twilio-Signature`.
- Keep `TWILIO_VALIDATE_SIGNATURE=true` in public environments.
- Cartesia and Gemini keys are never sent to the browser.

## Rate Limiting

Rate limiting is not currently implemented. Add it before public multi-tenant launch, especially for:

- `/generate-leads`
- `/send-email`
- `/ai-sdr/imports`
- `/ai-sdr/conversations/*`
- `/ai-sdr/calls/outbound`
- `/ai-sdr/calls/*/control`

## CORS

CORS allows configured `FRONTEND_ORIGIN` plus localhost development origins. Production should set `FRONTEND_ORIGIN` exactly to the public frontend URL.

## HTTPS

All production deployments should use HTTPS for:

- App access.
- API calls.
- Tracking URLs.
- OAuth callback/control flows.
- Twilio Media Streams (`wss://`).

## Logging

Logs should support debugging without exposing:

- API keys.
- OAuth refresh tokens.
- Service account JSON.
- Full email bodies unless explicitly needed.
- Customer PII beyond operational necessity.

## Data Protection

LeadForge stores business contact data, emails, and CRM activity. Treat the database as sensitive.

Recommended practices:

- Encrypt managed DB at rest.
- Restrict DB network access.
- Use least-privilege database credentials.
- Back up regularly.
- Define retention/deletion policies.

## AI Transparency

AI SDR must honestly disclose that it is AI when asked. This behavior is implemented in the conversation engine and must remain intact when telephony is added.
