"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { initializePaddle, type Environments, type Paddle, type PaddleEventData } from "@paddle/paddle-js";
import { ArrowRight, Check, CreditCard, Loader2 } from "lucide-react";
import { toast } from "sonner";

import { BrandLogo } from "@/components/brand-logo";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { createPaddleCheckout, getBillingPlans } from "@/lib/api";
import { trackEvent } from "@/lib/analytics";
import { useAuth } from "@/lib/auth";
import type { BillingPlan, PaddleCheckoutSession } from "@/lib/types";
import { cn } from "@/lib/utils";

let paddlePromise: Promise<Paddle | undefined> | null = null;
let paddleInstanceKey = "";

export function PricingCheckout() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const { user, loading } = useAuth();
  const [plans, setPlans] = useState<BillingPlan[]>([]);
  const [environment, setEnvironment] = useState<"sandbox" | "production">("sandbox");
  const [plansLoading, setPlansLoading] = useState(true);
  const [checkoutPlan, setCheckoutPlan] = useState("");
  const checkoutCompletedRef = useRef(false);
  const cancelUrlRef = useRef("/billing/cancel");

  useEffect(() => {
    let mounted = true;
    getBillingPlans()
      .then((payload) => {
        if (!mounted) return;
        setPlans(payload.plans);
        setEnvironment(payload.environment);
      })
      .catch((error) => toast.error(error instanceof Error ? error.message : "Unable to load billing plans"))
      .finally(() => {
        if (mounted) setPlansLoading(false);
      });
    return () => {
      mounted = false;
    };
  }, []);

  const selectedPlan = useMemo(
    () => plans.find((plan) => plan.key === searchParams.get("plan")),
    [plans, searchParams],
  );

  const handlePaddleEvent = useCallback((event: PaddleEventData) => {
    if (event.name === "checkout.completed") {
      checkoutCompletedRef.current = true;
      trackEvent("purchase", { provider: "paddle", environment });
      router.push("/billing/success");
    }
    if (event.name === "checkout.closed" && !checkoutCompletedRef.current) {
      router.push(asAppPath(cancelUrlRef.current));
    }
    if (event.name === "checkout.error") {
      trackEvent("exception", { description: "Paddle checkout error", fatal: false });
    }
  }, [environment, router]);

  const paddleInstance = useCallback(async (session: PaddleCheckoutSession) => {
    const key = `${session.environment}:${session.client_token}`;
    if (!session.client_token) {
      throw new Error("Paddle checkout client token is not configured");
    }
    if (!paddlePromise || paddleInstanceKey !== key) {
      paddleInstanceKey = key;
      paddlePromise = initializePaddle({
        environment: session.environment as Environments,
        token: session.client_token,
        eventCallback: handlePaddleEvent,
      });
    }
    const paddle = await paddlePromise;
    if (!paddle) {
      throw new Error("Paddle checkout failed to initialize");
    }
    return paddle;
  }, [handlePaddleEvent]);

  const openCheckout = useCallback(async (plan: BillingPlan) => {
    if (!user) {
      router.push(`/login?next=${encodeURIComponent(`/pricing?plan=${plan.key}`)}`);
      return;
    }
    if (!plan.configured) {
      toast.error("This plan is not configured in Paddle yet");
      return;
    }
    setCheckoutPlan(plan.key);
    try {
      checkoutCompletedRef.current = false;
      const session = await createPaddleCheckout({ plan_key: plan.key });
      cancelUrlRef.current = session.cancel_url;
      setEnvironment(session.environment);
      const paddle = await paddleInstance(session);
      const customer = session.customer.paddle_customer_id
        ? { id: session.customer.paddle_customer_id }
        : { email: session.customer.email || user.email };
      trackEvent("begin_checkout", {
        plan: session.plan_key,
        price_id: session.price_id,
        environment: session.environment,
      });
      paddle.Checkout.open({
        items: [{ priceId: session.price_id, quantity: session.quantity }],
        customer,
        customData: session.custom_data,
        settings: {
          displayMode: "overlay",
          theme: "dark",
          successUrl: session.success_url,
          showAddDiscounts: true,
          allowLogout: false,
          variant: "one-page",
        },
      });
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Unable to open Paddle checkout");
    } finally {
      setCheckoutPlan("");
    }
  }, [paddleInstance, router, user]);

  useEffect(() => {
    if (selectedPlan && user && !loading) {
      void openCheckout(selectedPlan);
    }
  }, [selectedPlan, user, loading, openCheckout]);

  return (
    <main className="min-h-svh bg-background text-foreground">
      <header className="border-b border-border/70 bg-background/90 backdrop-blur-xl">
        <div className="mx-auto flex max-w-7xl items-center justify-between px-4 py-4 md:px-6">
          <Link href="/" className="flex items-center gap-3" aria-label="LeadForge AI home">
            <BrandLogo />
            <span className="font-semibold">LeadForge AI</span>
          </Link>
          <nav aria-label="Primary" className="hidden items-center gap-1 text-sm text-muted-foreground md:flex">
            <Link className="rounded-md px-3 py-2 hover:bg-secondary hover:text-foreground" href="/features">
              Features
            </Link>
            <Link className="rounded-md px-3 py-2 hover:bg-secondary hover:text-foreground" href="/contact">
              Contact
            </Link>
            <Link className="rounded-md px-3 py-2 hover:bg-secondary hover:text-foreground" href="/login">
              Login
            </Link>
          </nav>
        </div>
      </header>

      <section className="mx-auto grid max-w-7xl gap-8 px-4 py-12 md:px-6 lg:py-16">
        <div className="max-w-3xl">
          <Badge variant="outline" className="border-primary/30 bg-primary/10 text-primary">
            Paddle Billing {environment === "sandbox" ? "Sandbox" : "Production"}
          </Badge>
          <h1 className="mt-5 text-4xl font-semibold tracking-normal md:text-5xl">
            Subscribe to LeadForge AI
          </h1>
          <p className="mt-4 text-lg leading-8 text-muted-foreground">
            Choose a monthly workspace plan for AI lead generation, CRM, Gmail outreach,
            analytics, Twilio calling, and AI SDR workflows.
          </p>
        </div>

        {plansLoading ? (
          <div className="flex min-h-64 items-center justify-center rounded-lg border border-border/70 bg-card/60">
            <Loader2 className="size-6 animate-spin text-primary" />
          </div>
        ) : (
          <div className="grid gap-4 lg:grid-cols-3">
            {plans.map((plan) => {
              const busy = checkoutPlan === plan.key;
              return (
                <article
                  key={plan.key}
                  className={cn(
                    "flex min-h-[34rem] flex-col rounded-lg border bg-card/80 p-6 shadow-sm",
                    plan.highlighted ? "border-primary/60 shadow-primary/10" : "border-border/70",
                  )}
                >
                  <div className="flex items-start justify-between gap-4">
                    <div>
                      <h2 className="text-2xl font-semibold tracking-normal">{plan.name}</h2>
                      <p className="mt-2 min-h-14 text-sm leading-6 text-muted-foreground">{plan.description}</p>
                    </div>
                    {plan.highlighted ? <Badge className="bg-primary text-primary-foreground">Popular</Badge> : null}
                  </div>

                  <div className="mt-8 flex items-end gap-2">
                    <span className="text-4xl font-semibold tracking-normal">{formatMoney(plan.amount, plan.currency_code)}</span>
                    <span className="pb-1 text-sm text-muted-foreground">/{plan.interval}</span>
                  </div>

                  <ul className="mt-8 grid gap-3 text-sm text-muted-foreground">
                    {plan.features.map((feature) => (
                      <li key={feature} className="flex gap-3">
                        <Check className="mt-0.5 size-4 shrink-0 text-primary" />
                        <span>{feature}</span>
                      </li>
                    ))}
                  </ul>

                  <Button className="mt-auto w-full" disabled={busy || loading || !plan.configured} onClick={() => openCheckout(plan)}>
                    {busy ? <Loader2 className="animate-spin" /> : <CreditCard />}
                    {!plan.configured ? "Plan unavailable" : user ? "Open checkout" : "Login to subscribe"}
                    <ArrowRight />
                  </Button>
                </article>
              );
            })}
          </div>
        )}
      </section>
    </main>
  );
}

function asAppPath(url: string) {
  try {
    const parsed = new URL(url);
    return `${parsed.pathname}${parsed.search}${parsed.hash}`;
  } catch {
    return url || "/billing/cancel";
  }
}

function formatMoney(amount: string, currencyCode: string) {
  const value = Number.parseInt(amount || "0", 10) / 100;
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: currencyCode || "USD",
    maximumFractionDigits: value % 1 === 0 ? 0 : 2,
  }).format(value);
}
