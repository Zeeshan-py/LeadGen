# LeadForge AI

LeadForge AI is a private internal lead generation command center. It wraps the existing Python automation with a FastAPI backend, PostgreSQL persistence, Google Sheets sync, Gmail outreach, and a Next.js 15 dashboard.

## What Is Included

- `frontend/` - Next.js 15, TypeScript, TailwindCSS, shadcn/ui, Framer Motion
- `backend/` - FastAPI API wrapping the existing Python automation in `backend/lead_automation`
- `database/schema.sql` - PostgreSQL schema for leads, campaigns, outreach, analytics, settings, and jobs
- `scripts/dev.ps1` - local helper for starting Postgres, backend, and frontend
- `Dockerfile` - production image containing the exported dashboard and API
- `docker-compose.yml` - production-like app and PostgreSQL stack

## Core Flow

1. Enter City, State, Country, Business Type, and Max Leads.
2. `POST /generate-leads` starts a background job.
3. The frontend subscribes to `/generate-leads/{job_id}/events` for live pipeline progress.
4. The backend uses Apify Google Maps, website scraping, optional existing Claude contact extraction, Gemini website analysis/outreach, Google Sheets sync, and PostgreSQL upsert.
5. Leads, campaigns, outreach drafts, analytics, and settings are available from the dashboard.

## CRM

The built-in CRM is available at `/crm` and keeps lead management inside
LeadForge:

- Kanban and table views across New, Qualified, Email Generated, Email Sent,
  Opened, Replied, Interested, Meeting Scheduled, Won, Lost, and Archived.
- Search and filters for status, country, industry, assigned user, creation
  date, and last-contacted date.
- Relational PostgreSQL records for CRM users, tags, notes, activity events,
  and Gmail messages.
- Lead detail sheets with company/contact details, AI draft history, full Gmail
  conversations, notes, follow-up scheduling, and an immutable activity
  timeline.
- Automatic Gmail reply synchronization using
  `GMAIL_REPLY_SYNC_INTERVAL_SECONDS`, with Gmail message/thread IDs persisted
  and lead stages advanced when messages are sent, opened, or replied to.

## Environment

Copy `.env.example` to `.env` and fill in the values:

```powershell
Copy-Item .env.example .env
```

Required for lead generation:

- `DATABASE_URL`
- `APIFY_API_TOKEN`
- `GEMINI_API_KEY`
- `GOOGLE_SHEETS_SPREADSHEET_ID`
- `GOOGLE_SERVICE_ACCOUNT_JSON`

Required for Gmail sending:

- `GMAIL_CLIENT_ID`
- `GMAIL_CLIENT_SECRET`
- `GMAIL_REFRESH_TOKEN`
- `GMAIL_SENDER_EMAIL`

Optional Gmail automation:

- `GMAIL_REPLY_SYNC_INTERVAL_SECONDS` - background reply-check interval, default `60`
- `AUTO_REPLY_ENABLED` - send an automatic threaded reply when a client replies, default `true`
- `AUTO_REPLY_BODY` - body text for the automatic reply

The Settings page can store runtime overrides in PostgreSQL. Environment variables remain the deployment defaults.

### Google Sheets Credentials

LeadForge reads Google Sheets credentials only from the environment, so no
credential file is needed in Railway or Docker:

```dotenv
GOOGLE_SERVICE_ACCOUNT_JSON={"type":"service_account",...}
GOOGLE_SHEETS_SPREADSHEET_ID=your_spreadsheet_id
```

Share the target spreadsheet with the service account `client_email` as an editor. You can verify the connection at:

```text
GET /health/google
```

If `GOOGLE_SERVICE_ACCOUNT_JSON` is missing or invalid, the application logs a
clear warning and continues with PostgreSQL storage while Google Sheets remains
disabled.

### Railway

Deploy the root `Dockerfile`, add a Railway PostgreSQL service, and configure
the application variables from `.env.example`. Set
`GOOGLE_SERVICE_ACCOUNT_JSON` to the complete service account JSON object as a
single environment variable. Do not upload or mount `service-account.json`.

The Settings page also includes a Google Sheets Status card and a Test Google Sheets Connection button.

## Local Development

Start Postgres:

```powershell
docker compose up -d postgres
```

Backend:

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python -m playwright install chromium
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Frontend:

```powershell
cd frontend
npm install
npm run dev
```

Open [http://localhost:3000](http://localhost:3000).

## Docker

Set at least these values in `.env`:

```dotenv
POSTGRES_PASSWORD=use-a-long-url-safe-random-password
BASIC_AUTH_USERNAME=admin
BASIC_AUTH_PASSWORD=use-another-long-random-password
APP_URL=http://localhost:8000
```

Then build and start the complete application:

```powershell
docker compose up -d --build
docker compose ps
```

Open `http://localhost:8000`. The browser will request the Basic Auth
credentials from `.env`. PostgreSQL is private to the Compose network and is
persisted in the `leadgen_postgres` volume.

The container runs `alembic upgrade head` before starting the API. Readiness is
available at `GET /health/ready`; liveness is available at `GET /health/live`.

### Docker Hub

Build and push the requested image manually:

```powershell
docker build -t zeeshanpy/leadgen:latest .
docker login --username zeeshanpy
docker push zeeshanpy/leadgen:latest
```

GitHub Actions can publish the same image. Add a repository secret named
`DOCKERHUB_TOKEN`, then run the **Publish Docker image** workflow or push a
version tag such as `v1.0.0`.

## Deployment

For a Linux server with Docker:

```bash
git clone https://github.com/Zeeshan-py/LeadGen.git
cd LeadGen
cp .env.example .env
# Edit .env with production credentials and an https APP_URL.
docker compose pull
docker compose up -d
```

Place the app behind an HTTPS reverse proxy or a platform load balancer. Set
`FORWARDED_ALLOW_IPS` to the trusted proxy address/range, not `*`, and set
`APP_URL`, `FRONTEND_ORIGIN`, and `PUBLIC_BACKEND_URL` to the public HTTPS URL.

Keep `WEB_CONCURRENCY=1`: generation jobs and SSE delivery currently use
in-process state. Scaling to multiple replicas requires an external queue and
shared event transport.

Back up PostgreSQL regularly:

```bash
docker compose exec -T postgres pg_dump -U leadgen -d leadgen -Fc > leadgen.dump
```

## API

- `POST /generate-leads`
- `GET /generate-leads/latest`
- `GET /generate-leads/{job_id}`
- `GET /generate-leads/{job_id}/events`
- `GET /get-leads`
- `PATCH /get-leads/{lead_id}`
- `GET /get-leads/export.csv`
- `GET /get-campaigns`
- `POST /get-campaigns`
- `GET /outreach`
- `POST /outreach/{lead_id}/regenerate`
- `POST /send-email`
- `POST /send-email/sync-statuses`
- `GET /get-analytics`
- `GET /settings`
- `PUT /settings`
- `GET /health/google`
- `GET /crm/leads`
- `GET /crm/leads/{lead_id}`
- `PATCH /crm/leads/{lead_id}`
- `POST /crm/leads/{lead_id}/notes`
- `PUT /crm/leads/{lead_id}/tags`
- `POST /crm/leads/{lead_id}/sync-gmail`
- `GET /crm/users`
- `POST /crm/users`

## Existing Automation

The original Python files are copied unchanged into `backend/lead_automation/` and imported by the FastAPI orchestration layer. The dashboard wrapper does not replace the working Apify, scraping, contact extraction, deduplication, or Sheets logic.
