# Source File Reference

This reference documents the major Python, TypeScript, CSS, Docker, configuration, and schema files in LeadForge. It complements inline docstrings and explains purpose, dependencies, inputs, outputs, side effects, and extension points.

## Root Files

| File | Purpose and Responsibilities | Inputs / Outputs | Dependencies / Side Effects | Future Extensions |
|---|---|---|---|---|
| `README.md` | Product overview and platform entry documentation. | Markdown consumed by contributors/judges. | No runtime effect. | Add final logo/screenshots/license. |
| `.env.example` | Environment variable template. | Deployment variables. | Copied to `.env`; secrets supplied externally. | Add new integration variables as features grow. |
| `Dockerfile` | Production image build for full app. | Source tree, build args. | Builds frontend/backend image. | Multi-stage hardening and SBOM. |
| `docker-compose.yml` | Local/production-like app + Postgres stack. | `.env` values. | Starts Postgres and app containers. | Add worker/cache services. |
| `.dockerignore` | Docker build context exclusions. | Build context. | Reduces image size/secret exposure. | Keep aligned with generated artifacts. |
| `service-account.example.json` | Safe example for Google service account shape. | Developer reference. | No runtime effect. | Replace with docs link if public. |
| `database/schema.sql` | SQL schema reference. | SQL readers/tools. | Not the primary migration source. | Generate from Alembic for drift checks. |
| `scripts/dev.ps1` | Local startup helper. | Local PowerShell environment. | Starts platform dependencies/processes. | Add health checks and teardown. |

## Legacy Automation Archive

These Python files mirror or predate `backend/lead_automation`. They are archived under `legacy/lead_automation` so the project root stays focused on runtime entrypoints and deployment config. The backend package is the production path.

| File | Purpose | Notes |
|---|---|---|
| `legacy/lead_automation/main.py`, `legacy/lead_automation/__main__.py` | Legacy CLI entrypoints. | Keep for compatibility; prefer backend APIs. |
| `legacy/lead_automation/config.py` | Legacy automation configuration. | Backend config is authoritative for SaaS runtime. |
| `legacy/lead_automation/models.py` | Legacy data structures. | Backend SQLAlchemy models are production persistence. |
| `legacy/lead_automation/apify_maps.py`, `legacy/lead_automation/apify_web.py` | Legacy Apify integration modules. | Production equivalents live under `backend/lead_automation`. |
| `legacy/lead_automation/website_scraper.py` | Legacy website scraping. | Production equivalent lives under `backend/lead_automation`. |
| `legacy/lead_automation/ai_extractor.py` | Legacy AI extraction helpers. | Retained for compatibility. |
| `legacy/lead_automation/coverage.py` | Legacy coverage/report helper. | Avoid conflicting with Python `coverage` package naming in new code. |
| `legacy/lead_automation/sheets.py` | Legacy Sheets integration. | Backend Google Sheets modules are preferred. |

## Local and Work Folders

| Folder | Purpose | Notes |
|---|---|---|
| `local/logs` | Historical `.log` and `.err` runtime output. | Ignored by git. New runs may still create root logs if launched by older commands. |
| `local/pids` | Historical process ID files. | Ignored by git. |
| `local/data` | Local SQLite/database snapshots. | Ignored by git. |
| `local/secrets` | Local service-account and generated credential JSON files. | Ignored by git; do not commit real secrets. |
| `local/cache` | Moved Python and pytest cache folders. | Ignored by git. |
| `work/documents` | Generated PDFs, decks, reports, and document build scratch space. | Ignored by git. |

## Backend App

| File | Purpose and Responsibilities | Inputs / Outputs | Dependencies / Side Effects | Future Extensions |
|---|---|---|---|---|
| `backend/app/main.py` | FastAPI app factory/module, platform routes, middleware, health, lead generation, outreach, settings, analytics. | HTTP requests/responses, SSE streams. | Includes CRM and AI SDR routers; writes DB; calls Gmail/Gemini/Sheets. | Split large route groups into routers. |
| `backend/app/config.py` | Pydantic settings for backend runtime. | Environment variables. | Cached settings object. | Add integration/provider config. |
| `backend/app/database.py` | SQLAlchemy `Base`, engine, session, readiness check. | `DATABASE_URL`. | Opens DB connections. | Separate sync/async engines if needed. |
| `backend/app/models.py` | Core SQLAlchemy tables. | ORM access. | Defines migrations target metadata. | Add billing/conversation tables. |
| `backend/app/schemas.py` | Pydantic API contracts. | Route validation/serialization. | Shapes public API. | Generate OpenAPI docs from examples. |
| `backend/app/runner.py` | Lead generation job orchestration. | Generation request payload. | Runs automation, updates jobs/CRM. | Move to external worker. |
| `backend/app/job_state.py` | In-memory job/event state. | Job IDs and snapshots. | Process-local state. | Replace with Redis/Postgres event store. |
| `backend/app/crm.py` | CRM API router. | CRM HTTP requests. | Reads/writes CRM tables. | RBAC and saved views. |
| `backend/app/ai.py` | Gemini analysis/outreach adapter. | Website/lead context. | Calls Gemini API. | Provider abstraction and caching. |
| `backend/app/gmail.py` | Gmail client wrapper. | OAuth credentials, message payloads. | Sends email through Gmail. | OAuth setup UI. |
| `backend/app/email_sync.py` | Gmail reply synchronization. | Gmail threads/messages. | Updates CRM, messages, activities. | Queue and webhook support. |
| `backend/app/google_sheets.py` | Google Sheets validation/sync helpers. | Service account JSON, spreadsheet ID. | Calls Google APIs. | Multi-sheet mapping. |
| `backend/app/settings_store.py` | Effective settings merge logic. | Env settings + DB overrides. | Reads settings table. | Typed settings UI metadata. |
| `backend/app/screenshots.py` | Screenshot capture helpers. | Website URLs. | Uses Playwright/storage. | Object storage support. |

## Backend Services

| File | Purpose |
|---|---|
| `backend/app/services/crm.py` | Stage changes, CRM activity records, tag replacement, contact tracking. |
| `backend/app/services/events.py` | Event construction helpers for pipeline/job workflows. |
| `backend/app/services/lead_pipeline.py` | High-level lead generation pipeline composition. |
| `backend/app/services/lead_persistence.py` | Lead/campaign/outreach persistence and deduplication. |
| `backend/app/services/lead_analysis.py` | AI website analysis and outreach generation orchestration. |
| `backend/app/services/contact_enrichment.py` | Contact/social enrichment logic. |
| `backend/app/services/lead_search.py` | Lead search/filter helpers. |
| `backend/app/services/__init__.py` | Service package marker. |

## Lead Automation Package

| File | Purpose |
|---|---|
| `backend/lead_automation/main.py`, `__main__.py` | CLI/package entrypoints. |
| `backend/lead_automation/config.py` | Automation-specific configuration. |
| `backend/lead_automation/models.py` | Data structures for discovered leads. |
| `backend/lead_automation/apify_maps.py` | Apify Google Maps sourcing. |
| `backend/lead_automation/apify_web.py` | Apify web crawling integration. |
| `backend/lead_automation/website_scraper.py` | Website fetch/scrape utilities. |
| `backend/lead_automation/contact_discovery.py` | Contact extraction/discovery. |
| `backend/lead_automation/ai_extractor.py` | AI-assisted extraction helpers. |
| `backend/lead_automation/confidence.py` | Confidence scoring. |
| `backend/lead_automation/validation.py` | Data validation/normalization helpers. |
| `backend/lead_automation/source_maps.py` | Source mapping utilities. |
| `backend/lead_automation/social_links.py` | Social profile discovery. |
| `backend/lead_automation/sheets.py` | Google Sheets export/sync helpers. |
| `backend/lead_automation/coverage.py` | Coverage/reporting helper. |
| `backend/lead_automation/__init__.py` | Package marker. |

## AI SDR Backend

| File | Purpose and Responsibilities |
|---|---|
| `backend/ai_sdr/config.py` | AI SDR-specific settings and feature flags. |
| `backend/ai_sdr/models.py` | AI SDR import batch/record tables. |
| `backend/ai_sdr/schemas.py` | AI SDR API contracts, dashboard types, conversation types. |
| `backend/ai_sdr/api/router.py` | AI SDR routes for health, sources, imports, dashboard, contacts, export, conversations. |
| `backend/ai_sdr/services/sources.py` | Supported source descriptors. |
| `backend/ai_sdr/services/normalization.py` | Raw contact normalization, dedupe keys, source tags. |
| `backend/ai_sdr/services/ingestion.py` | Import batch lifecycle and CRM writes. |
| `backend/ai_sdr/services/dashboard.py` | Dashboard stats, filters, contact profiles, archive action. |
| `backend/ai_sdr/infrastructure/crm_gateway.py` | Boundary for writing normalized SDR contacts into shared CRM. |
| `backend/ai_sdr/conversation/conversation_manager.py` | State machine, turn handling, structured events. |
| `backend/ai_sdr/conversation/memory_manager.py` | In-memory sessions, transcript, needs, objections, qualification state. |
| `backend/ai_sdr/conversation/sales_strategy.py` | Natural SDR wording strategy. |
| `backend/ai_sdr/conversation/objection_handler.py` | Objection detection and honest AI disclosure. |
| `backend/ai_sdr/conversation/qualification.py` | Qualification scoring and questions. |
| `backend/ai_sdr/conversation/closing_strategy.py` | Closing, follow-up, goodbye language. |
| `backend/ai_sdr/conversation/company_information.py` | Business context extraction. |
| `backend/ai_sdr/conversation/owner_information.py` | Owner/contact context extraction. |

## Backend Tests and Migrations

| File | Purpose |
|---|---|
| `backend/tests/test_ai_sdr.py` | AI SDR ingestion, dashboard, contact profile, conversation engine tests. |
| `backend/tests/test_crm.py` | CRM behavior tests. |
| `backend/tests/test_enrichment.py` | Enrichment behavior tests. |
| `backend/tests/test_google_sheets_credentials.py` | Google Sheets credential parsing/validation tests. |
| `backend/tests/test_outreach_and_email.py` | Outreach/Gmail tests. |
| `backend/tests/test_pipeline.py` | Pipeline tests. |
| `backend/migrations/env.py` | Alembic migration environment. |
| `backend/migrations/script.py.mako` | Alembic migration template. |
| `backend/migrations/versions/*.py` | Database migrations. |
| `backend/alembic.ini` | Alembic configuration. |
| `backend/Dockerfile` | Backend image definition. |
| `backend/entrypoint.sh` | Container startup/migration script. |
| `backend/requirements.txt` | Backend Python dependencies. |

## Frontend App

| File | Purpose |
|---|---|
| `frontend/src/app/layout.tsx` | Root layout, fonts, shell, providers. |
| `frontend/src/app/globals.css` | Tailwind/theme/global styles. |
| `frontend/src/app/page.tsx` | Public landing page. |
| `frontend/src/app/dashboard/page.tsx` | Dashboard home. |
| `frontend/src/app/login/page.tsx` | Login page. |
| `frontend/src/app/signup/page.tsx` | Sign-up page. |
| `frontend/src/app/forgot-password/page.tsx` | Forgot-password page. |
| `frontend/src/app/reset-password/page.tsx` | Reset-password page. |
| `frontend/src/app/lead-generator/page.tsx` | Lead generation UI and SSE progress. |
| `frontend/src/app/leads/page.tsx` | Leads list/export UI. |
| `frontend/src/app/crm/page.tsx` | CRM workspace route. |
| `frontend/src/app/campaigns/page.tsx` | Campaigns page. |
| `frontend/src/app/outreach/page.tsx` | Outreach page. |
| `frontend/src/app/analytics/page.tsx` | Analytics page. |
| `frontend/src/app/settings/page.tsx` | Settings/integration health page. |
| `frontend/src/app/ai-sdr/page.tsx` | AI SDR dashboard route. |
| `frontend/src/app/ai-sdr/call/page.tsx` | Static-export-compatible AI Calling route. |

## Frontend Libraries and Components

| File | Purpose |
|---|---|
| `frontend/src/lib/api.ts` | Main frontend API client. |
| `frontend/src/lib/auth.tsx` | Auth context and session actions. |
| `frontend/src/lib/http.ts` | Cookie/CSRF-aware fetch helper. |
| `frontend/src/lib/types.ts` | Main frontend TypeScript contracts. |
| `frontend/src/lib/utils.ts` | Shared utility helpers. |
| `frontend/src/lib/format.ts` | Formatting helpers. |
| `frontend/src/lib/markets.ts` | Market/location constants. |
| `frontend/src/hooks/use-mobile.ts` | Responsive/mobile hook. |
| `frontend/src/components/app-shell.tsx` | Application shell and navigation. |
| `frontend/src/components/route-shell.tsx` | Public/protected route shell and redirect guard. |
| `frontend/src/components/metric-card.tsx` | Dashboard metric card. |
| `frontend/src/components/chart-panel.tsx` | Chart wrapper component. |
| `frontend/src/components/status-badge.tsx` | Status badge rendering. |
| `frontend/src/components/pipeline-progress.tsx` | Pipeline progress UI. |
| `frontend/src/components/crm/*.tsx` | CRM kanban, table, toolbar, cards, stage select, and detail sheet. |
| `frontend/src/components/ui/*.tsx` | shadcn/ui primitives. |

## AI SDR Frontend

| File | Purpose |
|---|---|
| `frontend/ai_sdr/api.ts` | AI SDR API client. |
| `frontend/ai_sdr/types.ts` | AI SDR TypeScript contracts. |
| `frontend/ai_sdr/index.ts` | Module exports. |
| `frontend/ai_sdr/components/ai-sdr-workspace.tsx` | AI SDR dashboard/table/profile UI. |
| `frontend/ai_sdr/components/ai-calling-workspace.tsx` | Full-screen mock AI calling UI. |
| `frontend/ai_sdr/components/ai-calling-route.tsx` | Query-param route adapter for static export. |
| `frontend/ai_sdr/README.md` | Frontend module boundary documentation. |

## Frontend Config

| File | Purpose |
|---|---|
| `frontend/package.json` | Scripts and dependencies. |
| `frontend/package-lock.json` | Locked dependency graph. |
| `frontend/next.config.ts` | Static export and image config. |
| `frontend/tsconfig.json` | TypeScript config. |
| `frontend/eslint.config.mjs` | ESLint config. |
| `frontend/postcss.config.mjs` | PostCSS/Tailwind config. |
| `frontend/components.json` | shadcn/ui config. |
| `frontend/Dockerfile` | Frontend image/build definition. |

## Source Documentation Policy

When adding or editing source files:

- Add module-level docstrings for Python modules with non-obvious responsibilities.
- Add class/function docstrings for service boundaries, orchestration, data models, and external integration code.
- Avoid comments that restate obvious code.
- Document side effects such as database writes, external API calls, background tasks, email sending, and file storage.
- Update this file and the relevant module/API/database docs when behavior changes.
