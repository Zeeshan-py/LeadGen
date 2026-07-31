"use client";

import { useEffect } from "react";
import { usePathname, useRouter } from "next/navigation";
import { BrainCircuit } from "lucide-react";

import { AppShell } from "@/components/app-shell";
import { useAuth } from "@/lib/auth";
import { SubscriptionProvider } from "@/lib/subscription";

const publicRoutes = new Set([
  "/",
  "/login",
  "/signup",
  "/forgot-password",
  "/reset-password",
  "/privacy",
  "/terms",
  "/contact",
  "/about",
  "/features",
  "/features/lead-generator",
  "/features/crm",
  "/features/outreach",
  "/features/ai-sdr",
  "/features/analytics",
  "/pricing",
]);
const authRoutes = new Set(["/login", "/signup", "/forgot-password", "/reset-password"]);

export function RouteShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const router = useRouter();
  const { user, loading } = useAuth();
  const normalizedPath = pathname === "/" ? "/" : pathname.replace(/\/+$/, "");
  const isPublic = publicRoutes.has(normalizedPath);
  const isAuthRoute = authRoutes.has(normalizedPath);

  useEffect(() => {
    if (loading) {
      return;
    }
    if (!user && !isPublic) {
      const query = typeof window !== "undefined" ? window.location.search : "";
      const next = `${pathname}${query}`;
      router.replace(`/login?next=${encodeURIComponent(next)}`);
    }
    if (user && isAuthRoute) {
      router.replace("/dashboard");
    }
  }, [isAuthRoute, isPublic, loading, pathname, router, user]);

  if (isPublic) {
    return <>{children}</>;
  }

  if (loading || !user) {
    return (
      <div className="grid min-h-svh place-items-center bg-background px-4">
        <div className="grid gap-4 text-center">
          <div className="mx-auto grid size-12 place-items-center rounded-lg bg-primary text-primary-foreground">
            <BrainCircuit className="size-6" />
          </div>
          <p className="text-sm text-muted-foreground">Opening LeadForge</p>
        </div>
      </div>
    );
  }

  return (
    <SubscriptionProvider>
      <AppShell>{children}</AppShell>
    </SubscriptionProvider>
  );
}
