# Backend Architecture Report

## Scope

This review covered every Python module under `backend/app` and
`backend/lead_automation`, the active FastAPI routes, SQLAlchemy persistence,
background jobs, scrapers, AI clients, Google integrations, runtime
configuration, Docker entry point, and the archived legacy automation copy.

No frontend files, API response models, routes, database models, or database
schema files were changed. No scraper or third-party integration was added.

## Current Architecture

The live application is a synchronous FastAPI service with SQLAlchemy
persistence. Lead generation starts as a FastAPI background task and now uses
the following internal pipeline:

1. `LeadSearchService` starts the existing Apify Google Maps actor.
2. `LeadValidationService` applies rating, review-count, duplicate, and
   contactability rules.
3. `ContactEnrichmentService` normalizes and crawls websites, extracts email
   and phone evidence, and uses the existing DuckDuckGo fallback when needed.
4. `SocialEnrichmentService` validates supplied social URLs deterministically.
5. `LeadAnalysisService` performs optional Claude contact extraction, Gemini
   website analysis, and Gemini outreach generation.
6. `LeadPersistenceService` atomically saves the lead, outreach draft, and
   analytics event.

`job_state.py` owns in-memory event queues and persisted job snapshots.
Google Sheets is optional and synchronized in one batch after database saves.
Gmail sending, reply synchronization, analytics, settings, and screenshots
remain separate from the lead pipeline.

### No-Website Enrichment

Leads without a website use the same modular pipeline but skip the website
crawl until a high-confidence website candidate is discovered. Existing
Google Maps fields and grouped DuckDuckGo searches provide candidate emails,
Facebook, Instagram, LinkedIn, YouTube, X/Twitter, TikTok, WhatsApp, and Google
Business links. Candidates are scored against business name, address, city,
state, country, and phone evidence. Low-confidence candidates are discarded,
and the highest-confidence email and profile for each network are selected.
Scores and source evidence are stored in `Lead.raw["confidence"]` so the API
and frontend contracts remain unchanged.

No new scraper or paid integration was added. The existing Apify Maps,
website-crawl, rendered-page, and DuckDuckGo sources were sufficient for this
fallback.

## Problems Found

### Addressed

- A 904-line runner mixed job state, scraping, enrichment, AI, persistence,
  source evidence, and error mapping.
- Static and rendered pages repeated parsing and merge logic.
- Social URL cleanup consumed one Gemini request per lead even though it was
  deterministic.
- Gemini website analysis ran for leads without a valid website.
- Google Sheets was read and written repeatedly for each saved lead.
- Contact discovery recreated its HTTP client for every lead.
- Source-map and social-candidate merging had multiple implementations.
- Scraper, screenshot, job-persistence, and Claude failures were silently
  swallowed in several paths.
- Website and search HTTP clients disabled TLS certificate verification.
- Automatic Gmail synchronization performed blocking network calls on the
  FastAPI event loop and initialized Gmail when no messages required checking.
- Completed in-memory jobs were never released.
- The FastAPI application depended on a qualification function inside the
  landscaping-specific legacy CLI.

### Remaining Production Risks

- FastAPI `BackgroundTasks` and in-memory queues are not durable. A process
  restart loses active work, and multiple API workers cannot share live events.
- Archived legacy automation files duplicate `backend/lead_automation`. They
  appear to preserve the original CLI and were not deleted without a migration
  plan.
- Runtime `ALTER TABLE` logic exists without a real migration tool, and
  `database/schema.sql` is not fully aligned with runtime models.
- The API has no authentication, authorization, tenant isolation, or rate
  limiting. Runtime secrets stored in the settings table are not encrypted.
- Website crawling and screenshots need explicit SSRF protection before the
  API is exposed to untrusted users.
- DuckDuckGo HTML scraping is fragile and provides weak ownership evidence for
  contacts found in snippets.
- A structurally valid social profile URL is not proof that the profile belongs
  to the business. Strong ownership verification is still missing.
- External calls are sequential, so large jobs can be slow. Safe bounded
  concurrency requires provider-specific rate limits and cancellation.
- Unit coverage now protects the core pipeline, but database, Apify, Google
  Sheets, Gmail, SSE, and failure-recovery integration tests are still missing.

## Refactored Files

- `app/runner.py`: thin job orchestration and error mapping.
- `app/job_state.py`: job registry, snapshots, persistence, and cleanup.
- `app/services/lead_search.py`: search and validation.
- `app/services/contact_enrichment.py`: contact and social enrichment.
- `app/services/lead_analysis.py`: AI calls and deterministic fallbacks.
- `app/services/lead_persistence.py`: database save transaction.
- `app/services/lead_pipeline.py`: ordered stage coordination.
- `app/services/events.py`: analytics event creation.
- `app/ai.py`: removed Gemini social normalization.
- `app/main.py` and `app/email_sync.py`: logging and non-blocking reply sync.
- `lead_automation/website_scraper.py`: shared static/rendered parser.
- `lead_automation/source_maps.py`: shared evidence merging.
- `lead_automation/social_links.py`: shared social merging and selection.
- `lead_automation/contact_discovery.py`: shared merging, logging, and TLS.
- `lead_automation/sheets.py`: cached reads and batch-friendly writes.
- `lead_automation/apify_web.py`, `apify_maps.py`, `ai_extractor.py`, and
  `validation.py`: logging, cleanup, and reusable validation.
- `tests/`: backend regression coverage for extraction and pipeline order.

## Existing Scrapers and Data Sources

- Apify `compass/crawler-google-places`: primary business search.
- Direct HTTPS plus BeautifulSoup: homepage, contact, and about-page parsing.
- Apify `apify/website-content-crawler` with Playwright Firefox: rendered-page
  fallback for failed or thin static pages.
- DuckDuckGo HTML results: fallback discovery for websites, email, phone, and
  social URLs.
- Local Playwright Chromium: screenshots only, not contact enrichment.
- Claude: optional structured contact extraction, not a scraper.
- Gemini: website analysis and outreach generation, not a scraper.
- Google Sheets and Gmail: storage/outreach integrations, not scrapers.

## Missing Capabilities

- Durable queue, worker retries, cancellation, and shared event delivery.
- Schema migrations and deployment-time migration checks.
- API authentication, secret encryption, audit controls, and rate limiting.
- SSRF-safe URL resolution and outbound-network policy.
- Email deliverability verification and stronger social ownership checks.
- Metrics, tracing, alerting, and provider quota dashboards.
- Provider contract tests and recorded fixtures for external failures.

## New Scraper or API Recommendations

No new scraper or API is required for this refactor, and none was implemented.
Apollo should not be added just to find social links: its documented strength
is people and organization enrichment, while this pipeline primarily targets
local business contact surfaces.

If Apify is replaced later, evaluate the official Google Places API first. It
supports text search and place details such as phone, rating, and website, but
field selection affects billing and Google usage restrictions must be reviewed:

- https://developers.google.com/maps/documentation/places/web-service/place-details
- https://developers.google.com/maps/documentation/places/web-service/place-id

If outbound email volume becomes significant, an email verification API may be
worth evaluating separately. This would improve deliverability, not discovery,
and introduces credits, privacy review, and another failure dependency.

Existing Apify actor execution remains appropriate for the current design:

- https://docs.apify.com/platform/actors/running

Any new provider should be approved only after a cost, terms, accuracy, data
retention, failure-mode, and API-contract review.

## Verification

- Python compilation passed for the full backend.
- Five regression tests passed.
- Static and rendered extraction parity is covered.
- Pipeline order, persistence, social selection, and reduced Gemini calls are
  covered.
- Live health and read-only API smoke checks passed.
- The OpenAPI document hash is unchanged from the pre-refactor baseline:
  `1D3CF12697278E3FBE948BF8FA4B2472B43DB4800FC94A53870FB9C905E2AF84`.
