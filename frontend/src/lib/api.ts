/**
 * Shared frontend API client for the LeadForge platform.
 *
 * Feature pages use these functions to call FastAPI routes for dashboard,
 * lead generation, CRM, outreach, analytics, settings, and integrations.
 */

import type {
  Analytics,
  BillingHistory,
  BillingOverview,
  BillingPlansResponse,
  Campaign,
  CrmLeadDetail,
  CrmLeadList,
  CrmUser,
  GenerationJob,
  GmailConnectionStatus,
  GoogleSheetsHealth,
  Lead,
  Outreach,
  TwilioConnectionStatus,
  VoiceSettingsStatus,
  VoiceSpeed,
} from "@/lib/types";
import { apiFetch, API_URL } from "@/lib/http";
import { trackAppError } from "@/lib/analytics";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await apiFetch(path, init);
  if (!response.ok) {
    const text = await response.text();
    let detail = "";
    try {
      const payload = JSON.parse(text) as { detail?: string };
      detail = payload.detail ?? "";
    } catch {}
    const message = detail || text || `Request failed: ${response.status}`;
    trackAppError(message, false);
    throw new Error(message);
  }
  return response.json() as Promise<T>;
}

export function getAnalytics() {
  return request<Analytics>("/get-analytics");
}

export function getLeads(params?: Record<string, string>) {
  const search = new URLSearchParams(params).toString();
  return request<Lead[]>(`/get-leads${search ? `?${search}` : ""}`);
}

export function updateLead(id: string, payload: Partial<Lead>) {
  return request<Lead>(`/get-leads/${id}`, {
    method: "PATCH",
    body: JSON.stringify(payload),
  });
}

export function getCampaigns() {
  return request<Campaign[]>("/get-campaigns");
}

export function createCampaign(payload: Partial<Campaign>) {
  return request<Campaign>("/get-campaigns", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function getOutreach(params?: Record<string, string>) {
  const search = new URLSearchParams(params).toString();
  return request<Outreach[]>(`/outreach${search ? `?${search}` : ""}`);
}

export function regenerateOutreach(leadId: string) {
  return request<Outreach>(`/outreach/${leadId}/regenerate`, { method: "POST" });
}

export function sendEmail(outreachId: string, version: string) {
  return request<Outreach>("/send-email", {
    method: "POST",
    body: JSON.stringify({ outreach_id: outreachId, version }),
  });
}

export function syncEmailStatuses() {
  return request<{ checked: number; replied: number; auto_replied: number; closed: number; failed: number; skipped: boolean }>(
    "/send-email/sync-statuses",
    { method: "POST" },
  );
}

export function getGmailConnection() {
  return request<GmailConnectionStatus>("/gmail/status");
}

export function checkGmailConnection() {
  return request<GmailConnectionStatus>("/gmail/check", { method: "POST" });
}

export function disconnectGmail() {
  return request<GmailConnectionStatus>("/gmail/disconnect", { method: "DELETE" });
}

export function gmailConnectUrl() {
  return `${API_URL}/gmail/connect`;
}

export function getTwilioConnection() {
  return request<TwilioConnectionStatus>("/twilio/status");
}

export function connectTwilio(payload: {
  account_sid: string;
  auth_token: string;
  phone_sid?: string;
  phone_number?: string;
}) {
  return request<TwilioConnectionStatus>("/twilio/connect", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function checkTwilioConnection() {
  return request<TwilioConnectionStatus>("/twilio/check", { method: "POST" });
}

export function disconnectTwilio() {
  return request<TwilioConnectionStatus>("/twilio/disconnect", { method: "DELETE" });
}

export function getVoiceSettings() {
  return request<VoiceSettingsStatus>("/twilio/voice-settings");
}

export function saveVoiceSettings(payload: {
  voice_provider: "cartesia";
  voice_id: string;
  voice_name: string;
  speaking_speed: VoiceSpeed;
  language: string;
  ai_greeting: string;
  business_name: string;
  assistant_name: string;
  cartesia_api_key?: string;
}) {
  return request<VoiceSettingsStatus>("/twilio/voice-settings", {
    method: "PUT",
    body: JSON.stringify(payload),
  });
}

export function startGeneration(payload: {
  continent: string;
  country: string;
  city: string;
  business_type: string;
  website_mode: string;
  max_leads: number;
}) {
  return request<{ job_id: string; status: string; events_url: string }>("/generate-leads", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function generationEventsUrl(jobId: string) {
  return `${API_URL}/generate-leads/${jobId}/events`;
}

export function getGenerationJob(jobId: string) {
  return request<GenerationJob>(`/generate-leads/${jobId}`);
}

export function getLatestGenerationJob() {
  return request<GenerationJob | null>("/generate-leads/latest");
}

export function getSettings() {
  return request<Record<string, unknown>>("/settings");
}

export function getGoogleSheetsHealth() {
  return request<GoogleSheetsHealth>("/health/google");
}

export function getBillingPlans() {
  return request<BillingPlansResponse>("/billing/plans");
}

export function getBillingOverview() {
  return request<BillingOverview>("/billing/me");
}

export function getBillingHistory() {
  return request<BillingHistory>("/billing/history");
}

export function createBillingPortalSession() {
  return request<{ url: string; urls: Record<string, unknown> }>("/billing/portal-session", {
    method: "POST",
  });
}

export function changeSubscriptionPlan(
  subscriptionId: string,
  payload: { price_id: string; proration_billing_mode?: string },
) {
  return request<BillingOverview["subscription"]>(`/billing/subscriptions/${subscriptionId}/change-plan`, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function cancelSubscription(
  subscriptionId: string,
  payload: { effective_from: "next_billing_period" | "immediately" },
) {
  return request<BillingOverview["subscription"]>(`/billing/subscriptions/${subscriptionId}/cancel`, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function saveSettings(payload: Record<string, unknown>) {
  return request<{ status: string }>("/settings", {
    method: "PUT",
    body: JSON.stringify(payload),
  });
}

export function csvExportUrl({
  scope = "latest",
  campaignId = "",
}: {
  scope?: string;
  campaignId?: string;
} = {}) {
  const params = new URLSearchParams({ scope });
  if (campaignId) params.set("campaign_id", campaignId);
  return `${API_URL}/get-leads/export.csv?${params.toString()}`;
}

export function getCrmLeads(params?: Record<string, string>) {
  const search = new URLSearchParams(params).toString();
  return request<CrmLeadList>(`/crm/leads${search ? `?${search}` : ""}`);
}

export function getCrmLead(id: string) {
  return request<CrmLeadDetail>(`/crm/leads/${id}`);
}

export function updateCrmLead(id: string, payload: Record<string, unknown>) {
  return request<CrmLeadDetail>(`/crm/leads/${id}`, {
    method: "PATCH",
    body: JSON.stringify(payload),
  });
}

export function addCrmNote(id: string, body: string) {
  return request<CrmLeadDetail>(`/crm/leads/${id}/notes`, {
    method: "POST",
    body: JSON.stringify({ body }),
  });
}

export function updateCrmTags(id: string, tags: string[]) {
  return request<CrmLeadDetail>(`/crm/leads/${id}/tags`, {
    method: "PUT",
    body: JSON.stringify({ tags }),
  });
}

export function getCrmUsers() {
  return request<CrmUser[]>("/crm/users");
}

export function syncCrmGmail(id: string) {
  return request<CrmLeadDetail>(`/crm/leads/${id}/sync-gmail`, {
    method: "POST",
  });
}

export function startManualSdrBridgeCall(payload: {
  contact_id?: string;
  to_phone?: string;
  business_name?: string;
  owner_phone?: string;
}) {
  return request<{
    id: string;
    status: string;
    provider_call_id: string;
    business_name: string;
    target_number: string;
  }>("/ai-sdr/calls/manual-bridge", {
    method: "POST",
    body: JSON.stringify({ ...payload, actor: "LeadForge user" }),
  });
}

export type { GenerationJob };
