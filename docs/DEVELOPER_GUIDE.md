# Developer Guide

## Project Setup

Clone the repository, copy `.env.example` to `.env`, then install backend and frontend dependencies.

```powershell
Copy-Item .env.example .env
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python -m playwright install chromium
cd ..\frontend
npm install
```

## Running Locally

Backend:

```powershell
cd backend
.\.venv\Scripts\Activate.ps1
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Frontend:

```powershell
cd frontend
npm run dev
```

Docker Postgres:

```powershell
docker compose up -d postgres
```

## Code Standards

- Keep backend modules small and service-oriented.
- Use Pydantic schemas for request/response contracts.
- Use SQLAlchemy models for persistence.
- Use explicit service boundaries for CRM, AI SDR, enrichment, and persistence.
- Use TypeScript types for frontend API contracts.
- Prefer existing UI primitives and app patterns before creating new ones.

## Folder Naming

| Area | Convention |
|---|---|
| Backend app | `backend/app/<domain>.py` or `backend/app/services/<service>.py` |
| AI SDR | `backend/ai_sdr/<api|services|conversation|infrastructure>` |
| Lead automation | `backend/lead_automation/<capability>.py` |
| Frontend pages | `frontend/src/app/<route>/page.tsx` |
| Feature components | `frontend/src/components/<domain>/` |
| AI SDR frontend | `frontend/ai_sdr/` |

## Dependency Injection

FastAPI dependencies are used for database sessions:

```python
def route(db: Session = Depends(get_db)):
    return Service(db).execute()
```

Do not instantiate database engines inside route handlers. Use `SessionLocal` through `get_db` or explicit sessions in tests.

## Configuration

Backend configuration is defined in:

- `backend/app/config.py`
- `backend/ai_sdr/config.py`

Use environment variables for deployment defaults and the `settings` table for runtime overrides where supported.

## Testing

Backend:

```powershell
cd backend
.\.venv312\Scripts\python.exe -m pytest
```

Frontend:

```powershell
cd frontend
npm run lint
npm run build
```

## Docker

```powershell
docker compose up -d --build
```

The root Dockerfile builds the frontend, copies static output into the backend image, runs migrations, then starts FastAPI.

## Debugging

| Symptom | Check |
|---|---|
| Frontend cannot reach API | `NEXT_PUBLIC_API_URL`, backend port, CORS `FRONTEND_ORIGIN` |
| Database readiness fails | `DATABASE_URL`, Postgres health, migrations |
| Google Sheets disabled | `GOOGLE_SERVICE_ACCOUNT_JSON`, spreadsheet sharing |
| Gmail send fails | OAuth client, refresh token, sender email |
| Generation stalls | Apify token, network, backend logs, SSE event stream |
| Next build fails while dev server runs | Stop `next dev`, remove `.next`, rebuild |

## Adding Features

1. Identify module ownership.
2. Add schema contracts.
3. Add service logic.
4. Add route.
5. Add frontend API client call if user-facing.
6. Add UI.
7. Add tests.
8. Update docs.

## Adding APIs

- Put CRM APIs in `backend/app/crm.py`.
- Put AI SDR APIs in `backend/ai_sdr/api/router.py`.
- Put platform APIs in `backend/app/main.py` only when they are cross-cutting.
- Always include response models where practical.

## Adding Database Models

1. Add SQLAlchemy model.
2. Create Alembic migration.
3. Add tests with SQLite when possible.
4. Document table in `docs/DATABASE.md`.

## Adding Frontend Pages

1. Add `frontend/src/app/<route>/page.tsx`.
2. Use the existing `AppShell`.
3. Add navigation in `frontend/src/components/app-shell.tsx`.
4. Add API client functions in `frontend/src/lib/api.ts` or the module-specific client.
5. Validate with lint and build.

## Coding Conventions

- Use ASCII unless a file already uses Unicode and there is a reason.
- Keep comments meaningful and sparse.
- Prefer typed data contracts over ad hoc dictionaries.
- Use existing CRM helpers for stage/activity changes.
- Do not import AI SDR from Lead Generator or Lead Generator from AI SDR.
- Avoid hidden side effects in constructors.
