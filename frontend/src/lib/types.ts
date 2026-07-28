/**
 * Shared TypeScript contracts for LeadForge platform APIs.
 *
 * These interfaces intentionally represent stable frontend-facing API shapes
 * rather than backend ORM implementation details.
 */

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

export type GmailConnectionStatus = {
  is_connected: boolean;
  gmail_email: string;
  connected_at: string | null;
  disconnected_at: string | null;
  scopes: string;
  health: "connected" | "disconnected" | "ok" | "error" | string;
  last_health_check_at: string | null;
  last_error: string;
};

export const crmStages = [
  "new",
  "qualified",
  "email_generated",
  "email_sent",
  "opened",
  "replied",
  "interested",
  "meeting_scheduled",
  "won",
  "lost",
  "archived",
] as const;

export type CrmStage = (typeof crmStages)[number];

export const crmStageLabels: Record<CrmStage, string> = {
  new: "New",
  qualified: "Qualified",
  email_generated: "Email Generated",
  email_sent: "Email Sent",
  opened: "Opened",
  replied: "Replied",
  interested: "Interested",
  meeting_scheduled: "Meeting Scheduled",
  won: "Won",
  lost: "Lost",
  archived: "Archived",
};

export type CrmUser = {
  id: string;
  name: string;
  email: string;
  initials: string;
  is_active: boolean;
};

export type CrmTag = {
  id: string;
  name: string;
  color: string;
};

export type CrmLead = {
  id: string;
  campaign_id: string | null;
  business_name: string;
  contact_name: string;
  email: string;
  phone: string;
  website: string;
  address: string;
  city: string;
  state: string;
  country: string;
  industry: string;
  notes: string;
  crm_stage: CrmStage;
  last_contacted_at: string | null;
  next_follow_up_at: string | null;
  assigned_user: CrmUser | null;
  tags: CrmTag[];
  created_at: string;
  updated_at: string;
};

export type CrmNote = {
  id: string;
  body: string;
  created_by: string;
  created_at: string;
  updated_at: string;
};

export type CrmActivity = {
  id: string;
  event_type: string;
  title: string;
  description: string;
  actor: string;
  metadata: Record<string, unknown>;
  created_at: string;
};

export type CrmEmailMessage = {
  id: string;
  outreach_id: string | null;
  gmail_message_id: string;
  gmail_thread_id: string;
  direction: "sent" | "received";
  from_email: string;
  to_email: string;
  subject: string;
  body_text: string;
  body_html: string;
  snippet: string;
  message_at: string;
};

export type CrmLeadDetail = CrmLead & {
  outreach_history: Outreach[];
  email_messages: CrmEmailMessage[];
  note_history: CrmNote[];
  activity: CrmActivity[];
};

export type CrmLeadList = {
  items: CrmLead[];
  total: number;
  stage_counts: Record<CrmStage, number>;
};
