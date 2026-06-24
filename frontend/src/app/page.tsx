"use client";

import { useEffect, useMemo, useState } from "react";
import { Activity, AlertTriangle, AtSign, Link2, Save, Search } from "lucide-react";

import { AreaPanel, BarPanel } from "@/components/chart-panel";
import { MetricCard } from "@/components/metric-card";
import { StatusBadge } from "@/components/status-badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { getAnalytics } from "@/lib/api";
import { compactNumber, dateLabel, statusLabel } from "@/lib/format";
import type { Analytics } from "@/lib/types";

export default function DashboardHome() {
  const [analytics, setAnalytics] = useState<Analytics | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    getAnalytics().then(setAnalytics).catch((err) => setError(err.message));
  }, []);

  const leadData = useMemo(
    () =>
      analytics?.lead_generation_per_day.map((item) => ({
        ...item,
        date: dateLabel(item.date),
      })) ?? [],
    [analytics],
  );
  const emailData = useMemo(
    () =>
      analytics?.emails_per_day.map((item) => ({
        ...item,
        date: dateLabel(item.date),
      })) ?? [],
    [analytics],
  );

  if (!analytics && !error) {
    return <DashboardSkeleton />;
  }

  return (
    <div className="flex flex-col gap-6">
      <section className="grid gap-4 md:grid-cols-2 xl:grid-cols-5">
        <MetricCard
          title="Leads Found"
          value={compactNumber(analytics?.leads_found ?? 0)}
          detail="Discovered in the latest country search"
          icon={Search}
        />
        <MetricCard
          title="Leads Saved"
          value={compactNumber(analytics?.leads_saved ?? 0)}
          detail="Validated and stored"
          icon={Save}
        />
        <MetricCard
          title="Emails Found"
          value={compactNumber(analytics?.emails_found ?? 0)}
          detail="Valid emails in the latest run"
          icon={AtSign}
        />
        <MetricCard
          title="Social Links Found"
          value={compactNumber(analytics?.social_links_found ?? 0)}
          detail="Profiles across six networks"
          icon={Link2}
        />
        <MetricCard
          title="Failed Leads"
          value={compactNumber(analytics?.failed_leads ?? 0)}
          detail="Skipped after validation or provider errors"
          icon={AlertTriangle}
        />
      </section>

      {error ? (
        <Card className="glass-panel">
          <CardContent className="p-6 text-sm text-destructive">{error}</CardContent>
        </Card>
      ) : null}

      <section className="grid gap-4 xl:grid-cols-[1.5fr_1fr]">
        <AreaPanel title="Lead Generation Per Day" data={leadData} dataKey="leads" />
        <Card className="glass-panel">
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-base">
              <Activity className="size-4 text-primary" />
              Recent Activity
            </CardTitle>
          </CardHeader>
          <CardContent className="flex flex-col gap-3">
            {(analytics?.recent_activity ?? []).length ? (
              analytics?.recent_activity.slice(0, 8).map((item) => (
                <div key={item.id} className="flex items-center justify-between gap-3 rounded-lg border border-border/70 bg-secondary/30 p-3">
                  <div className="min-w-0">
                    <p className="truncate text-sm font-medium">{statusLabel(item.type)}</p>
                    <p className="truncate text-xs text-muted-foreground">
                      {activitySummary(item.metadata)}
                    </p>
                  </div>
                  <StatusBadge value={item.type.includes("failed") ? "failed" : "completed"} />
                </div>
              ))
            ) : (
              <p className="rounded-lg border border-border/70 bg-secondary/30 p-4 text-sm text-muted-foreground">
                No activity yet. Run a lead generation job to populate the command center.
              </p>
            )}
          </CardContent>
        </Card>
      </section>

      <section className="grid gap-4 xl:grid-cols-3">
        <AreaPanel title="Emails Sent" data={emailData} dataKey="emails" />
        <BarPanel title="Top Cities" data={analytics?.top_cities ?? []} labelKey="city" />
        <BarPanel title="Top Niches" data={analytics?.top_niches ?? []} labelKey="niche" />
      </section>
    </div>
  );
}

function activitySummary(metadata: Record<string, unknown>) {
  const business = typeof metadata.business_name === "string" ? metadata.business_name : "";
  const error = typeof metadata.error === "string" ? metadata.error : "";
  if (/429|resource_exhausted|quota/i.test(error)) {
    return `${business ? `${business}: ` : ""}AI quota unavailable; enrichment continued where possible.`;
  }
  if (error) {
    return `${business ? `${business}: ` : ""}${error.slice(0, 140)}`;
  }
  return Object.values(metadata ?? {}).join(" ") || "Automation event";
}

function DashboardSkeleton() {
  return (
    <div className="flex flex-col gap-6">
      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-5">
        {Array.from({ length: 5 }).map((_, index) => (
          <Card key={index} className="glass-panel">
            <CardContent className="p-6">
              <Skeleton className="h-4 w-28" />
              <Skeleton className="mt-5 h-9 w-20" />
              <Skeleton className="mt-3 h-4 w-36" />
            </CardContent>
          </Card>
        ))}
      </div>
      <Skeleton className="h-[320px] rounded-lg" />
    </div>
  );
}
