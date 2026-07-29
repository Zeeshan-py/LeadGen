"use client";

type AnalyticsValue = string | number | boolean | null | undefined;
type AnalyticsParams = Record<string, AnalyticsValue>;

declare global {
  interface Window {
    dataLayer?: unknown[];
    gtag?: (...args: unknown[]) => void;
  }
}

export const GA_MEASUREMENT_ID = process.env.NEXT_PUBLIC_GA_MEASUREMENT_ID?.trim() || "";
export const GTM_ID = process.env.NEXT_PUBLIC_GTM_ID?.trim() || "";

export function analyticsEnabled() {
  return Boolean(GA_MEASUREMENT_ID || GTM_ID);
}

export function pushDataLayer(event: string, params: AnalyticsParams = {}) {
  if (typeof window === "undefined") return;
  window.dataLayer = window.dataLayer || [];
  window.dataLayer.push({ event, ...cleanParams(params) });
}

export function trackEvent(eventName: string, params: AnalyticsParams = {}) {
  const payload = cleanParams(params);
  pushDataLayer(eventName, payload);
  if (typeof window !== "undefined" && typeof window.gtag === "function" && GA_MEASUREMENT_ID) {
    window.gtag("event", eventName, payload);
  }
}

export function trackPageView(url: string, title: string) {
  pushDataLayer("page_view", {
    page_location: url,
    page_title: title,
  });
  if (typeof window !== "undefined" && typeof window.gtag === "function" && GA_MEASUREMENT_ID) {
    window.gtag("config", GA_MEASUREMENT_ID, {
      page_location: url,
      page_path: window.location.pathname,
      page_title: title,
      send_page_view: false,
    });
  }
}

export function trackLogin(method: string) {
  trackEvent("login", { method });
}

export function trackSignUp(method: string) {
  trackEvent("sign_up", { method });
}

export function trackWorkspaceCreation(source: string) {
  trackEvent("workspace_creation", { source });
}

export function trackLeadGeneration(params: AnalyticsParams) {
  trackEvent("generate_lead", params);
}

export function trackCrmUsage(action: string, params: AnalyticsParams = {}) {
  trackEvent("crm_usage", { action, ...params });
}

export function trackAiSdrUsage(action: string, params: AnalyticsParams = {}) {
  trackEvent("ai_sdr_usage", { action, ...params });
}

export function trackOutreachCampaign(action: string, params: AnalyticsParams = {}) {
  trackEvent("outreach_campaign", { action, ...params });
}

export function trackAppError(description: string, fatal = false) {
  trackEvent("exception", {
    description: description.slice(0, 180),
    fatal,
  });
}

export function trackPerformanceMetric(metric: {
  id: string;
  name: string;
  value: number;
  rating?: string;
}) {
  trackEvent("web_vital", {
    metric_id: metric.id,
    metric_name: metric.name,
    metric_value: Math.round(metric.value),
    metric_rating: metric.rating,
  });
}

function cleanParams(params: AnalyticsParams) {
  return Object.fromEntries(
    Object.entries(params).filter(([, value]) => value !== undefined && value !== null && value !== ""),
  );
}
