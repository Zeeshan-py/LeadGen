---
name: gmaps-lead-automation
description: Google Maps lead-generation workflow — Apify discovery, website enrichment, AI contact extraction, and Google Sheets sync for any geography and business type.
allowed-tools: Bash, Read, Write, Edit, Glob, Grep
---

# Google Maps Lead Automation

## Objective
Discover and qualify local businesses via Google Maps, enrich contact data from their websites, and sync deduplicated leads to Google Sheets. Designed to run incrementally over a large geography.

## Constraints
- Queries must be narrow — Apify bills per result, so don't rely on post-filter cleanup
- Never embed location in `searchStringsArray`; pass geography as a separate Apify field
- Never enable `maximumLeadsEnrichmentRecords` — it's a cost multiplier
- Skip businesses with rating < 3.0 and no website before crawling

## Workflow
1. Load `.tmp/lead_config.json` — if missing, prompt for business types, exclusion signals, and geography, then save
2. Break geography into sub-regions; propose sequence to user
3. Build one Apify query per business type per sub-region
4. Run Apify Google Maps scraper with hardcoded cost-control parameters
5. Apply Google Business Gate (rating, website presence)
6. Apply business-type filter as secondary catch for ambiguous query matches
7. Crawl business websites for contact data (homepage + `/contact`, `/about`, `/team`)
8. Use AI to normalize owner/contact info where website data is ambiguous
9. Upsert deduplicated rows to Google Sheets
10. Mark sub-region complete in `.tmp/coverage.json`; skip completed sub-regions on future runs

## Tools / APIs
- **Apify** — Google Maps Places Scraper
- **Google Sheets API** — lead output and upsert
- **Claude API** — contact normalization (only where needed)

## Output Schema

| Column | Description |
|---|---|
| `dedupe_key` | Internal dedup identifier |
| `business_name` | Name from Google Maps |
| `lead_segment` | Business type from config |
| `owner_or_contact` | Primary contact name |
| `email` | Contact email |
| `phone` | Contact phone |
| `website` | Business website URL |
| `social_media` | Social profile URLs |
| `google_maps_url` | Google Maps listing URL |
| `coverage_market` | Sub-region this lead came from |
| `search_query` | Apify query that surfaced this lead |
| `pages_scraped` | Pages crawled |
| `enrichment_status` | `google_only` / `website_crawled` / `ai_enriched` / `partial_timeout` |

## Website Enrichment Notes
- crawl homepage plus likely contact pages like `contact`, `about`, or `team`
- support Cloudflare-protected email decoding
- tolerate blocked sites and timeouts
- if a lead is still qualified, keep it as `partial_timeout` when appropriate