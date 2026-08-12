"use client";

import { useEffect } from "react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { CreditCard, LockKeyhole } from "lucide-react";

import { AppShell } from "@/components/app-shell";
import { BrandLogo } from "@/components/brand-logo";
import { Button } from "@/components/ui/button";
import { useAuth, type AuthUser } from "@/lib/auth";
import { SubscriptionProvider, useSubscription } from "@/lib/subscription";

const publicRoutes = new Set([
  "/",
  "/login",
  "/signup",
  "/forgot-password",
  "/reset-password",
  "/privacy",
  "/terms",
  "/refund",
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
          <BrandLogo className="mx-auto size-12" />
          <p className="text-sm text-muted-foreground">Opening LeadForge</p>
        </div>
      </div>
    );
  }

  return (
    <SubscriptionProvider>
      <PaidWorkspaceGate user={user}>{children}</PaidWorkspaceGate>
    </SubscriptionProvider>
  );
}

function PaidWorkspaceGate({
  children,
  user,
}: {
  children: React.ReactNode;
  user: AuthUser;
}) {
  const subscription = useSubscription();
  const { logout } = useAuth();

  if (subscription.loading) {
    return (
      <div className="grid min-h-svh place-items-center bg-background px-4">
        <div className="grid gap-4 text-center">
          <BrandLogo className="mx-auto size-12" />
          <p className="text-sm text-muted-foreground">Checking workspace access</p>
        </div>
      </div>
    );
  }

  if (user.is_admin || subscription.access?.access_active) {
    return <AppShell>{children}</AppShell>;
  }

  return (
    <main className="score-grid grid min-h-svh place-items-center px-4 py-10">
      <section className="glass-panel w-full max-w-xl rounded-lg border border-border/70 p-6 text-center shadow-2xl shadow-black/20 md:p-8">
        <BrandLogo className="mx-auto size-14 rounded-xl" />
        <div className="mx-auto mt-6 grid size-12 place-items-center rounded-lg bg-primary/10 text-primary">
          <LockKeyhole className="size-6" />
        </div>
        <h1 className="mt-5 text-2xl font-semibold tracking-normal">Choose a paid plan to continue</h1>
        <p className="mx-auto mt-3 max-w-md text-sm leading-6 text-muted-foreground">
          LeadForge AI requires an active Basic, Agent, or Agency subscription before opening the private workspace.
        </p>
        <div className="mt-6 flex flex-col-reverse gap-2 sm:flex-row sm:justify-center">
          <Button variant="outline" onClick={() => void logout()}>
            Log out
          </Button>
          <Button asChild>
            <Link href="/pricing">
              <CreditCard />
              View plans
            </Link>
          </Button>
        </div>
      </section>
    </main>
  );
}
