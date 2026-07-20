"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import Link from "next/link";
import {
  AlertTriangle,
  ArrowUpRight,
  Bot,
  CalendarClock,
  CheckCircle2,
  Clock3,
  Flame,
  Mail,
  Megaphone,
  PhoneCall,
  Play,
  Radio,
  Rocket,
  Send,
  Sparkles,
  Target,
  Users,
  Zap,
} from "lucide-react";
import { useReducedMotion } from "framer-motion";

import { PipelineProgress } from "@/components/pipeline-progress";
import { StatusBadge } from "@/components/status-badge";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";
import { Skeleton } from "@/components/ui/skeleton";
import {
  getAnalytics,
  getCampaigns,
  getCrmLeads,
  getLatestGenerationJob,
  getOutreach,
} from "@/lib/api";
import {
  compactNumber,
  dateTimeLabel,
  relativeDateLabel,
  statusLabel,
} from "@/lib/format";
import type { Analytics, Campaign, CrmLead, CrmLeadList, GenerationJob, Outreach } from "@/lib/types";
import { cn } from "@/lib/utils";

const dailyGoal = 50;
const weeklyGoal = 250;

export default function DashboardHome() {
  const [analytics, setAnalytics] = useState<Analytics | null>(null);
  const [campaigns, setCampaigns] = useState<Campaign[]>([]);
  const [crm, setCrm] = useState<CrmLeadList | null>(null);
  const [outreach, setOutreach] = useState<Outreach[]>([]);
  const [job, setJob] = useState<GenerationJob | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    let mounted = true;

    Promise.all([
      getAnalytics().catch((err: Error) => {
        setError(err.message);
        return null;
      }),
      getCampaigns().catch(() => [] as Campaign[]),
      getCrmLeads({ limit: "500" }).catch(() => null),
      getOutreach().catch(() => [] as Outreach[]),
      getLatestGenerationJob().catch(() => null),
    ]).then(([analyticsResult, campaignRows, crmRows, outreachRows, jobResult]) => {
      if (!mounted) return;
      setAnalytics(analyticsResult);
      setCampaigns(campaignRows);
      setCrm(crmRows);
      setOutreach(outreachRows);
      setJob(jobResult);
      setLoading(false);
    });

    return () => {
      mounted = false;
    };
  }, []);

  const leadSeries = analytics?.lead_generation_per_day ?? [];
  const todaysLeads = leadSeries.at(-1)?.leads ?? analytics?.leads_saved ?? 0;
  const weeklyLeads = leadSeries.slice(-7).reduce((total, item) => total + item.leads, 0);
  const dueFollowUps = useMemo(() => getUpcomingFollowUps(crm?.items ?? []), [crm]);
  const hotLeads = useMemo(() => getHotLeads(crm?.items ?? []), [crm]);
  const activeCampaigns = useMemo(() => getActiveCampaigns(campaigns), [campaigns]);
  const recentActivity = useMemo(() => analytics?.recent_activity ?? [], [analytics]);
  const activityStream = useMemo(
    () => buildActivityStream(recentActivity, outreach),
    [recentActivity, outreach],
  );
  const agent = getAgentStatus(job);
  const pipelineCards = getPipelineCards(crm);
  const recommendations = getRecommendations({
    analytics,
    agent,
    hotLeadCount: hotLeads.length,
    followUpCount: dueFollowUps.length,
    activeCampaignCount: activeCampaigns.length,
  });

  if (loading) {
    return <DashboardSkeleton />;
  }

  return (
    <div className="flex flex-col gap-6">
      <section className="rounded-lg border border-primary/20 bg-card/80 p-4 shadow-2xl shadow-black/20 backdrop-blur-xl md:p-5">
        <div className="flex flex-col gap-5 xl:flex-row xl:items-center xl:justify-between">
          <div className="max-w-3xl">
            <Badge variant="outline" className="border-primary/30 bg-primary/10 text-primary">
              Operational Command Center
            </Badge>
            <h2 className="mt-3 text-2xl font-semibold tracking-normal md:text-3xl">
              Live lead generation control room
            </h2>
            <p className="mt-2 text-sm leading-6 text-muted-foreground">
              Monitor today&apos;s production, intervene on urgent leads, and launch the next revenue action.
            </p>
          </div>
          <div className="grid gap-3 sm:grid-cols-2 xl:min-w-[560px] xl:grid-cols-4">
            <CommandKpi title="Today" value={todaysLeads} suffix=" leads" icon={Target} progress={(todaysLeads / dailyGoal) * 100} />
            <CommandKpi title="7 days" value={weeklyLeads} suffix=" leads" icon={Rocket} progress={(weeklyLeads / weeklyGoal) * 100} />
            <CommandKpi title="Hot queue" value={hotLeads.length} suffix=" leads" icon={Flame} tone="hot" />
            <CommandKpi title="Follow-ups" value={dueFollowUps.length} suffix=" due" icon={CalendarClock} tone="warning" />
          </div>
        </div>
      </section>

      {error ? (
        <Card className="glass-panel">
          <CardContent className="p-5 text-sm text-destructive">{error}</CardContent>
        </Card>
      ) : null}

      <section className="grid gap-4 xl:grid-cols-[1.25fr_0.75fr]">
        <Card className="glass-panel overflow-hidden">
          <CardHeader className="flex flex-row items-start justify-between gap-4">
            <div>
              <CardTitle className="flex items-center gap-2 text-base">
                <Bot className="size-5 text-primary" />
                AI Agent Status
              </CardTitle>
              <p className="mt-1 text-sm text-muted-foreground">
                {job?.stage || "Ready for the next generation run"}
              </p>
            </div>
            <StatusBadge value={agent.status} />
          </CardHeader>
          <CardContent className="grid gap-4 md:grid-cols-[220px_1fr]">
            <div className={cn("rounded-lg border p-4", agent.className)}>
              <div className="flex items-center gap-3">
                <div className="grid size-11 place-items-center rounded-lg bg-background/60">
                  <agent.icon className={cn("size-5", agent.pulse && "animate-pulse")} />
                </div>
                <div>
                  <p className="text-sm text-muted-foreground">Current mode</p>
                  <p className="text-xl font-semibold">{agent.label}</p>
                </div>
              </div>
              <div className="mt-5 grid grid-cols-3 gap-2 text-center text-xs">
                <MiniStat label="Progress" value={`${job?.progress ?? 0}%`} />
                <MiniStat label="Saved" value={job?.success_counter ?? analytics?.leads_saved ?? 0} />
                <MiniStat label="Failed" value={job?.failure_counter ?? analytics?.failed_leads ?? 0} />
              </div>
            </div>
            <div className="grid gap-3 sm:grid-cols-2">
              <QuickAction href="/lead-generator" label="Generate Leads" icon={Sparkles} />
              <QuickAction href="/ai-sdr/call" label="Start AI SDR Call" icon={PhoneCall} />
              <QuickAction href="/campaigns" label="Launch Campaign" icon={Megaphone} />
              <QuickAction href="/outreach" label="Send Emails" icon={Send} />
            </div>
          </CardContent>
        </Card>

        <Card className="glass-panel">
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-base">
              <Zap className="size-5 text-chart-3" />
              Notifications & AI Recommendations
            </CardTitle>
          </CardHeader>
          <CardContent className="flex flex-col gap-3">
            {recommendations.map((item) => (
              <div key={item.title} className="rounded-lg border border-border/70 bg-secondary/30 p-3">
                <div className="flex items-start gap-3">
                  <item.icon className={cn("mt-0.5 size-4 shrink-0", item.className)} />
                  <div>
                    <p className="text-sm font-medium">{item.title}</p>
                    <p className="mt-1 text-xs leading-5 text-muted-foreground">{item.detail}</p>
                  </div>
                </div>
              </div>
            ))}
          </CardContent>
        </Card>
      </section>

      <PipelineProgress job={job} />

      <section className="grid gap-4 xl:grid-cols-4">
        {pipelineCards.map((item) => (
          <Card key={item.label} className="glass-panel">
            <CardContent className="p-4">
              <div className="flex items-center justify-between gap-3">
                <div>
                  <p className="text-sm text-muted-foreground">{item.label}</p>
                  <p className="mt-2 text-2xl font-semibold tabular-nums">{item.value}</p>
                </div>
                <div className="grid size-10 place-items-center rounded-lg bg-secondary/70 text-primary">
                  <item.icon className="size-5" />
                </div>
              </div>
              <Progress value={item.progress} className="mt-4 h-1.5" />
            </CardContent>
          </Card>
        ))}
      </section>

      <section className="grid gap-4 xl:grid-cols-[1fr_1fr_0.9fr]">
        <OperationsPanel title="Active Campaigns" icon={Megaphone}>
          {activeCampaigns.length ? (
            activeCampaigns.map((campaign) => (
              <div key={campaign.id} className="rounded-lg border border-border/70 bg-secondary/30 p-3">
                <div className="flex items-start justify-between gap-3">
                  <div className="min-w-0">
                    <p className="truncate text-sm font-medium">{campaign.name}</p>
                    <p className="mt-1 truncate text-xs text-muted-foreground">
                      {[campaign.city, campaign.country, campaign.business_type].filter(Boolean).join(" | ") || "All markets"}
                    </p>
                  </div>
                  <StatusBadge value={campaign.status} />
                </div>
                <Progress value={campaign.max_leads ? (campaign.leads_generated / campaign.max_leads) * 100 : 0} className="mt-3 h-1.5" />
                <p className="mt-2 text-xs text-muted-foreground">
                  {campaign.leads_generated} of {campaign.max_leads || "unlimited"} leads generated
                </p>
              </div>
            ))
          ) : (
            <EmptyState text="No active campaigns. Launch a campaign when the next market is ready." />
          )}
        </OperationsPanel>

        <OperationsPanel title="Hot Leads Requiring Action" icon={Flame}>
          {hotLeads.length ? (
            hotLeads.map((lead) => (
              <LeadActionRow key={lead.id} lead={lead} />
            ))
          ) : (
            <EmptyState text="No urgent leads in the CRM queue right now." />
          )}
        </OperationsPanel>

        <OperationsPanel title="Upcoming Follow-ups & Meetings" icon={CalendarClock}>
          {dueFollowUps.length ? (
            dueFollowUps.map((lead) => (
              <div key={lead.id} className="rounded-lg border border-border/70 bg-secondary/30 p-3">
                <div className="flex items-start justify-between gap-3">
                  <div className="min-w-0">
                    <p className="truncate text-sm font-medium">{lead.business_name}</p>
                    <p className="mt-1 text-xs text-muted-foreground">{dateTimeLabel(lead.next_follow_up_at)}</p>
                  </div>
                  <StatusBadge value={lead.crm_stage} />
                </div>
              </div>
            ))
          ) : (
            <EmptyState text="No follow-ups or meetings scheduled in the near-term queue." />
          )}
        </OperationsPanel>
      </section>

      <section className="grid gap-4 xl:grid-cols-[1fr_1fr]">
        <OperationsPanel title="Recent Activities Timeline" icon={Clock3}>
          {recentActivity.length ? (
            recentActivity.slice(0, 8).map((item) => (
              <TimelineItem key={item.id} title={statusLabel(item.type)} detail={activitySummary(item.metadata)} time={relativeDateLabel(item.created_at)} />
            ))
          ) : (
            <EmptyState text="Operational events will appear after lead generation or outreach runs." />
          )}
        </OperationsPanel>

        <OperationsPanel title="Recent AI SDR Calls & Email Activity" icon={Mail}>
          {activityStream.length ? (
            activityStream.slice(0, 8).map((item) => (
              <TimelineItem key={item.id} title={item.title} detail={item.detail} time={item.time} tone={item.tone} />
            ))
          ) : (
            <EmptyState text="Calls and email events will appear once SDR activity starts." />
          )}
        </OperationsPanel>
      </section>
    </div>
  );
}

function CommandKpi({
  title,
  value,
  suffix,
  icon: Icon,
  progress,
  tone = "normal",
}: {
  title: string;
  value: number;
  suffix: string;
  icon: typeof Target;
  progress?: number;
  tone?: "normal" | "hot" | "warning";
}) {
  return (
    <div className="rounded-lg border border-border/70 bg-secondary/30 p-4">
      <div className="flex items-center justify-between gap-3">
        <p className="text-sm text-muted-foreground">{title}</p>
        <Icon className={cn("size-4", tone === "hot" && "text-chart-4", tone === "warning" && "text-chart-3", tone === "normal" && "text-primary")} />
      </div>
      <p className="mt-3 text-2xl font-semibold tabular-nums">
        <AnimatedNumber value={value} />
        <span className="text-sm font-medium text-muted-foreground">{suffix}</span>
      </p>
      {progress !== undefined ? <Progress value={clamp(progress)} className="mt-3 h-1.5" /> : null}
    </div>
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
      setDisplay(Math.round(start + delta * progress));
      if (progress < 1) frame = requestAnimationFrame(tick);
      else previous.current = value;
    };
    frame = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(frame);
  }, [value, reduceMotion]);

  return <span>{compactNumber(display)}</span>;
}

function QuickAction({ href, label, icon: Icon }: { href: string; label: string; icon: typeof Sparkles }) {
  return (
    <Button asChild size="lg" className="h-16 justify-between px-4">
      <Link href={href}>
        <span className="flex items-center gap-2">
          <Icon data-icon="inline-start" />
          {label}
        </span>
        <ArrowUpRight className="size-4" />
      </Link>
    </Button>
  );
}

function OperationsPanel({
  title,
  icon: Icon,
  children,
}: {
  title: string;
  icon: typeof Flame;
  children: React.ReactNode;
}) {
  return (
    <Card className="glass-panel">
      <CardHeader>
        <CardTitle className="flex items-center gap-2 text-base">
          <Icon className="size-5 text-primary" />
          {title}
        </CardTitle>
      </CardHeader>
      <CardContent className="flex flex-col gap-3">{children}</CardContent>
    </Card>
  );
}

function LeadActionRow({ lead }: { lead: CrmLead }) {
  return (
    <div className="rounded-lg border border-border/70 bg-secondary/30 p-3">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="truncate text-sm font-medium">{lead.business_name}</p>
          <p className="mt-1 truncate text-xs text-muted-foreground">
            {[lead.city, lead.industry].filter(Boolean).join(" | ") || lead.email || "CRM lead"}
          </p>
        </div>
        <StatusBadge value={lead.crm_stage} />
      </div>
      <div className="mt-3 flex flex-wrap gap-2">
        {lead.email ? (
          <Button asChild size="sm" variant="outline">
            <a href={`mailto:${lead.email}`}>
              <Mail data-icon="inline-start" />
              Email
            </a>
          </Button>
        ) : null}
        {lead.phone ? (
          <Button asChild size="sm" variant="outline">
            <a href={`tel:${lead.phone}`}>
              <PhoneCall data-icon="inline-start" />
              Call
            </a>
          </Button>
        ) : null}
      </div>
    </div>
  );
}

function TimelineItem({
  title,
  detail,
  time,
  tone = "normal",
}: {
  title: string;
  detail: string;
  time: string;
  tone?: "normal" | "success" | "warning";
}) {
  return (
    <div className="flex gap-3 rounded-lg border border-border/70 bg-secondary/30 p-3">
      <div className={cn("mt-1 size-2.5 rounded-full bg-primary", tone === "success" && "bg-chart-3", tone === "warning" && "bg-chart-4")} />
      <div className="min-w-0 flex-1">
        <div className="flex items-start justify-between gap-3">
          <p className="truncate text-sm font-medium">{title}</p>
          <span className="shrink-0 text-xs text-muted-foreground">{time}</span>
        </div>
        <p className="mt-1 line-clamp-2 text-xs leading-5 text-muted-foreground">{detail}</p>
      </div>
    </div>
  );
}

function MiniStat({ label, value }: { label: string; value: string | number }) {
  return (
    <div className="rounded-md bg-background/50 px-2 py-2">
      <p className="text-[0.7rem] text-muted-foreground">{label}</p>
      <p className="mt-1 font-semibold tabular-nums">{value}</p>
    </div>
  );
}

function EmptyState({ text }: { text: string }) {
  return (
    <p className="rounded-lg border border-dashed border-border/70 p-4 text-sm leading-6 text-muted-foreground">
      {text}
    </p>
  );
}

function getAgentStatus(job: GenerationJob | null) {
  if (job?.status === "failed") {
    return {
      status: "failed",
      label: "Failed",
      icon: AlertTriangle,
      className: "border-destructive/30 bg-destructive/10 text-destructive",
      pulse: false,
    };
  }
  if (job?.status === "running" || (job && job.progress > 0 && job.progress < 100)) {
    return {
      status: "running",
      label: "Running",
      icon: Radio,
      className: "border-accent/30 bg-accent/10 text-accent",
      pulse: true,
    };
  }
  return {
    status: "completed",
    label: "Idle",
    icon: Play,
    className: "border-primary/30 bg-primary/10 text-primary",
    pulse: false,
  };
}

function getActiveCampaigns(campaigns: Campaign[]) {
  const active = campaigns.filter((campaign) => !["completed", "archived", "failed"].includes(campaign.status));
  return (active.length ? active : campaigns).slice(0, 4);
}

function getUpcomingFollowUps(leads: CrmLead[]) {
  const now = Date.now();
  const soon = now + 14 * 24 * 60 * 60 * 1000;
  return leads
    .filter((lead) => {
      if (!lead.next_follow_up_at) return false;
      const time = new Date(lead.next_follow_up_at).getTime();
      return time <= soon && !["won", "lost", "archived"].includes(lead.crm_stage);
    })
    .sort((a, b) => new Date(a.next_follow_up_at ?? 0).getTime() - new Date(b.next_follow_up_at ?? 0).getTime())
    .slice(0, 5);
}

function getHotLeads(leads: CrmLead[]) {
  const hotStages = new Set(["replied", "interested", "meeting_scheduled"]);
  return leads
    .filter((lead) => hotStages.has(lead.crm_stage))
    .sort((a, b) => new Date(b.updated_at).getTime() - new Date(a.updated_at).getTime())
    .slice(0, 5);
}

function getPipelineCards(crm: CrmLeadList | null) {
  const counts = crm?.stage_counts;
  const total = Math.max(crm?.total ?? 0, 1);
  return [
    { label: "New Leads", value: counts?.new ?? 0, icon: Users },
    { label: "Qualified", value: counts?.qualified ?? 0, icon: CheckCircle2 },
    { label: "Meetings", value: counts?.meeting_scheduled ?? 0, icon: CalendarClock },
    { label: "Won", value: counts?.won ?? 0, icon: Target },
  ].map((item) => ({ ...item, progress: ((item.value as number) / total) * 100 }));
}

function buildActivityStream(events: Analytics["recent_activity"], outreach: Outreach[]) {
  const emailRows = outreach
    .filter((item) => item.sent_at || item.opened_at || item.replied_at || item.status !== "draft")
    .slice(0, 5)
    .map((item) => ({
      id: `email-${item.id}`,
      title: item.status === "replied" ? "Email reply received" : item.status === "opened" ? "Email opened" : "Email activity",
      detail: item.subject_line || item.personalized_first_line || "Outreach sequence updated",
      time: relativeDateLabel(item.replied_at ?? item.opened_at ?? item.sent_at ?? item.created_at),
      tone: item.status === "replied" ? "success" as const : "normal" as const,
    }));
  const callRows = events
    .filter((item) => /call|sdr/i.test(item.type))
    .slice(0, 3)
    .map((item) => ({
      id: `call-${item.id}`,
      title: statusLabel(item.type),
      detail: activitySummary(item.metadata),
      time: relativeDateLabel(item.created_at),
      tone: "warning" as const,
    }));
  return [...callRows, ...emailRows];
}

function getRecommendations({
  analytics,
  agent,
  hotLeadCount,
  followUpCount,
  activeCampaignCount,
}: {
  analytics: Analytics | null;
  agent: ReturnType<typeof getAgentStatus>;
  hotLeadCount: number;
  followUpCount: number;
  activeCampaignCount: number;
}) {
  const items = [];
  if (agent.status === "failed") {
    items.push({
      title: "Resolve failed automation",
      detail: "The latest agent run failed. Review the pipeline error before launching another batch.",
      icon: AlertTriangle,
      className: "text-destructive",
    });
  }
  if ((analytics?.conversion_rate ?? 0) < 5 && (analytics?.emails_sent ?? 0) > 20) {
    items.push({
      title: "Conversion rate needs attention",
      detail: "Replies are below target. Test a new subject line or tighten lead qualification before the next send.",
      icon: Zap,
      className: "text-chart-3",
    });
  }
  if (hotLeadCount) {
    items.push({
      title: "Prioritize hot lead outreach",
      detail: `${hotLeadCount} leads have replied, shown interest, or reached meeting stage. Follow up while intent is fresh.`,
      icon: Flame,
      className: "text-chart-4",
    });
  }
  if (followUpCount) {
    items.push({
      title: "Follow-ups are due",
      detail: `${followUpCount} scheduled CRM actions are due within the next 14 days.`,
      icon: CalendarClock,
      className: "text-primary",
    });
  }
  if (!activeCampaignCount) {
    items.push({
      title: "No active campaign in motion",
      detail: "Launch a focused campaign to keep the lead pipeline producing fresh opportunities.",
      icon: Rocket,
      className: "text-accent",
    });
  }
  return items.slice(0, 4);
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

function clamp(value: number) {
  return Math.max(0, Math.min(100, value));
}

function DashboardSkeleton() {
  return (
    <div className="flex flex-col gap-6">
      <div className="rounded-lg border border-border/70 bg-card/80 p-5">
        <Skeleton className="h-6 w-52" />
        <Skeleton className="mt-4 h-9 w-80 max-w-full" />
        <div className="mt-5 grid gap-3 md:grid-cols-4">
          {Array.from({ length: 4 }).map((_, index) => (
            <Skeleton key={index} className="h-28 rounded-lg" />
          ))}
        </div>
      </div>
      <div className="grid gap-4 xl:grid-cols-2">
        <Skeleton className="h-72 rounded-lg" />
        <Skeleton className="h-72 rounded-lg" />
      </div>
    </div>
  );
}
