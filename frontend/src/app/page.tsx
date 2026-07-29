import Link from "next/link";
import {
  ArrowRight,
  BarChart3,
  Bot,
  BrainCircuit,
  CheckCircle2,
  LockKeyhole,
  Mail,
  ShieldCheck,
  Sparkles,
  Users,
} from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";

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

export default function LandingPage() {
  return (
    <main className="score-grid min-h-svh">
      <header className="mx-auto flex w-full max-w-7xl items-center justify-between px-4 py-5 md:px-6">
        <Link href="/" className="flex items-center gap-3">
          <div className="grid size-10 place-items-center rounded-lg bg-primary text-primary-foreground">
            <BrainCircuit className="size-5" />
          </div>
          <div>
            <p className="text-sm font-semibold">LeadForge AI</p>
            <p className="text-xs text-muted-foreground">Private workspace SaaS</p>
          </div>
        </Link>
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
            One account. One private workspace.
          </Badge>
          <h1 className="mt-5 text-4xl font-semibold tracking-normal md:text-6xl">
            LeadForge AI
          </h1>
          <p className="mt-5 max-w-2xl text-base leading-7 text-muted-foreground md:text-lg">
            Find leads, manage CRM follow-ups, prepare outreach, track analytics, and run AI SDR workflows inside a workspace only your account can access.
          </p>
          <div className="mt-7 flex flex-wrap gap-3">
            <Button asChild size="lg">
              <Link href="/signup">
                Create Workspace
                <ArrowRight data-icon="inline-end" />
              </Link>
            </Button>
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

      <footer className="mx-auto flex w-full max-w-7xl flex-wrap items-center justify-between gap-3 border-t border-border/70 px-4 py-6 text-sm text-muted-foreground md:px-6">
        <p>LeadForge AI</p>
        <nav className="flex flex-wrap items-center gap-4">
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
