"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { ArrowUpRight, Check, CreditCard, Loader2, ReceiptText, ShieldCheck, XCircle } from "lucide-react";
import { toast } from "sonner";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import {
  cancelSubscription,
  changeSubscriptionPlan,
  createBillingPortalSession,
  getBillingHistory,
  getBillingOverview,
} from "@/lib/api";
import { trackEvent } from "@/lib/analytics";
import type { BillingOverview, PaddleTransaction } from "@/lib/types";
import { cn } from "@/lib/utils";

export function BillingDashboard() {
  const searchParams = useSearchParams();
  const [overview, setOverview] = useState<BillingOverview | null>(null);
  const [transactions, setTransactions] = useState<PaddleTransaction[]>([]);
  const [loading, setLoading] = useState(true);
  const [action, setAction] = useState("");

  useEffect(() => {
    if (searchParams.get("checkout") === "success") {
      toast.success("Checkout completed. Subscription status may take a moment to sync.");
    }
  }, [searchParams]);

  useEffect(() => {
    void refreshBilling();
  }, []);

  async function refreshBilling() {
    setLoading(true);
    try {
      const [nextOverview, history] = await Promise.all([getBillingOverview(), getBillingHistory()]);
      setOverview(nextOverview);
      setTransactions(history.transactions);
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Unable to load billing");
    } finally {
      setLoading(false);
    }
  }

  const currentPlan = useMemo(
    () => overview?.plans.find((plan) => plan.price_id === overview.subscription?.price_id),
    [overview],
  );

  async function openPortal() {
    setAction("portal");
    try {
      const session = await createBillingPortalSession();
      trackEvent("billing_portal_opened", { provider: "paddle" });
      window.location.assign(session.url);
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Unable to open billing portal");
    } finally {
      setAction("");
    }
  }

  async function changePlan(priceId: string, planKey: string) {
    if (!overview?.subscription) return;
    setAction(`change:${priceId}`);
    try {
      await changeSubscriptionPlan(overview.subscription.subscription_id, {
        price_id: priceId,
        proration_billing_mode: "prorated_immediately",
      });
      trackEvent("subscription_plan_changed", { plan: planKey, provider: "paddle" });
      toast.success("Subscription plan updated");
      await refreshBilling();
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Unable to update subscription");
    } finally {
      setAction("");
    }
  }

  async function cancelAtPeriodEnd() {
    if (!overview?.subscription) return;
    setAction("cancel");
    try {
      await cancelSubscription(overview.subscription.subscription_id, {
        effective_from: "next_billing_period",
      });
      trackEvent("subscription_cancel_scheduled", { provider: "paddle" });
      toast.success("Cancellation scheduled for the end of the billing period");
      await refreshBilling();
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Unable to cancel subscription");
    } finally {
      setAction("");
    }
  }

  if (loading) {
    return (
      <div className="grid min-h-[calc(100svh-8rem)] place-items-center">
        <Loader2 className="size-7 animate-spin text-primary" />
      </div>
    );
  }

  return (
    <div className="mx-auto grid max-w-7xl gap-6">
      <section className="rounded-lg border border-border/70 bg-card/75 p-5 shadow-sm">
        <div className="flex flex-col gap-4 md:flex-row md:items-start md:justify-between">
          <div>
            <Badge variant="outline" className="border-primary/30 bg-primary/10 text-primary">
              Paddle {overview?.environment === "sandbox" ? "Sandbox" : "Production"}
            </Badge>
            <h2 className="mt-4 text-2xl font-semibold tracking-normal">Subscription</h2>
            <p className="mt-2 max-w-2xl text-sm leading-6 text-muted-foreground">
              Manage your LeadForge AI plan, invoices, payment method, and subscription lifecycle.
            </p>
          </div>
          <div className="flex flex-wrap gap-2">
            <Button variant="outline" onClick={openPortal} disabled={!overview?.customer || action === "portal"}>
              {action === "portal" ? <Loader2 className="animate-spin" /> : <ArrowUpRight />}
              Customer portal
            </Button>
            {!overview?.subscription ? (
              <Button asChild>
                <Link href="/pricing">
                  <CreditCard />
                  Choose plan
                </Link>
              </Button>
            ) : null}
          </div>
        </div>

        <div className="mt-6 grid gap-4 md:grid-cols-3">
          <Metric label="Current plan" value={currentPlan?.name || "No subscription"} />
          <Metric label="Status" value={formatStatus(overview?.subscription?.status)} />
          <Metric label="Next bill" value={formatDate(overview?.subscription?.next_billed_at)} />
        </div>

        {overview?.subscription?.scheduled_change_action ? (
          <div className="mt-4 rounded-lg border border-amber-400/30 bg-amber-400/10 p-4 text-sm text-amber-100">
            {overview.subscription.scheduled_change_action} scheduled for{" "}
            {formatDate(overview.subscription.scheduled_change_effective_at)}.
          </div>
        ) : null}
      </section>

      <section className="rounded-lg border border-border/70 bg-card/75 p-5 shadow-sm">
        <div className="flex items-center gap-3">
          <ShieldCheck className="size-5 text-primary" />
          <h2 className="text-xl font-semibold tracking-normal">Plans</h2>
        </div>
        <div className="mt-5 grid gap-4 lg:grid-cols-3">
          {overview?.plans.map((plan) => {
            const isCurrent = plan.price_id === overview.subscription?.price_id;
            const busy = action === `change:${plan.price_id}`;
            return (
              <article
                key={plan.key}
                className={cn(
                  "flex min-h-80 flex-col rounded-lg border bg-background/45 p-5",
                  isCurrent ? "border-primary/60" : "border-border/70",
                )}
              >
                <div className="flex items-start justify-between gap-3">
                  <div>
                    <h3 className="text-lg font-semibold tracking-normal">{plan.name}</h3>
                    <p className="mt-2 min-h-12 text-sm leading-6 text-muted-foreground">{plan.description}</p>
                  </div>
                  {isCurrent ? <Badge className="bg-primary text-primary-foreground">Current</Badge> : null}
                </div>
                <p className="mt-5 text-3xl font-semibold tracking-normal">
                  {formatMoney(plan.amount, plan.currency_code)}
                  <span className="text-sm font-normal text-muted-foreground">/{plan.interval}</span>
                </p>
                <ul className="mt-5 grid gap-2 text-sm text-muted-foreground">
                  {plan.features.slice(0, 4).map((feature) => (
                    <li key={feature} className="flex gap-2">
                      <Check className="mt-0.5 size-4 shrink-0 text-primary" />
                      <span>{feature}</span>
                    </li>
                  ))}
                </ul>
                {overview?.subscription ? (
                  <Button
                    className="mt-auto w-full"
                    variant={isCurrent ? "outline" : "default"}
                    disabled={isCurrent || busy}
                    onClick={() => changePlan(plan.price_id, plan.key)}
                  >
                    {busy ? <Loader2 className="animate-spin" /> : <CreditCard />}
                    {isCurrent ? "Active plan" : "Switch plan"}
                  </Button>
                ) : (
                  <Button asChild className="mt-auto w-full">
                    <Link href={`/pricing?plan=${plan.key}`}>
                      <CreditCard />
                      Subscribe
                    </Link>
                  </Button>
                )}
              </article>
            );
          })}
        </div>
      </section>

      {overview?.subscription ? (
        <section className="rounded-lg border border-border/70 bg-card/75 p-5 shadow-sm">
          <div className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
            <div>
              <h2 className="text-xl font-semibold tracking-normal">Cancellation</h2>
              <p className="mt-2 text-sm leading-6 text-muted-foreground">
                Schedule cancellation at the end of the current billing period. The workspace remains active until then.
              </p>
            </div>
            <Button variant="outline" disabled={action === "cancel"} onClick={cancelAtPeriodEnd}>
              {action === "cancel" ? <Loader2 className="animate-spin" /> : <XCircle />}
              Cancel at period end
            </Button>
          </div>
        </section>
      ) : null}

      <section className="rounded-lg border border-border/70 bg-card/75 p-5 shadow-sm">
        <div className="flex items-center gap-3">
          <ReceiptText className="size-5 text-primary" />
          <h2 className="text-xl font-semibold tracking-normal">Billing history</h2>
        </div>
        <div className="mt-5 overflow-hidden rounded-lg border border-border/70">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Date</TableHead>
                <TableHead>Status</TableHead>
                <TableHead>Invoice</TableHead>
                <TableHead className="text-right">Total</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {transactions.length ? (
                transactions.map((transaction) => (
                  <TableRow key={transaction.transaction_id}>
                    <TableCell>{formatDate(transaction.billed_at)}</TableCell>
                    <TableCell>{formatStatus(transaction.status)}</TableCell>
                    <TableCell>{transaction.invoice_number || transaction.transaction_id}</TableCell>
                    <TableCell className="text-right">{formatMoney(transaction.total, transaction.currency_code)}</TableCell>
                  </TableRow>
                ))
              ) : (
                <TableRow>
                  <TableCell colSpan={4} className="h-24 text-center text-muted-foreground">
                    No billing transactions synced yet.
                  </TableCell>
                </TableRow>
              )}
            </TableBody>
          </Table>
        </div>
      </section>
    </div>
  );
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-lg border border-border/70 bg-background/45 p-4">
      <p className="text-xs text-muted-foreground">{label}</p>
      <p className="mt-2 truncate text-lg font-semibold">{value}</p>
    </div>
  );
}

function formatStatus(status?: string | null) {
  if (!status) return "None";
  return status
    .split("_")
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(" ");
}

function formatDate(value?: string | null) {
  if (!value) return "Not scheduled";
  return new Intl.DateTimeFormat("en-US", {
    month: "short",
    day: "numeric",
    year: "numeric",
  }).format(new Date(value));
}

function formatMoney(amount: string, currencyCode: string) {
  const value = Number.parseInt(amount || "0", 10) / 100;
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: currencyCode || "USD",
    maximumFractionDigits: value % 1 === 0 ? 0 : 2,
  }).format(value);
}
