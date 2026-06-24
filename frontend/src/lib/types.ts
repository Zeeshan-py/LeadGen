export type Lead = {
  id: string;
  campaign_id: string | null;
  business_name: string;
  website: string;
  google_maps_url: string;
  email: string;
  phone: string;
  location: string;
  city: string;
  state: string;
  country: string;
  business_type: string;
  website_score: number;
  opportunity_score: number;
  website_problems: string[];
  website_summary: string;
  improvement_suggestions: string[];
  lead_status: string;
  outreach_status: string;
  notes: string;
  tags: string[];
  social_links: Record<string, string>;
  social_status: string;
  screenshot_url: string;
  created_at: string;
  updated_at: string;
};

export type Campaign = {
  id: string;
  name: string;
  city: string;
  state: string;
  country: string;
  business_type: string;
  status: string;
  max_leads: number;
  leads_generated: number;
  emails_sent: number;
  replies: number;
  created_at: string;
  updated_at: string;
};

export type Outreach = {
  id: string;
  lead_id: string;
  campaign_id: string | null;
  subject_line: string;
  personalized_first_line: string;
  cold_email: string;
  follow_up_1: string;
  follow_up_2: string;
  selected_version: string;
  status: string;
  gmail_message_id: string;
  gmail_thread_id: string;
  tracking_id: string;
  sent_at: string | null;
  opened_at: string | null;
  replied_at: string | null;
  bounced_at: string | null;
  failed_reason: string;
  created_at: string;
  updated_at: string;
};

export type Analytics = {
  leads_found: number;
  leads_saved: number;
  emails_found: number;
  social_links_found: number;
  failed_leads: number;
  total_leads_generated: number;
  emails_sent: number;
  replies_received: number;
  open_rate: number;
  website_opportunities_found: number;
  conversion_rate: number;
  lead_generation_per_day: Array<{ date: string; leads: number }>;
  emails_per_day: Array<{ date: string; emails: number }>;
  top_cities: Array<{ city: string; count: number }>;
  top_niches: Array<{ niche: string; count: number }>;
  recent_activity: Array<{
    id: string;
    type: string;
    metadata: Record<string, unknown>;
    created_at: string;
  }>;
};

export type GenerationJob = {
  job_id: string;
  status: string;
  stage: string;
  progress: number;
  lead_counter: number;
  success_counter: number;
  failure_counter: number;
  campaign_id: string | null;
  error: string;
  pipeline: string[];
  timestamp: string;
};

export type GoogleSheetsHealth = {
  status: "ok" | "error";
  google_sheets: boolean;
  spreadsheet_access: boolean;
  code: string;
  message: string;
  credentials_source: string;
  spreadsheet_id_configured: boolean;
  service_account_email: string;
};
