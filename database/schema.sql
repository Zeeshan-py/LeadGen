CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

CREATE TABLE IF NOT EXISTS campaigns (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  name VARCHAR(180) NOT NULL,
  city VARCHAR(120) DEFAULT '',
  state VARCHAR(120) DEFAULT '',
  country VARCHAR(120) DEFAULT '',
  business_type VARCHAR(160) NOT NULL,
  status VARCHAR(40) DEFAULT 'draft',
  max_leads INTEGER DEFAULT 50,
  leads_generated INTEGER DEFAULT 0,
  emails_sent INTEGER DEFAULT 0,
  replies INTEGER DEFAULT 0,
  created_at TIMESTAMPTZ DEFAULT now(),
  updated_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS leads (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  campaign_id UUID REFERENCES campaigns(id) ON DELETE SET NULL,
  dedupe_key VARCHAR(255) NOT NULL UNIQUE,
  business_name VARCHAR(240) NOT NULL,
  website VARCHAR(500) DEFAULT '',
  google_maps_url VARCHAR(800) DEFAULT '',
  email VARCHAR(320) DEFAULT '',
  phone VARCHAR(80) DEFAULT '',
  location VARCHAR(500) DEFAULT '',
  city VARCHAR(120) DEFAULT '',
  state VARCHAR(120) DEFAULT '',
  country VARCHAR(120) DEFAULT '',
  business_type VARCHAR(160) DEFAULT '',
  website_score INTEGER DEFAULT 0,
  opportunity_score INTEGER DEFAULT 0,
  website_problems JSONB DEFAULT '[]'::jsonb,
  website_summary TEXT DEFAULT '',
  improvement_suggestions JSONB DEFAULT '[]'::jsonb,
  lead_status VARCHAR(40) DEFAULT 'qualified',
  outreach_status VARCHAR(40) DEFAULT 'not_started',
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
CREATE INDEX IF NOT EXISTS idx_leads_outreach_status ON leads(outreach_status);
CREATE INDEX IF NOT EXISTS idx_leads_social_status ON leads(social_status);
CREATE INDEX IF NOT EXISTS idx_leads_business_type ON leads(business_type);
CREATE INDEX IF NOT EXISTS idx_outreach_lead_id ON outreach(lead_id);
CREATE INDEX IF NOT EXISTS idx_outreach_status ON outreach(status);
CREATE INDEX IF NOT EXISTS idx_analytics_created_at ON analytics(created_at);
