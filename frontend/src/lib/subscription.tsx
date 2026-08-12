"use client";

import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";

import { getSubscriptionAccess } from "@/lib/api";
import type { FeatureKey, PlanKey, SubscriptionAccess } from "@/lib/types";

export type UpgradePrompt = {
  feature: FeatureKey;
  title: string;
  requiredPlan: PlanKey;
  benefits: string[];
};

type SubscriptionContextValue = {
  access: SubscriptionAccess | null;
  loading: boolean;
  refreshAccess: () => Promise<SubscriptionAccess | null>;
  hasFeature: (feature: FeatureKey) => boolean;
  requiredPlanFor: (feature: FeatureKey) => PlanKey;
  featureLabel: (feature: FeatureKey) => string;
  prompt: UpgradePrompt | null;
  openUpgrade: (feature: FeatureKey, benefits?: string[]) => void;
  closeUpgrade: () => void;
};

const planOrder: Record<PlanKey, number> = {
  none: 0,
  basic: 1,
  agent: 2,
  agency: 3,
};

const planNames: Record<PlanKey, string> = {
  none: "No active plan",
  basic: "Basic",
  agent: "Agent",
  agency: "Agency",
};

const defaultRequirements: Record<FeatureKey, PlanKey> = {
  lead_generation: "basic",
  standard_filters: "basic",
  advanced_filters: "agent",
  crm: "basic",
  analytics: "basic",
  csv_export: "basic",
  outreach: "basic",
  campaigns: "agent",
  campaign_automation: "agency",
  ai_sdr: "agency",
  twilio: "agency",
  reply_sync: "agency",
  premium_enrichment: "agency",
  unlimited_outreach: "agency",
};

const defaultLabels: Record<FeatureKey, string> = {
  lead_generation: "Lead Generation",
  standard_filters: "Standard Filters",
  advanced_filters: "Advanced Filters",
  crm: "CRM",
  analytics: "Analytics",
  csv_export: "CSV Export",
  outreach: "Outreach",
  campaigns: "Campaigns",
  campaign_automation: "Campaign Automation",
  ai_sdr: "AI SDR",
  twilio: "Automated Calling",
  reply_sync: "Reply Sync",
  premium_enrichment: "Premium Enrichment",
  unlimited_outreach: "Unlimited Outreach",
};

const defaultBenefits: Record<FeatureKey, string[]> = {
  lead_generation: ["Monthly lead quota", "Basic lead generation"],
  standard_filters: ["Standard filters", "Gmail outreach readiness"],
  advanced_filters: ["Advanced filters", "Campaign targeting", "Social/contact filters"],
  crm: ["CRM pipeline", "Lead notes and stages", "Follow-up tracking"],
  analytics: ["Analytics dashboard", "Performance charts", "Conversion reporting"],
  csv_export: ["CSV export", "Campaign exports", "Lead data download"],
  outreach: ["Gmail outreach", "AI email drafts", "Daily sending quota"],
  campaigns: ["Campaign management", "Campaign history", "Campaign exports"],
  campaign_automation: ["Campaign automation", "Automated workflows", "Agency operations"],
  ai_sdr: ["AI SDR", "Automated Calling", "Campaign Automation"],
  twilio: ["Twilio calling connection", "Voice settings", "AI SDR calls"],
  reply_sync: ["Reply Sync", "Inbox tracking", "CRM reply updates"],
  premium_enrichment: ["Premium enrichment", "Deeper lead context", "Advanced scoring"],
  unlimited_outreach: ["Unlimited Outreach", "Higher sending volume", "Agency campaigns"],
};

const SubscriptionContext = createContext<SubscriptionContextValue | null>(null);

export function SubscriptionProvider({ children }: { children: React.ReactNode }) {
  const [access, setAccess] = useState<SubscriptionAccess | null>(null);
  const [loading, setLoading] = useState(true);
  const [prompt, setPrompt] = useState<UpgradePrompt | null>(null);

  const refreshAccess = useCallback(async () => {
    setLoading(true);
    try {
      const nextAccess = await getSubscriptionAccess();
      setAccess(nextAccess);
      return nextAccess;
    } catch {
      setAccess(null);
      return null;
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void refreshAccess();
  }, [refreshAccess]);

  const requiredPlanFor = useCallback(
    (feature: FeatureKey) => access?.requirements?.[feature] ?? defaultRequirements[feature],
    [access],
  );

  const featureLabel = useCallback(
    (feature: FeatureKey) => access?.feature_labels?.[feature] ?? defaultLabels[feature],
    [access],
  );

  const hasFeature = useCallback(
    (feature: FeatureKey) => {
      if (access?.features?.[feature] !== undefined) {
        return access.features[feature];
      }
      const plan = access?.plan_key ?? "none";
      return planOrder[plan] >= planOrder[requiredPlanFor(feature)];
    },
    [access, requiredPlanFor],
  );

  const openUpgrade = useCallback(
    (feature: FeatureKey, benefits?: string[]) => {
      const requiredPlan = requiredPlanFor(feature);
      setPrompt({
        feature,
        title: featureLabel(feature),
        requiredPlan,
        benefits: benefits?.length ? benefits : defaultBenefits[feature],
      });
    },
    [featureLabel, requiredPlanFor],
  );

  const value = useMemo<SubscriptionContextValue>(
    () => ({
      access,
      loading,
      refreshAccess,
      hasFeature,
      requiredPlanFor,
      featureLabel,
      prompt,
      openUpgrade,
      closeUpgrade: () => setPrompt(null),
    }),
    [access, featureLabel, hasFeature, loading, openUpgrade, prompt, refreshAccess, requiredPlanFor],
  );

  return <SubscriptionContext.Provider value={value}>{children}</SubscriptionContext.Provider>;
}

export function useSubscription() {
  const value = useContext(SubscriptionContext);
  if (!value) {
    throw new Error("useSubscription must be used inside SubscriptionProvider");
  }
  return value;
}

export function planName(plan: PlanKey) {
  return planNames[plan];
}
