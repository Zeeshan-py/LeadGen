import Link from "next/link";
import {
  ArrowRight,
  BarChart3,
  Bot,
  BrainCircuit,
  Building2,
  CheckCircle2,
  FileText,
  Globe2,
  Mail,
  MapPinned,
  ServerCog,
  ShieldCheck,
  Sparkles,
  Target,
  Users,
  Workflow,
} from "lucide-react";
import type { LucideIcon } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

type InfoCardItem = {
  title: string;
  detail: string;
  icon: LucideIcon;
};

const projectFacts = [
  { label: "Product type", value: "Lead generation and outreach platform" },
  { label: "Primary audience", value: "Founders, agencies, and SDR teams" },
  { label: "Deployment", value: "Dockerized FastAPI and Next.js app" },
  { label: "Database", value: "PostgreSQL with CRM activity history" },
];

const outcomes = [
  {
    title: "Find target businesses",
    detail: "Search by country, city, and niche, then collect structured business records from local markets.",
    icon: MapPinned,
  },
  {
    title: "Enrich every lead",
    detail: "Review websites, extract contact details, identify social profiles, and score the commercial opportunity.",
    icon: Sparkles,
  },
  {
    title: "Run outreach",
    detail: "Generate cold emails and follow-ups, send through Gmail, sync replies, and track open or bounce status.",
    icon: Mail,
  },
  {
    title: "Manage the pipeline",
    detail: "Move leads through CRM stages, assign follow-ups, record activity, and inspect campaign performance.",
    icon: Workflow,
  },
] satisfies InfoCardItem[];

const workflow = [
  {
    step: "01",
    title: "Select a market",
    detail: "Choose the geography, industry, website requirement, and lead volume.",
  },
  {
    step: "02",
    title: "Collect prospects",
    detail: "The system gathers business names, locations, websites, phones, and public profile links.",
  },
  {
    step: "03",
    title: "Qualify accounts",
    detail: "Each lead is checked for contact quality, website gaps, and outreach readiness.",
  },
  {
    step: "04",
    title: "Start outreach",
    detail: "Use generated email drafts, manual SDR calls, campaign queues, and CRM follow-up dates.",
  },
  {
    step: "05",
    title: "Measure results",
    detail: "Analytics separates lead trends, funnel movement, email performance, source quality, and ROI.",
  },
];

const modules = [
  {
    title: "Lead Generator",
    href: "/lead-generator",
    detail: "Creates new prospect lists for a selected market and saves enriched records.",
    icon: Target,
  },
  {
    title: "AI SDR",
    href: "/ai-sdr",
    detail: "Prepares call workflows and supports SDR calling activity from the same workspace.",
    icon: Bot,
  },
  {
    title: "Leads",
    href: "/leads",
    detail: "Search, filter, edit, export, and call individual leads with their source details intact.",
    icon: Building2,
  },
  {
    title: "CRM",
    href: "/crm",
    detail: "Tracks ownership, notes, stages, follow-ups, meetings, won deals, and lost opportunities.",
    icon: Users,
  },
  {
    title: "Campaigns",
    href: "/campaigns",
    detail: "Keeps generated lead batches organized and exportable by market or campaign.",
    icon: FileText,
  },
  {
    title: "Outreach",
    href: "/outreach",
    detail: "Manages generated emails, follow-up variants, sending, reply sync, and Gmail status.",
    icon: Mail,
  },
  {
    title: "Analytics",
    href: "/analytics",
    detail: "Shows funnel, source, geography, campaign, email, call, revenue, and forecasting views.",
    icon: BarChart3,
  },
  {
    title: "Settings",
    href: "/settings",
    detail: "Stores API keys, Google Sheets setup, Gmail configuration, and operating defaults.",
    icon: ServerCog,
  },
] satisfies Array<InfoCardItem & { href: string }>;

export default function DashboardHome() {
  return (
    <div className="mx-auto flex w-full max-w-7xl flex-col gap-5">
      <section className="grid gap-5 xl:grid-cols-[1.2fr_0.8fr]">
        <div className="glass-panel rounded-lg p-5 md:p-6">
          <div className="flex flex-wrap items-center gap-2">
            <Badge variant="outline" className="border-primary/30 bg-primary/10 text-primary">
              Project Brief
            </Badge>
            <Badge variant="outline" className="border-border bg-secondary/40 text-muted-foreground">
              Production SaaS Workspace
            </Badge>
          </div>

          <div className="mt-6 max-w-4xl">
            <p className="text-sm font-medium text-primary">LeadForge AI</p>
            <h2 className="mt-2 text-3xl font-semibold tracking-normal md:text-4xl">
              A single workspace for finding leads, preparing outreach, and managing the sales pipeline.
            </h2>
            <p className="mt-4 max-w-3xl text-base leading-7 text-muted-foreground">
              LeadForge AI is built for teams that need a repeatable way to turn market research into qualified prospects. It combines lead discovery, website enrichment, email outreach, CRM follow-up, SDR calling support, and analytics in one system.
            </p>
          </div>

          <div className="mt-6 flex flex-wrap gap-2">
            <Button asChild>
              <Link href="/lead-generator">
                Start Lead Generation
                <ArrowRight data-icon="inline-end" />
              </Link>
            </Button>
            <Button asChild variant="outline">
              <Link href="/analytics">
                View Analytics
                <BarChart3 data-icon="inline-start" />
              </Link>
            </Button>
          </div>
        </div>

        <Card className="glass-panel">
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-base">
              <ShieldCheck className="size-5 text-primary" />
              Project Snapshot
            </CardTitle>
          </CardHeader>
          <CardContent className="grid gap-3">
            {projectFacts.map((fact) => (
              <div key={fact.label} className="rounded-lg border border-border/70 bg-secondary/30 p-3">
                <p className="text-xs text-muted-foreground">{fact.label}</p>
                <p className="mt-1 text-sm font-medium leading-5">{fact.value}</p>
              </div>
            ))}
          </CardContent>
        </Card>
      </section>

      <section className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        {outcomes.map((item) => (
          <OverviewCard key={item.title} item={item} />
        ))}
      </section>

      <section className="grid gap-5 xl:grid-cols-[0.95fr_1.05fr]">
        <Card className="glass-panel">
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-base">
              <Workflow className="size-5 text-primary" />
              Operating Workflow
            </CardTitle>
          </CardHeader>
          <CardContent className="grid gap-3">
            {workflow.map((item) => (
              <div key={item.step} className="grid gap-3 rounded-lg border border-border/70 bg-secondary/30 p-3 sm:grid-cols-[52px_1fr]">
                <div className="grid size-10 place-items-center rounded-lg bg-background/70 text-sm font-semibold text-primary">
                  {item.step}
                </div>
                <div>
                  <p className="text-sm font-medium">{item.title}</p>
                  <p className="mt-1 text-sm leading-6 text-muted-foreground">{item.detail}</p>
                </div>
              </div>
            ))}
          </CardContent>
        </Card>

        <Card className="glass-panel">
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-base">
              <BrainCircuit className="size-5 text-primary" />
              What It Replaces
            </CardTitle>
          </CardHeader>
          <CardContent className="grid gap-4">
            <p className="text-sm leading-6 text-muted-foreground">
              The project reduces the need for separate scraping scripts, spreadsheets, manual website checks, disconnected Gmail tracking, CRM notes, and one-off reporting files. The important work stays tied to the same lead record from discovery through follow-up.
            </p>
            <div className="grid gap-3 md:grid-cols-2">
              <ReplaceItem title="Manual research" detail="Market selection, website review, contact discovery, and opportunity scoring are handled as one flow." />
              <ReplaceItem title="Scattered outreach" detail="Email drafts, send status, replies, CRM stages, and follow-up dates stay connected." />
              <ReplaceItem title="Disconnected reporting" detail="Analytics reads from the same lead, campaign, outreach, and CRM data model." />
              <ReplaceItem title="Deployment friction" detail="The production app is shipped as a Docker image for Railway or any container host." />
            </div>
          </CardContent>
        </Card>
      </section>

      <section>
        <Card className="glass-panel">
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-base">
              <Globe2 className="size-5 text-primary" />
              Product Modules
            </CardTitle>
          </CardHeader>
          <CardContent className="grid gap-3 md:grid-cols-2">
            {modules.map((item) => (
              <Link
                key={item.title}
                href={item.href}
                className="group rounded-lg border border-border/70 bg-secondary/30 p-4 transition-colors hover:border-primary/35 hover:bg-primary/10"
              >
                <div className="flex items-start justify-between gap-3">
                  <div className="flex min-w-0 items-start gap-3">
                    <div className="grid size-9 shrink-0 place-items-center rounded-lg bg-background/70 text-primary">
                      <item.icon className="size-4" />
                    </div>
                    <div>
                      <p className="text-sm font-medium">{item.title}</p>
                      <p className="mt-1 text-xs leading-5 text-muted-foreground">{item.detail}</p>
                    </div>
                  </div>
                  <ArrowRight className="mt-1 size-4 shrink-0 text-muted-foreground transition-transform group-hover:translate-x-0.5 group-hover:text-primary" />
                </div>
              </Link>
            ))}
          </CardContent>
        </Card>
      </section>
    </div>
  );
}

function OverviewCard({ item }: { item: InfoCardItem }) {
  const Icon = item.icon;
  return (
    <Card className="glass-panel">
      <CardContent className="p-4">
        <div className="grid size-10 place-items-center rounded-lg bg-primary/10 text-primary">
          <Icon className="size-5" />
        </div>
        <p className="mt-4 text-sm font-medium">{item.title}</p>
        <p className="mt-2 text-sm leading-6 text-muted-foreground">{item.detail}</p>
      </CardContent>
    </Card>
  );
}

function ReplaceItem({ title, detail }: { title: string; detail: string }) {
  return (
    <div className="rounded-lg border border-border/70 bg-secondary/30 p-3">
      <div className="flex items-center gap-2">
        <CheckCircle2 className="size-4 text-primary" />
        <p className="text-sm font-medium">{title}</p>
      </div>
      <p className="mt-2 text-sm leading-6 text-muted-foreground">{detail}</p>
    </div>
  );
}
