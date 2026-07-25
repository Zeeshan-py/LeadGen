# Testing Documentation

## Unit Tests

Backend tests live in `backend/tests`. They cover:

- Lead pipeline behavior.
- Enrichment.
- CRM services.
- Gmail/Google Sheets behavior.
- Outreach generation and sending.
- AI SDR ingestion, dashboard, and conversation engine.

Run:

```powershell
cd backend
.\.venv312\Scripts\python.exe -m pytest
```

## Integration Tests

Current integration tests use SQLite and service-level execution. Recommended additions:

- PostgreSQL integration suite.
- Gmail sandbox tests.
- Google Sheets test spreadsheet.
- Apify mocked/recorded integration tests.

## Manual Tests

Smoke checklist:

1. Load dashboard.
2. Sign up with email/password.
3. Log out and log back in.
4. Start lead generation.
5. Watch SSE progress.
6. Open CRM.
7. Add note/tag/follow-up.
8. Regenerate outreach.
9. Send test email.
10. Sync Gmail replies.
11. Open AI SDR dashboard.
12. Open AI Calling Workspace.
13. Start AI SDR conversation API session.
14. Confirm a second user cannot see the first user's leads, campaigns, CRM records, analytics, or AI SDR imports.

## Regression Tests

Run before shipping:

```powershell
cd backend
.\.venv312\Scripts\python.exe -m pytest
cd ..\frontend
npm run lint
npm run build
```

## Performance Tests

Recommended scenarios:

- 50, 100, 500 lead generation runs.
- Large AI SDR imports.
- CRM list pagination under 10k leads.
- Analytics aggregation under 100k events.

## Security Tests

- Verify email/password auth, logout, refresh, forgot/reset password, and OAuth callbacks.
- Verify protected routes redirect to login.
- Verify user A cannot access user B records by changing IDs in URLs/API payloads.
- Verify CSRF rejection for unsafe cookie-authenticated API calls without `X-CSRF-Token`.
- Verify CORS restrictions.
- Confirm secrets are masked.
- Test invalid Gmail/Sheets credentials.
- Test oversized AI SDR import limits.

## Deployment Tests

- Docker build.
- Alembic migration on clean database.
- `/health/ready`.
- Static frontend served from container.
- Railway public URL health.
- Netlify frontend to hosted backend CORS.
