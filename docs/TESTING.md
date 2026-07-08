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
2. Start lead generation.
3. Watch SSE progress.
4. Open CRM.
5. Add note/tag/follow-up.
6. Regenerate outreach.
7. Send test email.
8. Sync Gmail replies.
9. Open AI SDR dashboard.
10. Open AI Calling Workspace.
11. Start AI SDR conversation API session.

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

- Verify production Basic Auth.
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
