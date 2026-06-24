# LeadForge AI

LeadForge AI is a private internal lead generation command center. It wraps the existing Python automation with a FastAPI backend, PostgreSQL persistence, Google Sheets sync, Gmail outreach, and a Next.js 15 dashboard.

## What Is Included

- `frontend/` - Next.js 15, TypeScript, TailwindCSS, shadcn/ui, Framer Motion
- `backend/` - FastAPI API wrapping the existing Python automation in `backend/lead_automation`
- `database/schema.sql` - PostgreSQL schema for leads, campaigns, outreach, analytics, settings, and jobs
- `scripts/dev.ps1` - local helper for starting Postgres, backend, and frontend
- `docker-compose.yml` - local full-stack Docker setup

## Core Flow

1. Enter City, State, Country, Business Type, and Max Leads.
2. `POST /generate-leads` starts a background job.
3. The frontend subscribes to `/generate-leads/{job_id}/events` for live pipeline progress.
4. The backend uses Apify Google Maps, website scraping, optional existing Claude contact extraction, Gemini website analysis/outreach, Google Sheets sync, and PostgreSQL upsert.
5. Leads, campaigns, outreach drafts, analytics, and settings are available from the dashboard.

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
- `GOOGLE_SERVICE_ACCOUNT_FILE` or `GOOGLE_SERVICE_ACCOUNT_JSON`

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

LeadForge supports Google Sheets service account credentials in two ways.

Local file setup:

1. Download the service account JSON from Google Cloud.
2. Place it at one of these paths:
   - `backend/service-account.json`
   - `service-account.json`
3. Set:

```powershell
GOOGLE_SERVICE_ACCOUNT_FILE=./service-account.json
GOOGLE_SHEETS_SPREADSHEET_ID=your_spreadsheet_id
```

Cloud setup for Railway, Docker, or any host without file uploads:

1. Copy the full service account JSON.
2. Store it as a single environment variable:

```powershell
GOOGLE_SERVICE_ACCOUNT_JSON={"type":"service_account",...}
GOOGLE_SHEETS_SPREADSHEET_ID=your_spreadsheet_id
```

Share the target spreadsheet with the service account `client_email` as an editor. You can verify the connection at:

```text
GET /health/google
```

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

```powershell
docker compose up --build
```

Frontend runs on `http://localhost:3000`; backend runs on `http://localhost:8000`.

## Deployment

Railway backend:

- Deploy `backend/Dockerfile`.
- Set `DATABASE_URL` to Railway Postgres.
- Add the API, Google, Gmail, and Apify environment variables.
- Set `GOOGLE_SERVICE_ACCOUNT_JSON` to the full service account JSON so Railway works without uploading a JSON file.
- Set `PUBLIC_BACKEND_URL` to the Railway backend URL.
- Set `FRONTEND_ORIGIN` to the Vercel frontend URL.

Vercel frontend:

- Deploy `frontend/`.
- Set `NEXT_PUBLIC_API_URL` to the Railway backend URL.

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

## Existing Automation

The original Python files are copied unchanged into `backend/lead_automation/` and imported by the FastAPI orchestration layer. The dashboard wrapper does not replace the working Apify, scraping, contact extraction, deduplication, or Sheets logic.
