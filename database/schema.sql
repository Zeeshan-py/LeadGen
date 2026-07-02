CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

CREATE TABLE IF NOT EXISTS campaigns (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  name VARCHAR(180) NOT NULL,
  city VARCHAR(120) DEFAULT '',
  state VARCHAR(120) DEFAULT '',
  country VARCHAR(120) DEFAULT '',
  continent VARCHAR(80) DEFAULT '',
  business_type VARCHAR(160) NOT NULL,
  status VARCHAR(40) DEFAULT 'draft',
  max_leads INTEGER DEFAULT 50,
  leads_generated INTEGER DEFAULT 0,
  emails_sent INTEGER DEFAULT 0,
  replies INTEGER DEFAULT 0,
  created_at TIMESTAMPTZ DEFAULT now(),
  updated_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS crm_users (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  name VARCHAR(160) NOT NULL,
  email VARCHAR(320) NOT NULL DEFAULT '' UNIQUE,
  initials VARCHAR(8) NOT NULL DEFAULT '',
  is_active BOOLEAN NOT NULL DEFAULT true,
  created_at TIMESTAMPTZ DEFAULT now(),
  updated_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS leads (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  campaign_id UUID REFERENCES campaigns(id) ON DELETE SET NULL,
  dedupe_key VARCHAR(255) NOT NULL UNIQUE,
  business_name VARCHAR(240) NOT NULL,
  contact_name VARCHAR(180) DEFAULT '',
  website VARCHAR(500) DEFAULT '',
  google_maps_url VARCHAR(800) DEFAULT '',
  email VARCHAR(320) DEFAULT '',
  phone VARCHAR(80) DEFAULT '',
  location VARCHAR(500) DEFAULT '',
  city VARCHAR(120) DEFAULT '',
  state VARCHAR(120) DEFAULT '',
  country VARCHAR(120) DEFAULT '',
  continent VARCHAR(80) DEFAULT '',
  business_type VARCHAR(160) DEFAULT '',
  website_score INTEGER DEFAULT 0,
  opportunity_score INTEGER DEFAULT 0,
  website_problems JSONB DEFAULT '[]'::jsonb,
  website_summary TEXT DEFAULT '',
  improvement_suggestions JSONB DEFAULT '[]'::jsonb,
  lead_status VARCHAR(40) DEFAULT 'qualified',
  crm_stage VARCHAR(40) DEFAULT 'qualified',
  outreach_status VARCHAR(40) DEFAULT 'not_started',
  assigned_user_id UUID REFERENCES crm_users(id) ON DELETE SET NULL,
  last_contacted_at TIMESTAMPTZ,
  next_follow_up_at TIMESTAMPTZ,
  notes TEXT DEFAULT '',
  tags JSONB DEFAULT '[]'::jsonb,
  social_links JSONB DEFAULT '{}'::jsonb,
  social_status VARCHAR(40) DEFAULT 'missing',
  screenshot_url VARCHAR(800) DEFAULT '',
  source VARCHAR(80) DEFAULT 'apify_google_maps',
  raw JSONB DEFAULT '{}'::jsonb,
  created_at TIMESTAMPTZ DEFAULT now(),
  updated_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS outreach (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  lead_id UUID NOT NULL REFERENCES leads(id) ON DELETE CASCADE,
  campaign_id UUID REFERENCES campaigns(id) ON DELETE SET NULL,
  subject_line VARCHAR(220) DEFAULT '',
  personalized_first_line TEXT DEFAULT '',
  cold_email TEXT DEFAULT '',
  follow_up_1 TEXT DEFAULT '',
  follow_up_2 TEXT DEFAULT '',
  selected_version VARCHAR(40) DEFAULT 'cold_email',
  status VARCHAR(40) DEFAULT 'draft',
  gmail_message_id VARCHAR(255) DEFAULT '',
  gmail_thread_id VARCHAR(255) DEFAULT '',
  tracking_id VARCHAR(64) DEFAULT '',
  sent_at TIMESTAMPTZ,
  opened_at TIMESTAMPTZ,
  replied_at TIMESTAMPTZ,
  bounced_at TIMESTAMPTZ,
  failed_reason TEXT DEFAULT '',
  created_at TIMESTAMPTZ DEFAULT now(),
  updated_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS crm_tags (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  name VARCHAR(80) NOT NULL UNIQUE,
  color VARCHAR(40) NOT NULL DEFAULT '',
  created_at TIMESTAMPTZ DEFAULT now(),
  updated_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS lead_tags (
  lead_id UUID NOT NULL REFERENCES leads(id) ON DELETE CASCADE,
  tag_id UUID NOT NULL REFERENCES crm_tags(id) ON DELETE CASCADE,
  created_at TIMESTAMPTZ DEFAULT now(),
  PRIMARY KEY (lead_id, tag_id)
);

CREATE TABLE IF NOT EXISTS lead_notes (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  lead_id UUID NOT NULL REFERENCES leads(id) ON DELETE CASCADE,
  body TEXT NOT NULL,
  created_by VARCHAR(160) NOT NULL DEFAULT 'LeadForge user',
  created_at TIMESTAMPTZ DEFAULT now(),
  updated_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS lead_activities (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  lead_id UUID NOT NULL REFERENCES leads(id) ON DELETE CASCADE,
  event_type VARCHAR(80) NOT NULL,
  title VARCHAR(180) NOT NULL,
  description TEXT NOT NULL DEFAULT '',
  actor VARCHAR(160) NOT NULL DEFAULT 'LeadForge AI',
  metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
  created_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS email_messages (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  lead_id UUID NOT NULL REFERENCES leads(id) ON DELETE CASCADE,
  outreach_id UUID REFERENCES outreach(id) ON DELETE SET NULL,
  gmail_message_id VARCHAR(255) NOT NULL UNIQUE,
  gmail_thread_id VARCHAR(255) NOT NULL DEFAULT '',
  message_id_header VARCHAR(500) NOT NULL DEFAULT '',
  direction VARCHAR(20) NOT NULL,
  from_email VARCHAR(320) NOT NULL DEFAULT '',
  to_email VARCHAR(320) NOT NULL DEFAULT '',
  subject VARCHAR(500) NOT NULL DEFAULT '',
  body_text TEXT NOT NULL DEFAULT '',
  body_html TEXT NOT NULL DEFAULT '',
  snippet TEXT NOT NULL DEFAULT '',
  message_at TIMESTAMPTZ NOT NULL,
  created_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS analytics (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  event_type VARCHAR(80) NOT NULL,
  lead_id UUID REFERENCES leads(id) ON DELETE SET NULL,
  campaign_id UUID REFERENCES campaigns(id) ON DELETE SET NULL,
  metadata JSONB DEFAULT '{}'::jsonb,
  created_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS settings (
  key VARCHAR(120) PRIMARY KEY,
  value JSONB DEFAULT '{}'::jsonb,
  is_secret BOOLEAN DEFAULT false,
  updated_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS lead_generation_jobs (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  campaign_id UUID REFERENCES campaigns(id) ON DELETE SET NULL,
  status VARCHAR(40) DEFAULT 'queued',
  city VARCHAR(120) DEFAULT '',
  state VARCHAR(120) DEFAULT '',
  country VARCHAR(120) DEFAULT '',
  business_type VARCHAR(160) DEFAULT '',
  website_mode VARCHAR(40) DEFAULT 'withWebsite',
  max_leads INTEGER DEFAULT 50,
  progress INTEGER DEFAULT 0,
  lead_counter INTEGER DEFAULT 0,
  success_counter INTEGER DEFAULT 0,
  failure_counter INTEGER DEFAULT 0,
  error TEXT DEFAULT '',
  created_at TIMESTAMPTZ DEFAULT now(),
  finished_at TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_leads_campaign_id ON leads(campaign_id);
CREATE INDEX IF NOT EXISTS idx_leads_status ON leads(lead_status);
CREATE INDEX IF NOT EXISTS idx_leads_crm_stage ON leads(crm_stage);
CREATE INDEX IF NOT EXISTS idx_leads_assigned_user_id ON leads(assigned_user_id);
CREATE INDEX IF NOT EXISTS idx_leads_last_contacted_at ON leads(last_contacted_at);
CREATE INDEX IF NOT EXISTS idx_leads_next_follow_up_at ON leads(next_follow_up_at);
CREATE INDEX IF NOT EXISTS idx_leads_outreach_status ON leads(outreach_status);
CREATE INDEX IF NOT EXISTS idx_leads_social_status ON leads(social_status);
CREATE INDEX IF NOT EXISTS idx_leads_business_type ON leads(business_type);
CREATE INDEX IF NOT EXISTS idx_outreach_lead_id ON outreach(lead_id);
CREATE INDEX IF NOT EXISTS idx_outreach_status ON outreach(status);
CREATE INDEX IF NOT EXISTS idx_analytics_created_at ON analytics(created_at);
CREATE INDEX IF NOT EXISTS idx_lead_tags_tag_id ON lead_tags(tag_id);
CREATE INDEX IF NOT EXISTS idx_lead_notes_lead_id ON lead_notes(lead_id);
CREATE INDEX IF NOT EXISTS idx_lead_activities_lead_id_created_at ON lead_activities(lead_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_email_messages_lead_id_message_at ON email_messages(lead_id, message_at);
CREATE INDEX IF NOT EXISTS idx_email_messages_thread_id ON email_messages(gmail_thread_id);
