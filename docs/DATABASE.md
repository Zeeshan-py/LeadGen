# Database Documentation

LeadForge uses PostgreSQL in production and SQLite in tests. SQLAlchemy models are in `backend/app/models.py` and `backend/ai_sdr/models.py`; Alembic migrations are in `backend/migrations/versions`.

## Entity Relationship Diagram

```mermaid
erDiagram
    campaigns ||--o{ leads : contains
    campaigns ||--o{ outreach : groups
    crm_users ||--o{ leads : assigned
    leads ||--o{ outreach : has
    leads ||--o{ lead_notes : has
    leads ||--o{ lead_activities : records
    leads ||--o{ email_messages : has
    outreach ||--o{ email_messages : relates
    crm_tags ||--o{ lead_tags : maps
    leads ||--o{ lead_tags : maps
    ai_sdr_contact_batches ||--o{ ai_sdr_contact_records : contains
    leads ||--o{ ai_sdr_contact_records : crm_target
```

## Tables

### `campaigns`

Groups lead generation runs.

| Field | Purpose |
|---|---|
| `id` | UUID primary key. |
| `name` | Campaign name. |
| `city`, `state`, `country`, `continent` | Market geography. |
| `business_type` | Target industry/niche. |
| `status` | Draft/running/completed style lifecycle. |
| `max_leads` | Requested cap. |
| `leads_generated`, `emails_sent`, `replies` | Counters. |
| `created_at`, `updated_at` | Timestamps. |

Indexes: name, business_type, status.

### `crm_users`

Assignable CRM users.

Fields: `id`, `name`, `email`, `initials`, `is_active`, timestamps.
Constraint: unique `email`.

### `crm_tags`

Reusable CRM tags.

Fields: `id`, `name`, `color`, timestamps.
Constraint: unique `name`.

### `leads`

Central CRM account/contact table.

Fields include:

- Identity: `id`, `campaign_id`, `dedupe_key`
- Business: `business_name`, `business_type`, `website`, `google_maps_url`
- Contact: `contact_name`, `email`, `phone`
- Location: `location`, `city`, `state`, `country`
- AI analysis: `website_score`, `opportunity_score`, `website_problems`, `website_summary`, `improvement_suggestions`
- CRM lifecycle: `lead_status`, `crm_stage`, `outreach_status`, `assigned_user_id`, `last_contacted_at`, `next_follow_up_at`
- Metadata: `notes`, `tags`, `social_links`, `social_status`, `screenshot_url`, `source`, `raw`, timestamps

Constraint: unique `dedupe_key`.

### `lead_tags`

Many-to-many join table between leads and CRM tags.

Fields: `lead_id`, `tag_id`, `created_at`.
Primary key: `(lead_id, tag_id)`.

### `lead_notes`

User notes on CRM leads.

Fields: `id`, `lead_id`, `body`, `created_by`, timestamps.

### `lead_activities`

Immutable CRM activity timeline.

Fields: `id`, `lead_id`, `event_type`, `title`, `description`, `actor`, `metadata`, `created_at`.

### `outreach`

AI-generated outreach drafts and email lifecycle.

Fields:

- `id`, `lead_id`, `campaign_id`
- `subject_line`
- `personalized_first_line`
- `cold_email`
- `follow_up_1`
- `follow_up_2`
- `selected_version`
- `status`
- Gmail identifiers: `gmail_message_id`, `gmail_thread_id`, `tracking_id`
- Lifecycle timestamps: `sent_at`, `opened_at`, `replied_at`, `bounced_at`
- `failed_reason`, timestamps

### `email_messages`

Synced Gmail messages.

Fields: `id`, `lead_id`, `outreach_id`, `gmail_message_id`, `gmail_thread_id`, `message_id_header`, `direction`, `from_email`, `to_email`, `subject`, `body_text`, `body_html`, `snippet`, `message_at`, `created_at`.
Constraint: unique `gmail_message_id`.

### `analytics`

Platform event records.

Fields: `id`, `event_type`, `lead_id`, `campaign_id`, `metadata`, `created_at`.

### `settings`

Runtime settings overrides.

Fields: `key`, `value`, `is_secret`, `updated_at`.

### `lead_generation_jobs`

Background job tracking.

Fields: `id`, `campaign_id`, `status`, `city`, `state`, `country`, `continent`, `business_type`, `website_mode`, `max_leads`, `progress`, `lead_counter`, `success_counter`, `failure_counter`, `error`, `created_at`, `finished_at`.

### `ai_sdr_contact_batches`

AI SDR import batch metadata.

Fields: `id`, `source_type`, `status`, `total_count`, `normalized_count`, `stored_count`, `duplicate_count`, `failed_count`, `created_by`, `configuration`, `error`, timestamps.

Indexes: source/status.

### `ai_sdr_contact_records`

AI SDR per-contact import record.

Fields: `id`, `batch_id`, `crm_lead_id`, `source_type`, `external_id`, `status`, `dedupe_key`, `normalized`, `raw`, `errors`, timestamps.

Indexes: batch/status, CRM lead ID, source type, external ID, dedupe key.

## Relationships

- Campaigns own generated leads and outreach.
- Leads own CRM notes, activities, emails, outreach, tags, and AI SDR import records.
- Outreach can own Gmail message records.
- AI SDR import records point to CRM leads after normalization.

## Future Migrations

- Persistent conversation session tables.
- Tenant/organization tables.
- API token table.
- Billing/subscription tables.
- Job queue/task tables.
- Integration connection metadata.
