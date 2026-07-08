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
  Gauge,
  Home,
  Layers3,
  Mail,
  Settings,
  Sparkles,
  Users,
} from "lucide-react";
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
import { cn } from "@/lib/utils";

const nav = [
  { href: "/", label: "Dashboard", icon: Home },
  { href: "/lead-generator", label: "Lead Generator", icon: Sparkles },
  { href: "/ai-sdr", label: "AI SDR", icon: Bot },
  { href: "/leads", label: "Leads", icon: Users },
  { href: "/crm", label: "CRM", icon: ContactRound },
  { href: "/campaigns", label: "Campaigns", icon: Layers3 },
  { href: "/outreach", label: "Outreach", icon: Mail },
  { href: "/analytics", label: "Analytics", icon: BarChart3 },
  { href: "/settings", label: "Settings", icon: Settings },
];

export function AppShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
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
              <p className="truncate text-xs text-sidebar-foreground/60">Internal command center</p>
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
                  return (
                    <SidebarMenuItem key={item.href}>
                      <SidebarMenuButton asChild tooltip={item.label} isActive={active}>
                        <Link href={item.href}>
                          <Icon />
                          <span>{item.label}</span>
                        </Link>
                      </SidebarMenuButton>
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
              Apify, Gemini, Gmail, Sheets, and Postgres work from one console.
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
              Live pipeline
            </Badge>
            <div className="hidden items-center gap-2 rounded-lg border border-border/70 bg-card/70 px-3 py-2 text-xs text-muted-foreground md:flex">
              <Gauge className="size-4 text-accent" />
              Single-user internal system
            </div>
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
    </SidebarProvider>
  );
}
