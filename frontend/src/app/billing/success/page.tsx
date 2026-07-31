import type { Metadata } from "next";
import Link from "next/link";
import { CheckCircle2, ReceiptText } from "lucide-react";

import { Button } from "@/components/ui/button";

export const metadata: Metadata = {
  title: "Checkout Complete",
  robots: {
    index: false,
    follow: false,
  },
};

export default function BillingSuccessPage() {
  return (
    <main className="mx-auto grid min-h-[calc(100svh-8rem)] max-w-3xl place-items-center">
      <section className="w-full rounded-lg border border-border/70 bg-card/75 p-6 shadow-sm">
        <div className="flex items-start gap-4">
          <div className="grid size-11 shrink-0 place-items-center rounded-lg bg-primary text-primary-foreground">
            <CheckCircle2 className="size-6" />
          </div>
          <div>
            <h1 className="text-2xl font-semibold tracking-normal">Checkout complete</h1>
            <p className="mt-3 text-sm leading-6 text-muted-foreground">
              Paddle is confirming the payment and syncing your subscription. Your billing page will update as soon as the webhook arrives.
            </p>
            <div className="mt-6 flex flex-wrap gap-3">
              <Button asChild>
                <Link href="/billing">
                  <ReceiptText />
                  View billing
                </Link>
              </Button>
              <Button asChild variant="outline">
                <Link href="/dashboard">Go to dashboard</Link>
              </Button>
            </div>
          </div>
        </div>
      </section>
    </main>
  );
}
