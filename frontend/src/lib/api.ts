import type { Analytics, Campaign, GenerationJob, GoogleSheetsHealth, Lead, Outreach } from "@/lib/types";

export const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_URL}${path}`, {
    cache: "no-store",
    headers: {
      "Content-Type": "application/json",
      ...init?.headers,
    },
    ...init,
  });
  if (!response.ok) {
    const text = await response.text();
    let detail = "";
    try {
      const payload = JSON.parse(text) as { detail?: string };
      detail = payload.detail ?? "";
    } catch {}
    throw new Error(detail || text || `Request failed: ${response.status}`);
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

export function startGeneration(payload: {
  continent: string;
  country: string;
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

export function saveSettings(payload: Record<string, unknown>) {
  return request<{ status: string }>("/settings", {
    method: "PUT",
    body: JSON.stringify(payload),
  });
}

export function csvExportUrl(scope = "latest") {
  return `${API_URL}/get-leads/export.csv?scope=${encodeURIComponent(scope)}`;
}

export type { GenerationJob };
