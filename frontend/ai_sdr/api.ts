/**
 * AI SDR frontend API client.
 *
 * Keeps the independent SDR module off the shared lead-generation API client
 * and targets only `/ai-sdr/*` backend routes.
 */

import type {
  AISDRBatch,
  AISDRBulkActionResult,
  AISDRCallSession,
  AISDRContact,
  AISDRCustomCallResponse,
  AISDRCustomCallTarget,
  AISDRDashboard,
  AISDRDashboardParams,
  AISDRImportPayload,
  AISDRImportResponse,
  AISDRManualBridgeCallPayload,
  AISDRManualBridgeCallResponse,
  AISDRSourceDescriptor,
} from "./types";
import { apiFetch } from "@/lib/http";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await apiFetch(path, init);
  if (!response.ok) {
    const text = await response.text();
    let detail = "";
    try {
      detail = (JSON.parse(text) as { detail?: string }).detail ?? "";
    } catch {}
    throw new Error(detail || text || `Request failed: ${response.status}`);
  }
  return response.json() as Promise<T>;
}

export function getAISDRSources() {
  return request<AISDRSourceDescriptor[]>("/ai-sdr/sources");
}

export function getAISDRImports() {
  return request<AISDRBatch[]>("/ai-sdr/imports");
}

export function getAISDRDashboard(params?: AISDRDashboardParams) {
  const search = new URLSearchParams(
    Object.entries(params ?? {}).filter(([, value]) => Boolean(value)) as [string, string][],
  ).toString();
  return request<AISDRDashboard>(`/ai-sdr/dashboard${search ? `?${search}` : ""}`);
}

export function getAISDRContact(contactId: string) {
  return request<AISDRContact>(`/ai-sdr/contacts/${contactId}`);
}

export function createAISDRImport(payload: AISDRImportPayload) {
  return request<AISDRImportResponse>("/ai-sdr/imports", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function bulkDeleteAISDRContacts(contactIds: string[]) {
  return request<AISDRBulkActionResult>("/ai-sdr/contacts/bulk-delete", {
    method: "POST",
    body: JSON.stringify({ contact_ids: contactIds, actor: "LeadForge user" }),
  });
}

export function startAISDROutboundCall(contactId: string, objective?: string) {
  return request<AISDRCallSession>("/ai-sdr/calls/outbound", {
    method: "POST",
    body: JSON.stringify({
      contact_id: contactId,
      objective: objective ?? "",
      actor: "LeadForge user",
    }),
  });
}

export function startAISDRCustomTargetCall(payload: AISDRCustomCallTarget) {
  return request<AISDRCustomCallResponse>("/ai-sdr/calls/custom-target", {
    method: "POST",
    body: JSON.stringify({
      ...payload,
      actor: payload.actor ?? "LeadForge user",
    }),
  });
}

export function startAISDRManualBridgeCall(payload: AISDRManualBridgeCallPayload) {
  return request<AISDRManualBridgeCallResponse>("/ai-sdr/calls/manual-bridge", {
    method: "POST",
    body: JSON.stringify({
      ...payload,
      actor: payload.actor ?? "LeadForge user",
    }),
  });
}

export function getAISDRCall(callId: string) {
  return request<AISDRCallSession>(`/ai-sdr/calls/${callId}`);
}

export function controlAISDRCall(callId: string, action: string) {
  return request<AISDRCallSession>(`/ai-sdr/calls/${callId}/control`, {
    method: "POST",
    body: JSON.stringify({ action, actor: "LeadForge user" }),
  });
}

export async function exportAISDRContacts(contactIds: string[]) {
  const response = await apiFetch("/ai-sdr/contacts/export.csv", {
    method: "POST",
    body: JSON.stringify({ contact_ids: contactIds, actor: "LeadForge user" }),
  });
  if (!response.ok) {
    throw new Error((await response.text()) || `Request failed: ${response.status}`);
  }
  return response.blob();
}
