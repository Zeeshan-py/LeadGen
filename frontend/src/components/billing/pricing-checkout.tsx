"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { initializePaddle, type Environments, type Paddle, type PaddleEventData } from "@paddle/paddle-js";
import { ArrowRight, BrainCircuit, Check, CreditCard, Loader2 } from "lucide-react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { getBillingPlans } from "@/lib/api";
import { trackEvent } from "@/lib/analytics";
import { useAuth } from "@/lib/auth";
import type { BillingPlan } from "@/lib/types";
import { cn } from "@/lib/utils";

const paddleClientToken = process.env.NEXT_PUBLIC_PADDLE_CLIENT_TOKEN?.trim() || "";
const paddleEnvironment: Environments =
  process.env.NEXT_PUBLIC_PADDLE_ENV === "production" ? "production" : "sandbox";

let paddlePromise: Promise<Paddle | undefined> | null = null;

export function PricingCheckout() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const { user, loading } = useAuth();
  const [plans, setPlans] = useState<BillingPlan[]>([]);
  const [environment, setEnvironment] = useState<"sandbox" | "production">("sandbox");
  const [plansLoading, setPlansLoading] = useState(true);
  const [checkoutPlan, setCheckoutPlan] = useState("");

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
      trackEvent("purchase", { provider: "paddle", environment });
      router.push("/billing?checkout=success");
    }
    if (event.name === "checkout.error") {
      trackEvent("exception", { description: "Paddle checkout error", fatal: false });
    }
  }, [environment, router]);

  const paddleInstance = useCallback(async () => {
    if (!paddleClientToken) {
      throw new Error("Paddle checkout is not configured yet");
    }
    if (!paddlePromise) {
      paddlePromise = initializePaddle({
        environment: paddleEnvironment,
        token: paddleClientToken,
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
    if (!plan.price_id) {
      toast.error("This plan is missing a Paddle price ID");
      return;
    }
    setCheckoutPlan(plan.key);
    try {
      const paddle = await paddleInstance();
      trackEvent("begin_checkout", {
        plan: plan.key,
        price_id: plan.price_id,
        environment,
      });
      paddle.Checkout.open({
        items: [{ priceId: plan.price_id, quantity: 1 }],
        customer: {
          email: user.email,
        },
        customData: {
          leadforge_user_id: user.id,
          user_id: user.id,
          email: user.email,
          plan_key: plan.key,
        },
        settings: {
          displayMode: "overlay",
          theme: "dark",
          successUrl: `${window.location.origin}/billing?checkout=success`,
          showAddDiscounts: true,
        },
      });
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Unable to open Paddle checkout");
    } finally {
      setCheckoutPlan("");
    }
  }, [environment, paddleInstance, router, user]);

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
            <span className="grid size-10 place-items-center rounded-lg bg-primary text-primary-foreground">
              <BrainCircuit className="size-5" />
            </span>
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

                  <Button className="mt-auto w-full" disabled={busy || loading} onClick={() => openCheckout(plan)}>
                    {busy ? <Loader2 className="animate-spin" /> : <CreditCard />}
                    {user ? "Open checkout" : "Login to subscribe"}
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

function formatMoney(amount: string, currencyCode: string) {
  const value = Number.parseInt(amount || "0", 10) / 100;
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: currencyCode || "USD",
    maximumFractionDigits: value % 1 === 0 ? 0 : 2,
  }).format(value);
}
