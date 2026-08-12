import Link from "next/link";
import {
  ArrowRight,
  BarChart3,
  Bot,
  Building2,
  CheckCircle2,
  Database,
  LockKeyhole,
  Mail,
  PhoneCall,
  Send,
  ShieldCheck,
  Sparkles,
  Target,
  Users,
} from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { BrandLogo } from "@/components/brand-logo";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { StructuredData } from "@/components/structured-data";
import {
  createPageMetadata,
  organizationJsonLd,
  softwareApplicationJsonLd,
  websiteJsonLd,
} from "@/lib/seo";
import type { Metadata } from "next";

export const metadata: Metadata = createPageMetadata("/");

const signals = [
  { label: "Lead Generator", icon: Sparkles },
  { label: "CRM", icon: Users },
  { label: "Outreach", icon: Mail },
  { label: "Analytics", icon: BarChart3 },
  { label: "AI SDR", icon: Bot },
];

const checks = [
  "Private leads",
  "Private campaigns",
  "Private CRM",
  "Private analytics",
];

const productSteps = [
  {
    title: "Generate and qualify leads",
    description:
      "Find business prospects, enrich records, inspect website opportunities, and organize new leads into a private pipeline.",
    icon: Target,
  },
  {
    title: "Manage CRM follow-up",
    description:
      "Track stages, notes, contact details, campaign progress, and sales actions from one authenticated workspace.",
    icon: Database,
  },
  {
    title: "Automate outreach",
    description:
      "Prepare email campaigns, send through a connected Gmail account, sync replies, and keep outreach tied to each lead.",
    icon: Send,
  },
  {
    title: "Run AI SDR workflows",
    description:
      "Use connected Twilio and voice settings to support AI SDR calling workflows for qualification and follow-up.",
    icon: PhoneCall,
  },
];

const featureGroups = [
  "AI lead discovery and enrichment",
  "Private account-based CRM",
  "Gmail outreach and reply sync",
  "Google Sheets export support",
  "Campaign and analytics tracking",
  "Twilio and Cartesia voice settings",
];

const audiences = [
  {
    title: "Founders",
    description: "Turn market research into a clear lead pipeline without managing separate tools.",
  },
  {
    title: "Agencies",
    description: "Research prospects, prepare outreach, and track follow-up for client growth work.",
  },
  {
    title: "SDR teams",
    description: "Coordinate lead generation, email outreach, CRM notes, and AI calling workflows.",
  },
];

export default function LandingPage() {
  return (
    <main className="score-grid min-h-svh">
      <StructuredData data={[organizationJsonLd(), softwareApplicationJsonLd(), websiteJsonLd()]} />
      <header className="mx-auto flex w-full max-w-7xl items-center justify-between px-4 py-5 md:px-6">
        <Link href="/" className="flex items-center gap-3">
          <BrandLogo />
          <div>
            <p className="text-sm font-semibold">LeadForge AI</p>
            <p className="text-xs text-muted-foreground">Private workspace SaaS</p>
          </div>
        </Link>
        <nav aria-label="Primary" className="hidden items-center gap-1 text-sm text-muted-foreground md:flex">
          <Link className="rounded-md px-3 py-2 hover:bg-secondary hover:text-foreground" href="/features">
            Features
          </Link>
          <Link className="rounded-md px-3 py-2 hover:bg-secondary hover:text-foreground" href="/pricing">
            Pricing
          </Link>
          <Link className="rounded-md px-3 py-2 hover:bg-secondary hover:text-foreground" href="/about">
            About
          </Link>
          <Link className="rounded-md px-3 py-2 hover:bg-secondary hover:text-foreground" href="/contact">
            Contact
          </Link>
        </nav>
        <div className="flex items-center gap-2">
          <Button asChild variant="outline">
            <Link href="/login">Login</Link>
          </Button>
          <Button asChild>
            <Link href="/signup">
              Sign Up
              <ArrowRight data-icon="inline-end" />
            </Link>
          </Button>
        </div>
      </header>

      <section className="mx-auto grid min-h-[calc(100svh-5rem)] w-full max-w-7xl items-center gap-6 px-4 pb-10 md:px-6 xl:grid-cols-[1fr_520px]">
        <div className="max-w-3xl">
          <Badge variant="outline" className="border-primary/30 bg-primary/10 text-primary">
            AI-powered lead generation SaaS
          </Badge>
          <h1 className="mt-5 text-4xl font-semibold tracking-normal md:text-6xl">
            LeadForge AI
          </h1>
          <p className="mt-5 max-w-2xl text-base leading-7 text-muted-foreground md:text-lg">
            LeadForge AI helps businesses generate leads, manage CRM follow-up, automate outreach campaigns, track analytics, and operate AI SDR workflows from one secure private workspace.
          </p>
          <p className="mt-4 max-w-2xl text-sm leading-7 text-muted-foreground">
            The platform connects lead research, Gmail outreach, Google Sheets, Twilio calling, Cartesia voice settings, and AI-assisted sales workflows so teams can move from prospect discovery to follow-up without switching systems.
          </p>
          <div className="mt-7 flex flex-wrap gap-3">
            <Button asChild size="lg" variant="outline">
              <Link href="/login">
                <LockKeyhole data-icon="inline-start" />
                Login
              </Link>
            </Button>
          </div>
        </div>

        <Card className="glass-panel overflow-hidden">
          <CardContent className="p-0">
            <div className="border-b border-border/70 p-5">
              <div className="flex items-center justify-between gap-3">
                <div>
                  <p className="text-sm font-medium">Workspace Boundary</p>
                  <p className="mt-1 text-xs text-muted-foreground">Authenticated account scope</p>
                </div>
                <ShieldCheck className="size-5 text-primary" />
              </div>
            </div>
            <div className="grid gap-3 p-5">
              {signals.map((item) => (
                <div key={item.label} className="flex items-center justify-between rounded-lg border border-border/70 bg-secondary/30 p-3">
                  <div className="flex items-center gap-3">
                    <div className="grid size-9 place-items-center rounded-lg bg-background/70 text-primary">
                      <item.icon className="size-4" />
                    </div>
                    <span className="text-sm font-medium">{item.label}</span>
                  </div>
                  <CheckCircle2 className="size-4 text-primary" />
                </div>
              ))}
            </div>
            <div className="grid grid-cols-2 gap-2 border-t border-border/70 p-5">
              {checks.map((item) => (
                <div key={item} className="rounded-lg bg-background/45 px-3 py-2 text-xs text-muted-foreground">
                  {item}
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      </section>

      <section className="mx-auto w-full max-w-7xl px-4 py-12 md:px-6">
        <div className="max-w-3xl">
          <p className="text-sm font-medium text-primary">What the product does</p>
          <h2 className="mt-3 text-3xl font-semibold tracking-normal md:text-4xl">
            From prospect research to AI SDR follow-up
          </h2>
          <p className="mt-4 text-sm leading-7 text-muted-foreground md:text-base">
            LeadForge AI gives businesses a single place to discover prospects, review lead context, create outreach, send campaigns, monitor replies, manage CRM stages, and support phone-based AI SDR workflows.
          </p>
        </div>
        <div className="mt-8 grid gap-4 md:grid-cols-2 xl:grid-cols-4">
          {productSteps.map((item) => (
            <Card key={item.title} className="glass-panel">
              <CardContent className="p-5">
                <div className="grid size-10 place-items-center rounded-lg bg-primary/10 text-primary">
                  <item.icon className="size-5" />
                </div>
                <h3 className="mt-4 text-lg font-semibold">{item.title}</h3>
                <p className="mt-3 text-sm leading-6 text-muted-foreground">{item.description}</p>
              </CardContent>
            </Card>
          ))}
        </div>
      </section>

      <section className="border-y border-border/70 bg-background/35">
        <div className="mx-auto grid w-full max-w-7xl gap-8 px-4 py-12 md:px-6 lg:grid-cols-[0.9fr_1.1fr]">
          <div>
            <p className="text-sm font-medium text-primary">Features</p>
            <h2 className="mt-3 text-3xl font-semibold tracking-normal">Built for lead operations</h2>
            <p className="mt-4 text-sm leading-7 text-muted-foreground md:text-base">
              Every workflow is scoped to the signed-in user so leads, CRM data, campaigns, Gmail connections, Twilio credentials, voice settings, and analytics remain inside that account workspace.
            </p>
          </div>
          <div className="grid gap-3 sm:grid-cols-2">
            {featureGroups.map((feature) => (
              <div key={feature} className="flex items-center gap-3 rounded-lg border border-border/70 bg-background/55 px-4 py-3">
                <CheckCircle2 className="size-4 shrink-0 text-primary" />
                <span className="text-sm font-medium">{feature}</span>
              </div>
            ))}
          </div>
        </div>
      </section>

      <section className="mx-auto grid w-full max-w-7xl gap-8 px-4 py-12 md:px-6 lg:grid-cols-[1fr_1fr]">
        <div>
          <p className="text-sm font-medium text-primary">Who it is for</p>
          <h2 className="mt-3 text-3xl font-semibold tracking-normal">Teams that need focused sales automation</h2>
          <div className="mt-6 grid gap-4">
            {audiences.map((audience) => (
              <div key={audience.title} className="rounded-lg border border-border/70 bg-secondary/25 p-4">
                <div className="flex items-center gap-3">
                  <Building2 className="size-4 text-primary" />
                  <h3 className="font-semibold">{audience.title}</h3>
                </div>
                <p className="mt-2 text-sm leading-6 text-muted-foreground">{audience.description}</p>
              </div>
            ))}
          </div>
        </div>
        <div className="rounded-lg border border-border/70 bg-background/55 p-5">
          <p className="text-sm font-medium text-primary">Contact and policies</p>
          <h2 className="mt-3 text-2xl font-semibold tracking-normal">Public information for users and reviewers</h2>
          <p className="mt-4 text-sm leading-7 text-muted-foreground">
            LeadForge AI provides public access to product information, support contact details, privacy practices, and terms of service without requiring visitors to sign in.
          </p>
          <div className="mt-6 grid gap-3 sm:grid-cols-3">
            <Button asChild variant="outline">
              <Link href="/contact">Contact</Link>
            </Button>
            <Button asChild variant="outline">
              <Link href="/privacy">Privacy Policy</Link>
            </Button>
            <Button asChild variant="outline">
              <Link href="/terms">Terms of Service</Link>
            </Button>
          </div>
          <p className="mt-5 text-sm text-muted-foreground">
            Support email: <a className="text-primary hover:underline" href="mailto:support@leadforage.pro">support@leadforage.pro</a>
          </p>
        </div>
      </section>

      <footer className="mx-auto flex w-full max-w-7xl flex-wrap items-center justify-between gap-3 border-t border-border/70 px-4 py-6 text-sm text-muted-foreground md:px-6">
        <p>LeadForge AI</p>
        <nav aria-label="Footer" className="flex flex-wrap items-center gap-4">
          <Link className="hover:text-foreground" href="/features">
            Features
          </Link>
          <Link className="hover:text-foreground" href="/pricing">
            Pricing
          </Link>
          <Link className="hover:text-foreground" href="/about">
            About
          </Link>
          <Link className="hover:text-foreground" href="/privacy">
            Privacy
          </Link>
          <Link className="hover:text-foreground" href="/terms">
            Terms
          </Link>
          <Link className="hover:text-foreground" href="/contact">
            Contact
          </Link>
        </nav>
      </footer>
    </main>
  );
}
