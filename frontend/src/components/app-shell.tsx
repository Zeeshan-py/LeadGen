"use client";

/**
 * LeadForge application shell.
 *
 * Provides persistent navigation, responsive sidebar behavior, and the shared
 * page frame used by the platform and AI SDR routes.
 */

import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  BarChart3,
  Bot,
  BrainCircuit,
  ContactRound,
  CreditCard,
  Gauge,
  Home,
  Layers3,
  LockKeyhole,
  LogOut,
  Mail,
  Settings,
  Sparkles,
  Users,
} from "lucide-react";
import type { LucideIcon } from "lucide-react";
import { motion } from "framer-motion";

import {
  Sidebar,
  SidebarContent,
  SidebarFooter,
  SidebarGroup,
  SidebarGroupContent,
  SidebarHeader,
  SidebarInset,
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
  SidebarProvider,
  SidebarSeparator,
  SidebarTrigger,
} from "@/components/ui/sidebar";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { PlanBadge, UpgradeModal } from "@/components/subscription-gate";
import { useAuth } from "@/lib/auth";
import { useSubscription } from "@/lib/subscription";
import type { FeatureKey } from "@/lib/types";
import { cn } from "@/lib/utils";

const nav = [
  { href: "/dashboard", label: "Dashboard", icon: Home },
  { href: "/lead-generator", label: "Lead Generator", icon: Sparkles },
  { href: "/ai-sdr", label: "AI SDR", icon: Bot, feature: "ai_sdr" },
  { href: "/leads", label: "Leads", icon: Users },
  { href: "/crm", label: "CRM", icon: ContactRound, feature: "crm" },
  { href: "/campaigns", label: "Campaigns", icon: Layers3, feature: "campaigns" },
  { href: "/outreach", label: "Outreach", icon: Mail, feature: "outreach" },
  { href: "/analytics", label: "Analytics", icon: BarChart3, feature: "analytics" },
  { href: "/billing", label: "Billing", icon: CreditCard },
  { href: "/settings", label: "Settings", icon: Settings },
] satisfies Array<{ href: string; label: string; icon: LucideIcon; feature?: FeatureKey }>;

export function AppShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const { user, logout } = useAuth();
  const subscription = useSubscription();
  const normalizedPath = pathname === "/" ? pathname : pathname.replace(/\/+$/, "");
  const current = nav.find((item) => item.href === normalizedPath) ?? nav[0];

  return (
    <SidebarProvider>
      <Sidebar collapsible="icon" className="border-sidebar-border/80">
        <SidebarHeader className="p-4">
          <div className="flex items-center gap-3 rounded-lg border border-sidebar-border/70 bg-sidebar-accent/45 p-3">
            <div className="grid size-10 place-items-center rounded-lg bg-primary text-primary-foreground">
              <BrainCircuit />
            </div>
            <div className="min-w-0">
              <p className="truncate text-sm font-semibold">LeadForge AI</p>
              <p className="truncate text-xs text-sidebar-foreground/60">Private workspace</p>
            </div>
          </div>
        </SidebarHeader>
        <SidebarContent>
          <SidebarGroup>
            <SidebarGroupContent>
              <SidebarMenu>
                {nav.map((item) => {
                  const Icon = item.icon;
                  const active = normalizedPath === item.href;
                  const locked = Boolean(item.feature && !subscription.loading && !subscription.hasFeature(item.feature));
                  return (
                    <SidebarMenuItem key={item.href}>
                      {locked && item.feature ? (
                        <SidebarMenuButton
                          tooltip={`${item.label} requires ${subscription.requiredPlanFor(item.feature)}`}
                          isActive={active}
                          aria-label={`${item.label} locked`}
                          onClick={() => subscription.openUpgrade(item.feature)}
                        >
                          <Icon />
                          <span>{item.label}</span>
                          <LockKeyhole className="ml-auto size-3.5 text-muted-foreground" />
                        </SidebarMenuButton>
                      ) : (
                        <SidebarMenuButton asChild tooltip={item.label} isActive={active}>
                          <Link href={item.href}>
                            <Icon />
                            <span>{item.label}</span>
                            {item.feature ? (
                              <span className="ml-auto">
                                <PlanBadge feature={item.feature} />
                              </span>
                            ) : null}
                          </Link>
                        </SidebarMenuButton>
                      )}
                    </SidebarMenuItem>
                  );
                })}
              </SidebarMenu>
            </SidebarGroupContent>
          </SidebarGroup>
        </SidebarContent>
        <SidebarSeparator />
        <SidebarFooter className="p-4">
          <div className="rounded-lg border border-sidebar-border/70 bg-sidebar-accent/35 p-3">
            <div className="flex items-center gap-2">
              <Bot className="size-4 text-primary" />
              <span className="text-xs font-medium">Automation ready</span>
            </div>
            <p className="mt-2 text-xs leading-5 text-sidebar-foreground/60">
              Leads, outreach, CRM, and SDR workflows stay scoped to this account.
            </p>
          </div>
        </SidebarFooter>
      </Sidebar>
      <SidebarInset className="min-h-svh overflow-hidden">
        <header className="sticky top-0 z-20 flex h-16 items-center justify-between border-b border-border/70 bg-background/80 px-4 backdrop-blur-xl md:px-6">
          <div className="flex items-center gap-3">
            <SidebarTrigger />
            <div>
              <p className="text-sm text-muted-foreground">LeadForge AI</p>
              <h1 className="text-lg font-semibold tracking-normal">{current.label}</h1>
            </div>
          </div>
          <div className="flex items-center gap-3">
            <Badge variant="outline" className="hidden border-primary/30 bg-primary/10 text-primary sm:inline-flex">
              {subscription.access?.plan_name ?? (user?.is_admin ? "Admin" : "Private")}
            </Badge>
            <div className="hidden items-center gap-2 rounded-lg border border-border/70 bg-card/70 px-3 py-2 text-xs text-muted-foreground md:flex">
              <Gauge className="size-4 text-accent" />
              <span className="max-w-44 truncate">{user?.email}</span>
            </div>
            <Button
              variant="outline"
              size="icon"
              aria-label="Log out"
              title="Log out"
              onClick={() => {
                logout();
              }}
            >
              <LogOut />
            </Button>
          </div>
        </header>
        <motion.main
          key={pathname}
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.25, ease: "easeOut" }}
          className={cn("score-grid min-h-[calc(100svh-4rem)] p-4 md:p-6")}
        >
          {children}
        </motion.main>
      </SidebarInset>
      <UpgradeModal />
    </SidebarProvider>
  );
}
