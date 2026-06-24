"use client";

import { useEffect, useMemo, useState } from "react";
import { BarChart3, MailCheck, MousePointer2, Reply, TrendingUp, Users } from "lucide-react";
import { toast } from "sonner";

import { AreaPanel, BarPanel } from "@/components/chart-panel";
import { MetricCard } from "@/components/metric-card";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { getAnalytics } from "@/lib/api";
import { compactNumber, dateLabel } from "@/lib/format";
import type { Analytics } from "@/lib/types";

export default function AnalyticsPage() {
  const [analytics, setAnalytics] = useState<Analytics | null>(null);

  useEffect(() => {
    getAnalytics().then(setAnalytics).catch((error) => toast.error(error.message));
  }, []);

  const leadData = useMemo(() => analytics?.lead_generation_per_day.map((item) => ({ ...item, date: dateLabel(item.date) })) ?? [], [analytics]);
  const emailData = useMemo(() => analytics?.emails_per_day.map((item) => ({ ...item, date: dateLabel(item.date) })) ?? [], [analytics]);

  return (
    <div className="flex flex-col gap-6">
      <section className="grid gap-4 md:grid-cols-2 xl:grid-cols-5">
        <MetricCard title="Leads" value={compactNumber(analytics?.total_leads_generated ?? 0)} detail="All generated records" icon={Users} />
        <MetricCard title="Emails Sent" value={compactNumber(analytics?.emails_sent ?? 0)} detail="Cold + follow-up sends" icon={MailCheck} />
        <MetricCard title="Replies" value={compactNumber(analytics?.replies_received ?? 0)} detail="Detected Gmail replies" icon={Reply} />
        <MetricCard title="Open Rate" value={`${analytics?.open_rate ?? 0}%`} detail="Open tracking pixel" icon={MousePointer2} />
        <MetricCard title="Conversion Rate" value={`${analytics?.conversion_rate ?? 0}%`} detail="Replies over sends" icon={TrendingUp} />
      </section>
      <section className="grid gap-4 xl:grid-cols-2">
        <AreaPanel title="Lead Generation Per Day" data={leadData} dataKey="leads" />
        <AreaPanel title="Emails Sent" data={emailData} dataKey="emails" />
      </section>
      <section className="grid gap-4 xl:grid-cols-2">
        <BarPanel title="Top Cities" data={analytics?.top_cities ?? []} labelKey="city" />
        <BarPanel title="Top Niches" data={analytics?.top_niches ?? []} labelKey="niche" />
      </section>
      <Card className="glass-panel">
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <BarChart3 className="size-5 text-primary" />
            Website Opportunity Signal
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="grid gap-4 md:grid-cols-3">
            <div className="rounded-lg border border-border/70 bg-secondary/30 p-4">
              <p className="text-sm text-muted-foreground">High Opportunity Leads</p>
              <p className="mt-2 text-3xl font-semibold">{analytics?.website_opportunities_found ?? 0}</p>
            </div>
            <div className="rounded-lg border border-border/70 bg-secondary/30 p-4">
              <p className="text-sm text-muted-foreground">Open Rate</p>
              <p className="mt-2 text-3xl font-semibold">{analytics?.open_rate ?? 0}%</p>
            </div>
            <div className="rounded-lg border border-border/70 bg-secondary/30 p-4">
              <p className="text-sm text-muted-foreground">Reply Conversion</p>
              <p className="mt-2 text-3xl font-semibold">{analytics?.conversion_rate ?? 0}%</p>
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
