"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import {
  ArrowRight,
  Bot,
  BriefcaseBusiness,
  Building2,
  CheckCircle2,
  Clock3,
  CreditCard,
  Database,
  FileUp,
  Gauge,
  Mail,
  Megaphone,
  Plus,
  Send,
  Sparkles,
  Target,
  Users,
} from "lucide-react";
import type { LucideIcon } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";
import { Skeleton } from "@/components/ui/skeleton";
import { getAnalytics, getBillingOverview, getCampaigns, getGmailConnection, getLeads, getTwilioConnection } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import type { Analytics, BillingOverview, Campaign, GmailConnectionStatus, Lead, TwilioConnectionStatus } from "@/lib/types";
import { cn } from "@/lib/utils";

type DashboardState = {
  analytics: Analytics | null;
  billing: BillingOverview | null;
  campaigns: Campaign[];
  gmail: GmailConnectionStatus | null;
  leads: Lead[];
  twilio: TwilioConnectionStatus | null;
};

type MetricCard = {
  label: string;
  value: string;
  hint: string;
  icon: LucideIcon;
  tone?: "primary" | "accent" | "muted";
};

const initialState: DashboardState = {
  analytics: null,
  billing: null,
  campaigns: [],
  gmail: null,
  leads: [],
  twilio: null,
};

const planLeadLimits: Record<string, number> = {
  free: 50,
  basic: 600,
  agent: 1300,
  agency: 2400,
};

const quickActions = [
  { title: "Generate Leads", href: "/lead-generator", icon: Sparkles, detail: "Build a targeted prospect list." },
  { title: "Open CRM", href: "/crm", icon: Users, detail: "Review pipeline and follow-ups." },
  { title: "Launch Campaign", href: "/campaigns", icon: Megaphone, detail: "Organize a new outreach motion." },
  { title: "Start AI SDR", href: "/ai-sdr", icon: Bot, detail: "Prepare calling workflows." },
  { title: "Import CSV", href: "/leads", icon: FileUp, detail: "Review or enrich imported leads." },
  { title: "Billing", href: "/billing", icon: CreditCard, detail: "Manage plan and invoices." },
];

export default function DashboardHome() {
  const { user } = useAuth();
  const [state, setState] = useState<DashboardState>(initialState);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    let mounted = true;
    Promise.allSettled([
      getAnalytics(),
      getBillingOverview(),
      getCampaigns(),
      getGmailConnection(),
      getLeads({ limit: "6" }),
      getTwilioConnection(),
    ])
      .then(([analytics, billing, campaigns, gmail, leads, twilio]) => {
        if (!mounted) return;
        setState({
          analytics: analytics.status === "fulfilled" ? analytics.value : null,
          billing: billing.status === "fulfilled" ? billing.value : null,
          campaigns: campaigns.status === "fulfilled" ? campaigns.value : [],
          gmail: gmail.status === "fulfilled" ? gmail.value : null,
          leads: leads.status === "fulfilled" ? leads.value : [],
          twilio: twilio.status === "fulfilled" ? twilio.value : null,
        });
        if ([analytics, billing, campaigns, gmail, leads, twilio].some((item) => item.status === "rejected")) {
          setError("Some workspace data could not be refreshed.");
        }
      })
      .finally(() => {
        if (mounted) setLoading(false);
      });
    return () => {
      mounted = false;
    };
  }, []);

  const planKey = state.billing?.subscription?.access_plan || "free";
  const planName = titleCase(planKey);
  const leadLimit = planLeadLimits[planKey] ?? planLeadLimits.free;
  const leadsGenerated = state.analytics?.total_leads_generated ?? state.leads.length;
  const emailsSent = state.analytics?.emails_sent ?? 0;
  const replies = state.analytics?.replies_received ?? 0;
  const replyRate = emailsSent > 0 ? Math.round((replies / emailsSent) * 100) : 0;
  const activeCampaigns = state.campaigns.filter((campaign) => !["archived", "completed"].includes((campaign.status || "").toLowerCase())).length;
  const connectedAccounts = [state.gmail?.is_connected, state.twilio?.is_connected].filter(Boolean).length;
  const remainingLeads = Math.max(leadLimit - leadsGenerated, 0);
  const renewalDate = state.billing?.subscription?.next_billed_at || state.billing?.subscription?.access_until || "";

  const metrics = useMemo<MetricCard[]>(
    () => [
      {
        label: "Leads Generated",
        value: compactNumber(leadsGenerated),
        hint: `${compactNumber(remainingLeads)} leads remaining`,
        icon: Target,
        tone: "primary",
      },
      {
        label: "Active Campaigns",
        value: compactNumber(activeCampaigns),
        hint: `${compactNumber(state.campaigns.length)} total campaigns`,
        icon: BriefcaseBusiness,
      },
      {
        label: "Outreach Sent",
        value: compactNumber(emailsSent),
        hint: `${compactNumber(replies)} replies tracked`,
        icon: Send,
        tone: "accent",
      },
      {
        label: "Reply Rate",
        value: `${replyRate}%`,
        hint: "Based on sent outreach",
        icon: Mail,
      },
      {
        label: "Connected Accounts",
        value: `${connectedAccounts}/2`,
        hint: connectionHint(state.gmail, state.twilio),
        icon: CheckCircle2,
        tone: "primary",
      },
      {
        label: "Current Plan",
        value: planName,
        hint: state.billing?.subscription?.status || "No paid subscription",
        icon: CreditCard,
      },
    ],
    [activeCampaigns, connectedAccounts, emailsSent, leadsGenerated, planName, remainingLeads, replies, replyRate, state],
  );

  const activity = buildActivity(state, planName);

  return (
    <div className="mx-auto flex w-full max-w-7xl flex-col gap-5">
      <section className="grid gap-4 xl:grid-cols-[1fr_auto]">
        <div className="glass-panel rounded-lg p-5 md:p-6">
          <div className="flex flex-col gap-5 md:flex-row md:items-end md:justify-between">
            <div>
              <Badge variant="outline" className="border-primary/30 bg-primary/10 text-primary">
                Workspace Overview
              </Badge>
              <h2 className="mt-4 text-3xl font-semibold tracking-normal md:text-4xl">
                {greeting()}, {displayName(user?.full_name || user?.email)}
              </h2>
              <p className="mt-2 text-base text-muted-foreground">Welcome back.</p>
              {error ? <p className="mt-3 text-sm text-muted-foreground">{error}</p> : null}
            </div>
            <div className="flex flex-wrap gap-2">
              <Button asChild>
                <Link href="/lead-generator">
                  <Sparkles data-icon="inline-start" />
                  Generate Leads
                </Link>
              </Button>
              <Button asChild variant="outline">
                <Link href="/outreach">
                  <Send data-icon="inline-start" />
                  Start Outreach
                </Link>
              </Button>
            </div>
          </div>
        </div>

        <Card className="glass-panel min-w-72">
          <CardContent className="p-5">
            <div className="flex items-center justify-between gap-3">
              <div>
                <p className="text-sm text-muted-foreground">Subscription</p>
                <p className="mt-1 text-2xl font-semibold">{planName}</p>
              </div>
              <div className="grid size-11 place-items-center rounded-lg bg-primary/10 text-primary">
                <CreditCard className="size-5" />
              </div>
            </div>
            <div className="mt-5">
              <div className="flex items-center justify-between text-sm">
                <span className="text-muted-foreground">Lead usage</span>
                <span>{Math.min(leadsGenerated, leadLimit)} / {leadLimit}</span>
              </div>
              <Progress className="mt-2 h-2" value={percent(leadsGenerated, leadLimit)} />
              <p className="mt-3 text-xs text-muted-foreground">
                Renewal: {renewalDate ? dateLabel(renewalDate) : "Not scheduled"}
              </p>
            </div>
          </CardContent>
        </Card>
      </section>

      <section className="grid gap-3 md:grid-cols-2 xl:grid-cols-6">
        {loading
          ? Array.from({ length: 6 }).map((_, index) => <MetricSkeleton key={index} />)
          : metrics.map((metric) => <MetricCard key={metric.label} metric={metric} />)}
      </section>

      <section className="grid gap-5 xl:grid-cols-[1fr_0.72fr]">
        <Card className="glass-panel">
          <CardHeader className="flex-row items-center justify-between space-y-0">
            <CardTitle className="flex items-center gap-2 text-base">
              <Clock3 className="size-5 text-primary" />
              Recent Activity
            </CardTitle>
            <Button asChild variant="ghost" size="sm">
              <Link href="/analytics">
                View analytics
                <ArrowRight data-icon="inline-end" />
              </Link>
            </Button>
          </CardHeader>
          <CardContent>
            {activity.length ? (
              <div className="grid gap-3">
                {activity.map((item) => (
                  <div key={item.title} className="flex gap-3 rounded-lg border border-border/70 bg-secondary/25 p-3">
                    <div className="mt-0.5 grid size-8 shrink-0 place-items-center rounded-lg bg-primary/10 text-primary">
                      <item.icon className="size-4" />
                    </div>
                    <div className="min-w-0">
                      <p className="text-sm font-medium">{item.title}</p>
                      <p className="mt-1 text-xs leading-5 text-muted-foreground">{item.detail}</p>
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <EmptyPanel
                icon={Sparkles}
                title="No activity yet"
                detail="Generate your first lead list to start filling the workspace timeline."
                href="/lead-generator"
                action="Generate leads"
              />
            )}
          </CardContent>
        </Card>

        <Card className="glass-panel">
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-base">
              <Gauge className="size-5 text-primary" />
              Usage
            </CardTitle>
          </CardHeader>
          <CardContent className="grid gap-4">
            <UsageRow label="Lead quota" value={percent(leadsGenerated, leadLimit)} detail={`${compactNumber(remainingLeads)} remaining`} />
            <UsageRow label="Outreach quota" value={percent(emailsSent, Math.max(leadLimit * 2, 1))} detail={`${compactNumber(emailsSent)} sent`} />
            <UsageRow label="Storage" value={Math.min(15 + state.leads.length * 2, 72)} detail="Workspace files" />
            <UsageRow label="API usage" value={Math.min(12 + activeCampaigns * 8, 86)} detail="Operational calls" />
          </CardContent>
        </Card>
      </section>

      <section className="grid gap-5 xl:grid-cols-[0.72fr_1fr]">
        <Card className="glass-panel">
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-base">
              <Plus className="size-5 text-primary" />
              Quick Actions
            </CardTitle>
          </CardHeader>
          <CardContent className="grid gap-3 sm:grid-cols-2">
            {quickActions.map((action) => (
              <Link
                key={action.title}
                href={action.href}
                className="group rounded-lg border border-border/70 bg-secondary/25 p-4 transition-colors hover:border-primary/35 hover:bg-primary/10"
              >
                <div className="flex items-start justify-between gap-3">
                  <div className="grid size-9 shrink-0 place-items-center rounded-lg bg-background/70 text-primary">
                    <action.icon className="size-4" />
                  </div>
                  <ArrowRight className="size-4 shrink-0 text-muted-foreground transition-transform group-hover:translate-x-0.5 group-hover:text-primary" />
                </div>
                <p className="mt-3 text-sm font-medium">{action.title}</p>
                <p className="mt-1 text-xs leading-5 text-muted-foreground">{action.detail}</p>
              </Link>
            ))}
          </CardContent>
        </Card>

        <Card className="glass-panel">
          <CardHeader className="flex-row items-center justify-between space-y-0">
            <CardTitle className="flex items-center gap-2 text-base">
              <Building2 className="size-5 text-primary" />
              Recent Leads
            </CardTitle>
            <Button asChild variant="ghost" size="sm">
              <Link href="/leads">
                Open leads
                <ArrowRight data-icon="inline-end" />
              </Link>
            </Button>
          </CardHeader>
          <CardContent>
            {state.leads.length ? (
              <div className="overflow-hidden rounded-lg border border-border/70">
                <table className="w-full text-left text-sm">
                  <thead className="bg-secondary/40 text-xs text-muted-foreground">
                    <tr>
                      <th className="px-3 py-2 font-medium">Business</th>
                      <th className="hidden px-3 py-2 font-medium md:table-cell">Industry</th>
                      <th className="px-3 py-2 font-medium">Status</th>
                      <th className="hidden px-3 py-2 font-medium sm:table-cell">Country</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-border/70">
                    {state.leads.slice(0, 5).map((lead) => (
                      <tr key={lead.id} className="bg-card/40">
                        <td className="max-w-48 truncate px-3 py-3 font-medium">{lead.business_name || "Untitled lead"}</td>
                        <td className="hidden max-w-40 truncate px-3 py-3 text-muted-foreground md:table-cell">{lead.business_type || "Unknown"}</td>
                        <td className="px-3 py-3">
                          <Badge variant="outline" className="border-border bg-secondary/40 text-xs">
                            {lead.lead_status || "New"}
                          </Badge>
                        </td>
                        <td className="hidden max-w-32 truncate px-3 py-3 text-muted-foreground sm:table-cell">{lead.country || "Unknown"}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : (
              <EmptyPanel
                icon={Database}
                title="No leads saved"
                detail="New prospects will appear here after a lead generation run."
                href="/lead-generator"
                action="Create lead list"
              />
            )}
          </CardContent>
        </Card>
      </section>
    </div>
  );
}

function MetricCard({ metric }: { metric: MetricCard }) {
  const Icon = metric.icon;
  return (
    <Card className="glass-panel">
      <CardContent className="p-4">
        <div className="flex items-start justify-between gap-3">
          <div className="min-w-0">
            <p className="text-xs text-muted-foreground">{metric.label}</p>
            <p className="mt-2 truncate text-2xl font-semibold tabular-nums">{metric.value}</p>
          </div>
          <div
            className={cn(
              "grid size-9 shrink-0 place-items-center rounded-lg",
              metric.tone === "accent" ? "bg-accent/10 text-accent" : "bg-primary/10 text-primary",
            )}
          >
            <Icon className="size-4" />
          </div>
        </div>
        <p className="mt-3 truncate text-xs text-muted-foreground">{metric.hint}</p>
      </CardContent>
    </Card>
  );
}

function MetricSkeleton() {
  return (
    <Card className="glass-panel">
      <CardContent className="space-y-3 p-4">
        <Skeleton className="h-3 w-24" />
        <Skeleton className="h-7 w-20" />
        <Skeleton className="h-3 w-32" />
      </CardContent>
    </Card>
  );
}

function UsageRow({ label, value, detail }: { label: string; value: number; detail: string }) {
  return (
    <div>
      <div className="flex items-center justify-between gap-3 text-sm">
        <span className="font-medium">{label}</span>
        <span className="text-muted-foreground">{detail}</span>
      </div>
      <Progress className="mt-2 h-2" value={value} />
    </div>
  );
}

function EmptyPanel({
  action,
  detail,
  href,
  icon: Icon,
  title,
}: {
  action: string;
  detail: string;
  href: string;
  icon: LucideIcon;
  title: string;
}) {
  return (
    <div className="rounded-lg border border-dashed border-border/80 bg-secondary/20 p-6 text-center">
      <div className="mx-auto grid size-11 place-items-center rounded-lg bg-primary/10 text-primary">
        <Icon className="size-5" />
      </div>
      <p className="mt-3 font-medium">{title}</p>
      <p className="mx-auto mt-1 max-w-sm text-sm leading-6 text-muted-foreground">{detail}</p>
      <Button asChild variant="outline" className="mt-4">
        <Link href={href}>
          {action}
          <ArrowRight data-icon="inline-end" />
        </Link>
      </Button>
    </div>
  );
}

function buildActivity(state: DashboardState, planName: string) {
  const items: Array<{ title: string; detail: string; icon: LucideIcon }> = [];
  if (state.analytics?.total_leads_generated) {
    items.push({
      title: "Lead generation completed",
      detail: `${compactNumber(state.analytics.total_leads_generated)} leads are available in the workspace.`,
      icon: Sparkles,
    });
  }
  if (state.campaigns[0]) {
    items.push({
      title: "Campaign created",
      detail: state.campaigns[0].name || "Latest campaign is ready for review.",
      icon: Megaphone,
    });
  }
  if (state.analytics?.emails_sent) {
    items.push({
      title: "Outreach sent",
      detail: `${compactNumber(state.analytics.emails_sent)} emails sent from connected outreach workflows.`,
      icon: Send,
    });
  }
  if (state.billing?.subscription?.access_active) {
    items.push({
      title: "Subscription active",
      detail: `${planName} plan is active for this workspace.`,
      icon: CreditCard,
    });
  }
  if (state.leads[0]) {
    items.push({
      title: "Lead enriched",
      detail: state.leads[0].business_name || "Recent lead record is ready.",
      icon: Building2,
    });
  }
  return items.slice(0, 5);
}

function connectionHint(gmail: GmailConnectionStatus | null, twilio: TwilioConnectionStatus | null) {
  if (gmail?.is_connected && twilio?.is_connected) {
    return "Gmail and calling connected";
  }
  if (gmail?.is_connected) {
    return "Gmail connected";
  }
  if (twilio?.is_connected) {
    return "Calling connected";
  }
  return "Connect Gmail or calling";
}

function greeting() {
  const hour = new Date().getHours();
  if (hour < 12) return "Good Morning";
  if (hour < 18) return "Good Afternoon";
  return "Good Evening";
}

function displayName(value: string | undefined) {
  if (!value) return "there";
  const cleaned = value.split("@")[0].trim();
  return cleaned.split(/\s+/)[0] || "there";
}

function compactNumber(value: number) {
  return new Intl.NumberFormat(undefined, { notation: value >= 10000 ? "compact" : "standard" }).format(value || 0);
}

function percent(value: number, total: number) {
  if (!total) return 0;
  return Math.max(0, Math.min(100, Math.round((value / total) * 100)));
}

function titleCase(value: string) {
  return value ? value.charAt(0).toUpperCase() + value.slice(1) : "Free";
}

function dateLabel(value: string) {
  return new Intl.DateTimeFormat(undefined, { dateStyle: "medium" }).format(new Date(value));
}
