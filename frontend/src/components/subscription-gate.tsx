"use client";

import Link from "next/link";
import { ArrowLeft, CreditCard, LockKeyhole, Sparkles } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import type { FeatureKey } from "@/lib/types";
import { planName, useSubscription } from "@/lib/subscription";
import { cn } from "@/lib/utils";

export function SubscriptionGate({
  feature,
  children,
  benefits,
}: {
  feature: FeatureKey;
  children: React.ReactNode;
  benefits?: string[];
}) {
  const subscription = useSubscription();

  if (subscription.loading) {
    return (
      <div className="grid min-h-[calc(100svh-10rem)] place-items-center">
        <div className="grid gap-3 text-center">
          <div className="mx-auto grid size-11 place-items-center rounded-lg border border-border/70 bg-card/80">
            <LockKeyhole className="size-5 text-muted-foreground" />
          </div>
          <p className="text-sm text-muted-foreground">Checking subscription access</p>
        </div>
      </div>
    );
  }

  if (!subscription.hasFeature(feature)) {
    return <LockedFeaturePage feature={feature} benefits={benefits} />;
  }

  return <>{children}</>;
}

export function LockedFeaturePage({
  feature,
  benefits,
}: {
  feature: FeatureKey;
  benefits?: string[];
}) {
  const { featureLabel, requiredPlanFor } = useSubscription();
  const label = featureLabel(feature);
  const requiredPlan = requiredPlanFor(feature);
  const bullets = benefits?.length ? benefits : defaultBullets(label);

  return (
    <div className="grid min-h-[calc(100svh-8rem)] place-items-center px-2 py-10">
      <Card className="glass-panel w-full max-w-xl overflow-hidden">
        <CardContent className="p-6 md:p-8">
          <div className="flex flex-col items-center text-center">
            <div className="grid size-14 place-items-center rounded-xl bg-primary/10 text-primary">
              <LockKeyhole className="size-7" />
            </div>
            <Badge variant="outline" className="mt-5 border-primary/30 bg-primary/10 text-primary">
              Upgrade Required
            </Badge>
            <h2 className="mt-4 text-2xl font-semibold tracking-normal">{label} is locked</h2>
            <p className="mt-3 max-w-md text-sm leading-6 text-muted-foreground">
              This feature is included in the {planName(requiredPlan)} Plan. Upgrade your subscription to unlock:
            </p>
          </div>
          <ul className="mt-6 grid gap-3 rounded-lg border border-border/70 bg-secondary/25 p-4 text-sm">
            {bullets.map((item) => (
              <li key={item} className="flex gap-3">
                <Sparkles className="mt-0.5 size-4 shrink-0 text-primary" />
                <span>{item}</span>
              </li>
            ))}
          </ul>
          <div className="mt-6 flex flex-col-reverse gap-2 sm:flex-row sm:justify-center">
            <Button variant="outline" asChild>
              <Link href="/dashboard">
                <ArrowLeft />
                Back
              </Link>
            </Button>
            <Button asChild>
              <Link href={`/pricing?plan=${requiredPlan === "free" ? "basic" : requiredPlan}`}>
                <CreditCard />
                Upgrade Plan
              </Link>
            </Button>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}

export function UpgradeModal() {
  const { closeUpgrade, prompt } = useSubscription();
  const requiredPlan = prompt?.requiredPlan ?? "basic";

  return (
    <Dialog open={Boolean(prompt)} onOpenChange={(open) => !open && closeUpgrade()}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>Upgrade Your Plan</DialogTitle>
          <DialogDescription>
            Your current plan doesn&apos;t include this feature. Upgrade to continue using:
          </DialogDescription>
        </DialogHeader>
        <ul className="grid gap-3 rounded-lg border border-border/70 bg-secondary/25 p-4 text-sm">
          {(prompt?.benefits ?? ["Premium access"]).map((item) => (
            <li key={item} className="flex gap-3">
              <LockKeyhole className="mt-0.5 size-4 shrink-0 text-primary" />
              <span>{item}</span>
            </li>
          ))}
        </ul>
        <DialogFooter>
          <Button variant="outline" onClick={closeUpgrade}>
            Maybe Later
          </Button>
          <Button asChild onClick={closeUpgrade}>
            <Link href={`/pricing?plan=${requiredPlan === "free" ? "basic" : requiredPlan}`}>
              <CreditCard />
              Upgrade Now
            </Link>
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

export function PlanBadge({ feature }: { feature: FeatureKey }) {
  const { requiredPlanFor } = useSubscription();
  const requiredPlan = requiredPlanFor(feature);
  if (requiredPlan === "free") return null;
  return (
    <Badge variant="outline" className="border-primary/25 bg-primary/10 text-[10px] uppercase text-primary">
      {requiredPlan}
    </Badge>
  );
}

export function LockedSection({
  feature,
  children,
  className,
  benefits,
}: {
  feature: FeatureKey;
  children: React.ReactNode;
  className?: string;
  benefits?: string[];
}) {
  const subscription = useSubscription();
  const locked = !subscription.loading && !subscription.hasFeature(feature);
  if (!locked) {
    return <>{children}</>;
  }

  return (
    <div className={cn("relative overflow-hidden rounded-lg", className)}>
      <div className="pointer-events-none select-none blur-[2px] opacity-45">{children}</div>
      <div className="absolute inset-0 grid place-items-center bg-background/70 p-4 backdrop-blur-[2px]">
        <div className="max-w-xs rounded-lg border border-border/80 bg-card/95 p-4 text-center shadow-2xl shadow-black/25">
          <LockKeyhole className="mx-auto size-5 text-primary" />
          <p className="mt-2 text-sm font-medium">{subscription.featureLabel(feature)}</p>
          <p className="mt-1 text-xs leading-5 text-muted-foreground">
            Requires the {planName(subscription.requiredPlanFor(feature))} plan.
          </p>
          <Button size="sm" className="mt-3" onClick={() => subscription.openUpgrade(feature, benefits)}>
            Upgrade
          </Button>
        </div>
      </div>
    </div>
  );
}

function defaultBullets(label: string) {
  return [label, "Premium workspace access", "Higher monthly limits"];
}
