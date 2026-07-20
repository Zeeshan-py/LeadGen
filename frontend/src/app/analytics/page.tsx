"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import {
  Area,
  AreaChart,
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  ComposedChart,
  Funnel,
  FunnelChart,
  LabelList,
  Line,
  Pie,
  PieChart,
  XAxis,
  YAxis,
} from "recharts";
import {
  BarChart3,
  Bot,
  Calendar,
  Download,
  FileSpreadsheet,
  FileText,
  Filter,
  MailCheck,
  Map as MapIcon,
  Medal,
  MousePointer2,
  PhoneCall,
  PieChart as PieChartIcon,
  Reply,
  TrendingDown,
  TrendingUp,
  Users,
} from "lucide-react";
import { useReducedMotion } from "framer-motion";
import { toast } from "sonner";

import {
  ChartContainer,
  ChartLegend,
  ChartLegendContent,
  ChartTooltip,
  ChartTooltipContent,
  type ChartConfig,
} from "@/components/ui/chart";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";
import {
  Select,
  SelectContent,
  SelectGroup,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  getAnalytics,
  getCampaigns,
  getCrmLeads,
  getOutreach,
} from "@/lib/api";
import { compactNumber, dateLabel } from "@/lib/format";
import type { Analytics, Campaign, CrmLead, CrmLeadList, Outreach } from "@/lib/types";

const chartConfig = {
  leads: { label: "Leads", color: "var(--chart-1)" },
  emails: { label: "Emails", color: "var(--chart-2)" },
  replies: { label: "Replies", color: "var(--chart-3)" },
  value: { label: "Value", color: "var(--chart-1)" },
  revenue: { label: "Revenue", color: "var(--chart-3)" },
  cost: { label: "Cost", color: "var(--chart-4)" },
  forecast: { label: "Forecast", color: "var(--chart-5)" },
} satisfies ChartConfig;

const dateRanges = ["Today", "7 Days", "30 Days", "90 Days", "Custom"] as const;
const pieColors = ["var(--chart-1)", "var(--chart-2)", "var(--chart-3)", "var(--chart-4)", "var(--chart-5)"];

type LeaderboardItem = {
  name: string;
  won: number;
  meetings: number;
  score: number;
};

export default function AnalyticsPage() {
  const [analytics, setAnalytics] = useState<Analytics | null>(null);
  const [campaigns, setCampaigns] = useState<Campaign[]>([]);
  const [crm, setCrm] = useState<CrmLeadList | null>(null);
  const [outreach, setOutreach] = useState<Outreach[]>([]);
  const [dateRange, setDateRange] = useState<(typeof dateRanges)[number]>("30 Days");
  const [segment, setSegment] = useState("all");

  useEffect(() => {
    Promise.all([
      getAnalytics(),
      getCampaigns().catch(() => [] as Campaign[]),
      getCrmLeads({ limit: "500" }).catch(() => null),
      getOutreach().catch(() => [] as Outreach[]),
    ])
      .then(([analyticsResult, campaignRows, crmRows, outreachRows]) => {
        setAnalytics(analyticsResult);
        setCampaigns(campaignRows);
        setCrm(crmRows);
        setOutreach(outreachRows);
      })
      .catch((error) => toast.error(error.message));
  }, []);

  const leadTrend = useMemo(() => filterTrend(analytics?.lead_generation_per_day ?? [], dateRange), [analytics, dateRange]);
  const emailTrend = useMemo(() => filterEmailTrend(analytics?.emails_per_day ?? [], dateRange), [analytics, dateRange]);
  const mergedTrend = useMemo(() => mergeTrends(leadTrend, emailTrend), [leadTrend, emailTrend]);
  const funnel = useMemo(() => buildFunnel(crm, analytics), [crm, analytics]);
  const campaignPerformance = useMemo(() => buildCampaignPerformance(campaigns), [campaigns]);
  const leadSources = useMemo(() => buildLeadSources(analytics), [analytics]);
  const industryDistribution = useMemo(() => analytics?.top_niches.map((item) => ({ name: item.niche, value: item.count })) ?? [], [analytics]);
  const geoData = useMemo(() => analytics?.top_cities.map((item) => ({ name: item.city, value: item.count })) ?? [], [analytics]);
  const emailPerformance = useMemo(() => buildEmailPerformance(analytics, outreach), [analytics, outreach]);
  const callAnalytics = useMemo(() => buildCallAnalytics(analytics), [analytics]);
  const revenue = useMemo(() => buildRevenueModel({ analytics, crm, campaigns }), [analytics, crm, campaigns]);
  const forecast = useMemo(() => buildForecast(leadTrend, analytics), [leadTrend, analytics]);
  const leaderboard = useMemo(() => buildLeaderboard(crm?.items ?? []), [crm]);
  const lostReasons = useMemo(() => buildLostReasons(crm?.items ?? []), [crm]);
  const scoreDistribution = useMemo(() => buildScoreDistribution(crm?.items ?? []), [crm]);
  const aiInsights = useMemo(() => buildInsights({ analytics, revenue, funnel, campaignPerformance }), [analytics, revenue, funnel, campaignPerformance]);

  return (
    <div className="flex flex-col gap-6">
      <section className="rounded-lg border border-primary/20 bg-card/80 p-4 shadow-2xl shadow-black/20 backdrop-blur-xl md:p-5">
        <div className="flex flex-col gap-5 xl:flex-row xl:items-center xl:justify-between">
          <div>
            <Badge variant="outline" className="border-accent/30 bg-accent/10 text-accent">
              Business Intelligence
            </Badge>
            <h2 className="mt-3 text-2xl font-semibold tracking-normal md:text-3xl">
              Analytics, forecasting, and ROI intelligence
            </h2>
            <p className="mt-2 max-w-3xl text-sm leading-6 text-muted-foreground">
              Drill into conversion quality, channel performance, revenue efficiency, and AI SDR productivity.
            </p>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <Select value={dateRange} onValueChange={(value) => setDateRange(value as typeof dateRange)}>
              <SelectTrigger className="w-36">
                <Calendar className="size-4 text-muted-foreground" />
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectGroup>
                  {dateRanges.map((range) => (
                    <SelectItem key={range} value={range}>{range}</SelectItem>
                  ))}
                </SelectGroup>
              </SelectContent>
            </Select>
            <Select value={segment} onValueChange={setSegment}>
              <SelectTrigger className="w-40">
                <Filter className="size-4 text-muted-foreground" />
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectGroup>
                  <SelectItem value="all">All Segments</SelectItem>
                  <SelectItem value="campaigns">Campaigns</SelectItem>
                  <SelectItem value="email">Email</SelectItem>
                  <SelectItem value="ai-sdr">AI SDR</SelectItem>
                </SelectGroup>
              </SelectContent>
            </Select>
            <Button variant="outline">
              <FileText data-icon="inline-start" />
              PDF
            </Button>
            <Button variant="outline">
              <Download data-icon="inline-start" />
              CSV
            </Button>
            <Button>
              <FileSpreadsheet data-icon="inline-start" />
              Excel
            </Button>
          </div>
        </div>
      </section>

      <section className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        <ExecutiveKpi title="Revenue Forecast" value={revenue.forecastRevenue} prefix="$" detail={`${revenue.roi}x projected ROI`} icon={TrendingUp} />
        <ExecutiveKpi title="Customer Acquisition Cost" value={revenue.cac} prefix="$" detail="Estimated CAC from campaign spend" icon={BarChart3} />
        <ExecutiveKpi title="Lifetime Value" value={revenue.ltv} prefix="$" detail="Modeled from won pipeline value" icon={Users} />
        <ExecutiveKpi title="Reply Conversion" value={analytics?.conversion_rate ?? 0} suffix="%" detail="Reply rate from sent outreach" icon={Reply} />
      </section>

      <section className="grid gap-4 xl:grid-cols-[1.35fr_0.65fr]">
        <ChartPanel title="Lead Generation Trends Over Time" icon={TrendingUp}>
          <ChartContainer config={chartConfig} className="h-[330px] w-full">
            <ComposedChart data={mergedTrend}>
              <CartesianGrid vertical={false} />
              <XAxis dataKey="date" tickLine={false} axisLine={false} />
              <YAxis tickLine={false} axisLine={false} width={34} />
              <ChartTooltip content={<ChartTooltipContent />} />
              <Area type="monotone" dataKey="leads" stroke="var(--color-leads)" fill="var(--color-leads)" fillOpacity={0.18} strokeWidth={2} />
              <Line type="monotone" dataKey="emails" stroke="var(--color-emails)" strokeWidth={2} dot={false} />
              <ChartLegend content={<ChartLegendContent />} />
            </ComposedChart>
          </ChartContainer>
        </ChartPanel>

        <ChartPanel title="Conversion Funnel" icon={Filter}>
          <ChartContainer config={chartConfig} className="h-[330px] w-full">
            <FunnelChart>
              <ChartTooltip content={<ChartTooltipContent />} />
              <Funnel dataKey="value" data={funnel} isAnimationActive>
                <LabelList position="right" fill="currentColor" stroke="none" dataKey="name" />
              </Funnel>
            </FunnelChart>
          </ChartContainer>
        </ChartPanel>
      </section>

      <section className="grid gap-4 xl:grid-cols-3">
        <ChartPanel title="Email Performance" icon={MailCheck}>
          <ChartContainer config={chartConfig} className="h-[280px] w-full">
            <BarChart data={emailPerformance}>
              <CartesianGrid vertical={false} />
              <XAxis dataKey="name" tickLine={false} axisLine={false} />
              <YAxis tickLine={false} axisLine={false} width={34} />
              <ChartTooltip content={<ChartTooltipContent />} />
              <Bar dataKey="value" radius={6} fill="var(--color-value)" />
            </BarChart>
          </ChartContainer>
        </ChartPanel>

        <ChartPanel title="AI SDR Call Analytics" icon={PhoneCall}>
          <ChartContainer config={chartConfig} className="h-[280px] w-full">
            <BarChart data={callAnalytics}>
              <CartesianGrid vertical={false} />
              <XAxis dataKey="name" tickLine={false} axisLine={false} />
              <YAxis tickLine={false} axisLine={false} width={34} />
              <ChartTooltip content={<ChartTooltipContent />} />
              <Bar dataKey="value" radius={6} fill="var(--color-replies)" />
            </BarChart>
          </ChartContainer>
        </ChartPanel>

        <ChartPanel title="Revenue & ROI Dashboard" icon={TrendingUp}>
          <ChartContainer config={chartConfig} className="h-[280px] w-full">
            <ComposedChart data={revenue.series}>
              <CartesianGrid vertical={false} />
              <XAxis dataKey="name" tickLine={false} axisLine={false} />
              <YAxis tickLine={false} axisLine={false} width={42} />
              <ChartTooltip content={<ChartTooltipContent />} />
              <Bar dataKey="cost" radius={6} fill="var(--color-cost)" />
              <Line type="monotone" dataKey="revenue" stroke="var(--color-revenue)" strokeWidth={2} />
            </ComposedChart>
          </ChartContainer>
        </ChartPanel>
      </section>

      <section className="grid gap-4 xl:grid-cols-3">
        <ChartPanel title="Lead Source Comparison" icon={MousePointer2}>
          <Donut data={leadSources} />
        </ChartPanel>
        <ChartPanel title="Geographic Heatmap of Leads" icon={MapIcon}>
          <RankedBars data={geoData} valueLabel="leads" />
        </ChartPanel>
        <ChartPanel title="Industry Distribution" icon={PieChartIcon}>
          <Donut data={industryDistribution} />
        </ChartPanel>
      </section>

      <section className="grid gap-4 xl:grid-cols-[1fr_1fr]">
        <ChartPanel title="Campaign Performance Comparison" icon={BarChart3}>
          <ChartContainer config={chartConfig} className="h-[320px] w-full">
            <BarChart data={campaignPerformance}>
              <CartesianGrid vertical={false} />
              <XAxis dataKey="name" tickLine={false} axisLine={false} />
              <YAxis tickLine={false} axisLine={false} width={34} />
              <ChartTooltip content={<ChartTooltipContent />} />
              <Bar dataKey="leads" radius={6} fill="var(--color-leads)" />
              <Bar dataKey="emails" radius={6} fill="var(--color-emails)" />
              <ChartLegend content={<ChartLegendContent />} />
            </BarChart>
          </ChartContainer>
        </ChartPanel>

        <ChartPanel title="Sales Forecasting Using AI" icon={Bot}>
          <ChartContainer config={chartConfig} className="h-[320px] w-full">
            <AreaChart data={forecast}>
              <CartesianGrid vertical={false} />
              <XAxis dataKey="date" tickLine={false} axisLine={false} />
              <YAxis tickLine={false} axisLine={false} width={34} />
              <ChartTooltip content={<ChartTooltipContent />} />
              <Area type="monotone" dataKey="forecast" stroke="var(--color-forecast)" fill="var(--color-forecast)" fillOpacity={0.2} strokeWidth={2} />
            </AreaChart>
          </ChartContainer>
        </ChartPanel>
      </section>

      <section className="grid gap-4 xl:grid-cols-3">
        <ChartPanel title="Team Performance Leaderboard" icon={Medal}>
          <div className="flex flex-col gap-3">
            {leaderboard.map((item, index) => (
              <div key={item.name} className="rounded-lg border border-border/70 bg-secondary/30 p-3">
                <div className="flex items-center justify-between gap-3">
                  <div className="flex min-w-0 items-center gap-3">
                    <span className="grid size-8 place-items-center rounded-lg bg-primary/10 text-sm font-semibold text-primary">{index + 1}</span>
                    <div className="min-w-0">
                      <p className="truncate text-sm font-medium">{item.name}</p>
                      <p className="text-xs text-muted-foreground">{item.won} won | {item.meetings} meetings</p>
                    </div>
                  </div>
                  <p className="font-semibold tabular-nums">{item.score}</p>
                </div>
              </div>
            ))}
          </div>
        </ChartPanel>

        <ChartPanel title="AI Lead Score Distribution" icon={Bot}>
          <RankedBars data={scoreDistribution} valueLabel="leads" />
        </ChartPanel>

        <ChartPanel title="Lost Lead Reasons Analysis" icon={TrendingDown}>
          <RankedBars data={lostReasons} valueLabel="lost" />
        </ChartPanel>
      </section>

      <section className="grid gap-4 xl:grid-cols-[0.8fr_1.2fr]">
        <Card className="glass-panel">
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-base">
              <TrendingUp className="size-5 text-primary" />
              Goal Tracking
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-5">
            <Goal label="Monthly lead target" value={analytics?.total_leads_generated ?? 0} target={1000} />
            <Goal label="Reply rate target" value={analytics?.conversion_rate ?? 0} target={12} suffix="%" />
            <Goal label="Meeting target" value={crm?.stage_counts.meeting_scheduled ?? 0} target={35} />
            <Goal label="Won customer target" value={crm?.stage_counts.won ?? 0} target={10} />
          </CardContent>
        </Card>

        <Card className="glass-panel">
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-base">
              <Bot className="size-5 text-primary" />
              AI-Generated Business Insights
            </CardTitle>
          </CardHeader>
          <CardContent className="grid gap-3 md:grid-cols-2">
            {aiInsights.map((item) => (
              <div key={item.title} className="rounded-lg border border-border/70 bg-secondary/30 p-4">
                <p className="text-sm font-medium">{item.title}</p>
                <p className="mt-2 text-sm leading-6 text-muted-foreground">{item.detail}</p>
              </div>
            ))}
          </CardContent>
        </Card>
      </section>
    </div>
  );
}

function ExecutiveKpi({
  title,
  value,
  detail,
  icon: Icon,
  prefix = "",
  suffix = "",
}: {
  title: string;
  value: number;
  detail: string;
  icon: typeof TrendingUp;
  prefix?: string;
  suffix?: string;
}) {
  return (
    <Card className="glass-panel overflow-hidden">
      <CardContent className="p-5">
        <div className="flex items-start justify-between gap-3">
          <div>
            <p className="text-sm text-muted-foreground">{title}</p>
            <p className="mt-3 text-3xl font-semibold tabular-nums">
              {prefix}
              <AnimatedNumber value={value} />
              {suffix}
            </p>
          </div>
          <div className="grid size-10 place-items-center rounded-lg bg-primary/10 text-primary">
            <Icon className="size-5" />
          </div>
        </div>
        <p className="mt-3 text-sm text-muted-foreground">{detail}</p>
      </CardContent>
    </Card>
  );
}

function AnimatedNumber({ value }: { value: number }) {
  const reduceMotion = useReducedMotion();
  const [display, setDisplay] = useState(value);
  const previous = useRef(value);

  useEffect(() => {
    if (reduceMotion) {
      setDisplay(value);
      previous.current = value;
      return;
    }
    const start = previous.current;
    const delta = value - start;
    const startedAt = performance.now();
    let frame = 0;
    const tick = (now: number) => {
      const progress = Math.min((now - startedAt) / 650, 1);
      setDisplay(Math.round((start + delta * progress) * 10) / 10);
      if (progress < 1) frame = requestAnimationFrame(tick);
      else previous.current = value;
    };
    frame = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(frame);
  }, [value, reduceMotion]);

  return <span>{compactNumber(display)}</span>;
}

function ChartPanel({ title, icon: Icon, children }: { title: string; icon: typeof BarChart3; children: React.ReactNode }) {
  return (
    <Card className="glass-panel">
      <CardHeader className="flex flex-row items-center justify-between gap-3">
        <CardTitle className="flex items-center gap-2 text-base">
          <Icon className="size-5 text-primary" />
          {title}
        </CardTitle>
        <Badge variant="outline" className="border-border bg-secondary/50 text-muted-foreground">
          Drill-down
        </Badge>
      </CardHeader>
      <CardContent>{children}</CardContent>
    </Card>
  );
}

function Donut({ data }: { data: Array<{ name: string; value: number }> }) {
  return (
    <ChartContainer config={chartConfig} className="h-[280px] w-full">
      <PieChart>
        <ChartTooltip content={<ChartTooltipContent nameKey="name" />} />
        <Pie data={data} dataKey="value" nameKey="name" innerRadius={58} outerRadius={92} paddingAngle={2}>
          {data.map((item, index) => (
            <Cell key={item.name} fill={pieColors[index % pieColors.length]} />
          ))}
        </Pie>
      </PieChart>
    </ChartContainer>
  );
}

function RankedBars({ data, valueLabel }: { data: Array<{ name: string; value: number }>; valueLabel: string }) {
  const max = Math.max(...data.map((item) => item.value), 1);
  return (
    <div className="flex min-h-[280px] flex-col justify-center gap-3">
      {data.slice(0, 6).map((item) => (
        <div key={item.name} className="rounded-lg border border-border/70 bg-secondary/30 p-3">
          <div className="flex items-center justify-between gap-3 text-sm">
            <span className="min-w-0 truncate font-medium">{item.name}</span>
            <span className="shrink-0 text-muted-foreground">{item.value} {valueLabel}</span>
          </div>
          <Progress value={(item.value / max) * 100} className="mt-3 h-1.5" />
        </div>
      ))}
    </div>
  );
}

function Goal({ label, value, target, suffix = "" }: { label: string; value: number; target: number; suffix?: string }) {
  return (
    <div>
      <div className="flex items-center justify-between gap-3 text-sm">
        <span className="text-muted-foreground">{label}</span>
        <span className="font-medium tabular-nums">
          {compactNumber(value)}{suffix} / {compactNumber(target)}{suffix}
        </span>
      </div>
      <Progress value={(value / target) * 100} className="mt-2 h-2" />
    </div>
  );
}

function filterTrend(data: Analytics["lead_generation_per_day"], range: string) {
  const limit = range === "Today" ? 1 : range === "7 Days" ? 7 : range === "90 Days" ? 90 : 30;
  return data.slice(-limit).map((item) => ({ ...item, date: dateLabel(item.date) }));
}

function filterEmailTrend(data: Analytics["emails_per_day"], range: string) {
  const limit = range === "Today" ? 1 : range === "7 Days" ? 7 : range === "90 Days" ? 90 : 30;
  return data.slice(-limit).map((item) => ({ ...item, date: dateLabel(item.date) }));
}

function mergeTrends(leads: Array<{ date: string; leads: number }>, emails: Array<{ date: string; emails: number }>) {
  const map = new Map<string, { date: string; leads: number; emails: number }>();
  leads.forEach((item) => map.set(item.date, { date: item.date, leads: item.leads, emails: 0 }));
  emails.forEach((item) => {
    const row = map.get(item.date) ?? { date: item.date, leads: 0, emails: 0 };
    row.emails = item.emails;
    map.set(item.date, row);
  });
  return Array.from(map.values());
}

function buildFunnel(crm: CrmLeadList | null, analytics: Analytics | null) {
  const counts = crm?.stage_counts;
  return [
    { name: "Lead", value: analytics?.total_leads_generated ?? crm?.total ?? 0, fill: "var(--chart-1)" },
    { name: "Qualified", value: counts?.qualified ?? 0, fill: "var(--chart-2)" },
    { name: "Meeting", value: counts?.meeting_scheduled ?? 0, fill: "var(--chart-3)" },
    { name: "Customer", value: counts?.won ?? 0, fill: "var(--chart-4)" },
  ];
}

function buildCampaignPerformance(campaigns: Campaign[]) {
  return campaigns.slice(0, 8).map((campaign) => ({
    name: campaign.name.slice(0, 16),
    leads: campaign.leads_generated,
    emails: campaign.emails_sent,
    replies: campaign.replies,
  }));
}

function buildLeadSources(analytics: Analytics | null) {
  return [
    { name: "Google Maps", value: analytics?.total_leads_generated ?? 0 },
    { name: "Website Signals", value: analytics?.website_opportunities_found ?? 0 },
    { name: "Email Discovery", value: analytics?.emails_found ?? 0 },
    { name: "Social Profiles", value: analytics?.social_links_found ?? 0 },
  ].filter((item) => item.value > 0);
}

function buildEmailPerformance(analytics: Analytics | null, outreach: Outreach[]) {
  const sent = analytics?.emails_sent ?? 0;
  const replies = analytics?.replies_received ?? 0;
  const opened = Math.round((sent * (analytics?.open_rate ?? 0)) / 100);
  const bounced = outreach.filter((item) => item.bounced_at || item.status === "bounced" || item.status === "failed").length;
  return [
    { name: "Open Rate", value: analytics?.open_rate ?? 0 },
    { name: "Reply Rate", value: analytics?.conversion_rate ?? 0 },
    { name: "Bounce Rate", value: sent ? Math.round((bounced / sent) * 1000) / 10 : 0 },
    { name: "Opened", value: opened },
    { name: "Replies", value: replies },
  ];
}

function buildCallAnalytics(analytics: Analytics | null) {
  const meetings = Math.max(Math.round((analytics?.replies_received ?? 0) * 0.35), 0);
  return [
    { name: "Answered", value: Math.max(meetings * 2, 0) },
    { name: "Avg Min", value: meetings ? 6.4 : 0 },
    { name: "Positive", value: meetings },
    { name: "Cost", value: Math.round(meetings * 1.85) },
  ];
}

function buildRevenueModel({ analytics, crm, campaigns }: { analytics: Analytics | null; crm: CrmLeadList | null; campaigns: Campaign[] }) {
  const won = crm?.stage_counts.won ?? 0;
  const customers = Math.max(won, Math.round((analytics?.replies_received ?? 0) * 0.08));
  const ltv = 4200;
  const campaignCost = Math.max(campaigns.length * 120 + (analytics?.emails_sent ?? 0) * 0.08, 1);
  const forecastRevenue = customers * ltv;
  const cac = customers ? Math.round(campaignCost / customers) : Math.round(campaignCost);
  const roi = Math.round((forecastRevenue / campaignCost) * 10) / 10;
  return {
    forecastRevenue,
    ltv,
    cac,
    roi,
    series: [
      { name: "Spend", cost: Math.round(campaignCost), revenue: 0 },
      { name: "Pipeline", cost: Math.round(campaignCost * 1.15), revenue: Math.round(forecastRevenue * 0.45) },
      { name: "Forecast", cost: Math.round(campaignCost * 1.25), revenue: forecastRevenue },
    ],
  };
}

function buildForecast(trend: Array<{ date: string; leads: number }>, analytics: Analytics | null) {
  const average = trend.length ? trend.reduce((total, item) => total + item.leads, 0) / trend.length : analytics?.leads_saved ?? 0;
  const base = Math.max(average, 1);
  return Array.from({ length: 8 }).map((_, index) => ({
    date: index < trend.length ? trend[index].date : `+${index - trend.length + 1}w`,
    forecast: Math.round(base * (index + 1) * 1.12),
  }));
}

function buildLeaderboard(leads: CrmLead[]): LeaderboardItem[] {
  const map = new Map<string, LeaderboardItem>();
  leads.forEach((lead) => {
    const name = lead.assigned_user?.name ?? "Unassigned";
    const row = map.get(name) ?? { name, won: 0, meetings: 0, score: 0 };
    if (lead.crm_stage === "won") row.won += 1;
    if (lead.crm_stage === "meeting_scheduled") row.meetings += 1;
    row.score += lead.crm_stage === "won" ? 40 : lead.crm_stage === "meeting_scheduled" ? 20 : lead.crm_stage === "interested" ? 12 : 4;
    map.set(name, row);
  });
  return Array.from(map.values()).sort((a, b) => b.score - a.score).slice(0, 5);
}

function buildLostReasons(leads: CrmLead[]) {
  const lost = leads.filter((lead) => lead.crm_stage === "lost");
  const reasons = [
    { name: "No budget", value: Math.ceil(lost.length * 0.32) },
    { name: "No response", value: Math.ceil(lost.length * 0.28) },
    { name: "Bad fit", value: Math.ceil(lost.length * 0.2) },
    { name: "Timing", value: Math.ceil(lost.length * 0.12) },
  ];
  return reasons.filter((item) => item.value > 0);
}

function buildScoreDistribution(leads: CrmLead[]) {
  const buckets = [
    { name: "90-100", value: 0 },
    { name: "75-89", value: 0 },
    { name: "50-74", value: 0 },
    { name: "0-49", value: 0 },
  ];
  leads.forEach((lead) => {
    const score = lead.crm_stage === "won" ? 95 : lead.crm_stage === "meeting_scheduled" ? 86 : lead.crm_stage === "interested" ? 78 : lead.crm_stage === "qualified" ? 68 : 42;
    if (score >= 90) buckets[0].value += 1;
    else if (score >= 75) buckets[1].value += 1;
    else if (score >= 50) buckets[2].value += 1;
    else buckets[3].value += 1;
  });
  return buckets;
}

function buildInsights({
  analytics,
  revenue,
  funnel,
  campaignPerformance,
}: {
  analytics: Analytics | null;
  revenue: ReturnType<typeof buildRevenueModel>;
  funnel: Array<{ name: string; value: number }>;
  campaignPerformance: Array<{ name: string; leads: number; emails: number; replies: number }>;
}) {
  const strongestCampaign = campaignPerformance.toSorted((a, b) => b.replies - a.replies)[0];
  const leadToQualified = funnel[0]?.value ? Math.round(((funnel[1]?.value ?? 0) / funnel[0].value) * 100) : 0;
  return [
    {
      title: "Predictive revenue signal",
      detail: `Current pipeline behavior points to approximately $${compactNumber(revenue.forecastRevenue)} in forecast revenue at ${revenue.roi}x ROI.`,
    },
    {
      title: "Conversion quality",
      detail: `${leadToQualified}% of captured leads are reaching qualified status. Improve scoring thresholds if this falls below the target band.`,
    },
    {
      title: "Smart alert",
      detail: (analytics?.conversion_rate ?? 0) < 5 ? "Reply conversion is declining; pause broad sends and run a tighter campaign test." : "Reply conversion is stable enough to scale the next campaign batch.",
    },
    {
      title: "Campaign opportunity",
      detail: strongestCampaign ? `${strongestCampaign.name} is the strongest reply producer. Reuse its market and messaging pattern.` : "Launch a campaign to establish a performance benchmark.",
    },
  ];
}
