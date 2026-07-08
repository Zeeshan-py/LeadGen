/**
 * TypeScript contracts for the independent AI SDR frontend module.
 *
 * These types mirror backend AI SDR schemas for sources, imports, dashboard
 * rows, bulk actions, and CRM-normalized contacts.
 */

export const aiSdrSourceTypes = [
  "csv",
  "excel",
  "google_sheets",
  "manual_entry",
  "rest_api",
  "crm",
  "future_integration",
] as const;

export type AISDRSourceType = (typeof aiSdrSourceTypes)[number];

export const aiSdrSourceLabels: Record<AISDRSourceType, string> = {
  csv: "CSV",
  excel: "Excel",
  google_sheets: "Google Sheets",
  manual_entry: "Manual Entry",
  rest_api: "REST API",
  crm: "CRM",
  future_integration: "Future Integration",
};

export type AISDRSourceDescriptor = {
  type: AISDRSourceType;
  label: string;
  status: string;
  entrypoint: string;
  notes: string;
};

export type AISDRContactInput = {
  company_name?: string;
  business_name?: string;
  contact_name?: string;
  first_name?: string;
  last_name?: string;
  title?: string;
  email?: string;
  phone?: string;
  website?: string;
  linkedin_url?: string;
  address?: string;
  city?: string;
  state?: string;
  country?: string;
  industry?: string;
  notes?: string;
  tags?: string[];
  external_id?: string;
  raw?: Record<string, unknown>;
};

export type AISDRBatch = {
  id: string;
  source_type: string;
  status: string;
  total_count: number;
  normalized_count: number;
  stored_count: number;
  duplicate_count: number;
  failed_count: number;
  created_by: string;
  configuration: Record<string, unknown>;
  error: string;
  created_at: string;
  updated_at: string;
};

export type AISDRRecord = {
  id: string;
  batch_id: string;
  crm_lead_id: string | null;
  source_type: string;
  external_id: string;
  status: string;
  dedupe_key: string;
  normalized: Record<string, unknown>;
  raw: Record<string, unknown>;
  errors: string[];
  created_at: string;
  updated_at: string;
};

export type AISDRImportResponse = {
  batch: AISDRBatch;
  records: AISDRRecord[];
};

export type AISDRImportPayload = {
  source_type: AISDRSourceType;
  contacts: AISDRContactInput[];
  configuration?: Record<string, unknown>;
  created_by?: string;
};

export type AISDRContact = {
  id: string;
  company: string;
  contact: string;
  phone: string;
  email: string;
  industry: string;
  status: string;
  source: string;
  pipeline_stage: string;
  next_follow_up: string | null;
  city: string;
  state: string;
  country: string;
  website: string;
  notes: string;
  last_contacted_at: string | null;
  source_record_id: string | null;
  source_batch_id: string | null;
  created_at: string;
  updated_at: string;
};

export type AISDRDashboardStats = {
  total_contacts: number;
  ready_to_call: number;
  calls_today: number;
  interested: number;
  qualified: number;
  meetings_pending: number;
  average_call_duration_seconds: number;
  conversion_rate: number;
};

export type AISDRDashboardFilters = {
  statuses: string[];
  industries: string[];
  cities: string[];
  sources: string[];
};

export type AISDRDashboard = {
  stats: AISDRDashboardStats;
  contacts: AISDRContact[];
  filters: AISDRDashboardFilters;
  total: number;
};

export type AISDRDashboardParams = {
  status?: string;
  industry?: string;
  city?: string;
  source?: string;
  search?: string;
};

export type AISDRBulkActionResult = {
  requested: number;
  updated: number;
  skipped: number;
  contact_ids: string[];
};

export type AISDRCallTranscriptLine = {
  role: "customer" | "ai" | "system";
  text: string;
  is_final: boolean;
  confidence: number | null;
  sequence: number;
  created_at: string | null;
  raw: Record<string, unknown>;
};

export type AISDRCallOutcome = {
  conversation_summary: string;
  qualification_score: number;
  interested: boolean;
  reason: string;
  objections: string[];
  website_problems: string[];
  recommended_services: string[];
  next_follow_up: string;
  metadata: Record<string, unknown>;
};

export type AISDRCallSession = {
  id: string;
  contact_id: string;
  status: string;
  provider_call_id: string;
  stream_id: string;
  objective: string;
  telephony_provider: string;
  llm_provider: string;
  speech_provider: string;
  ai_paused: boolean;
  muted: boolean;
  transfer_requested: boolean;
  brain: Record<string, unknown>;
  outcome: AISDRCallOutcome | null;
  transcript: AISDRCallTranscriptLine[];
  duration_seconds: number;
  created_at: string;
  started_at: string | null;
  ended_at: string | null;
  updated_at: string;
};

export type AISDRCustomCallTarget = {
  business_name: string;
  owner_name?: string;
  phone: string;
  email?: string;
  website?: string;
  instagram_url?: string;
  industry?: string;
  city?: string;
  offer: string;
  instructions: string;
  notes?: string;
  actor?: string;
};

export type AISDRCustomCallResponse = {
  contact: AISDRContact;
  call: AISDRCallSession;
};
