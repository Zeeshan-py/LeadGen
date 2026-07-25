# Security Documentation

## Authentication

LeadForge uses account-based authentication with JWT access cookies, server-side refresh tokens, email/password login, Google OAuth, GitHub OAuth, logout, and password reset tokens. Health readiness endpoints remain public for platform checks.

Admin access is not a separate login system. A user is marked admin only when the logged-in email matches `ADMIN_EMAIL`; the admin email/password are configured with environment variables.

## Authorization

The product intentionally uses a simple private-workspace model:

- One account equals one private workspace.
- Every user-owned table has `user_id`.
- API routes filter by the authenticated user's ID.
- No organizations, teams, invitations, collaboration, or shared workspaces are implemented.

## Secrets

Secrets include:

- Database URL/password.
- Apify token.
- Gemini key.
- Google service account JSON.
- Gmail OAuth client secret and refresh token.
- JWT signing secret.
- Admin password.
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

- Twilio callbacks bypass user authentication so Twilio can reach them, then validate `X-Twilio-Signature`.
- Keep `TWILIO_VALIDATE_SIGNATURE=true` in public environments.
- Cartesia and Gemini keys are never sent to the browser.

## Rate Limiting

Login, sign up, and forgot-password routes include in-memory rate limiting. Add durable shared rate limiting before horizontal public scaling, especially for:

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
