import type { Metadata } from "next";
import { Suspense } from "react";

import { BillingDashboard } from "@/components/billing/billing-dashboard";

export const metadata: Metadata = {
  title: "Billing",
  robots: {
    index: false,
    follow: false,
  },
};

export default function BillingPage() {
  return (
    <Suspense fallback={null}>
      <BillingDashboard />
    </Suspense>
  );
}
