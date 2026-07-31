import type { Metadata } from "next";
import Link from "next/link";
import { CreditCard, XCircle } from "lucide-react";

import { Button } from "@/components/ui/button";

export const metadata: Metadata = {
  title: "Checkout Cancelled",
  robots: {
    index: false,
    follow: false,
  },
};

export default function BillingCancelPage() {
  return (
    <main className="mx-auto grid min-h-[calc(100svh-8rem)] max-w-3xl place-items-center">
      <section className="w-full rounded-lg border border-border/70 bg-card/75 p-6 shadow-sm">
        <div className="flex items-start gap-4">
          <div className="grid size-11 shrink-0 place-items-center rounded-lg bg-destructive/10 text-destructive">
            <XCircle className="size-6" />
          </div>
          <div>
            <h1 className="text-2xl font-semibold tracking-normal">Checkout cancelled</h1>
            <p className="mt-3 text-sm leading-6 text-muted-foreground">
              No subscription changes were made. You can return to pricing whenever you are ready to choose a plan.
            </p>
            <div className="mt-6 flex flex-wrap gap-3">
              <Button asChild>
                <Link href="/pricing">
                  <CreditCard />
                  Choose a plan
                </Link>
              </Button>
              <Button asChild variant="outline">
                <Link href="/billing">Back to billing</Link>
              </Button>
            </div>
          </div>
        </div>
      </section>
    </main>
  );
}
