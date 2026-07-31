import type { Metadata } from "next";
import { Suspense } from "react";

import { PricingCheckout } from "@/components/billing/pricing-checkout";
import { StructuredData } from "@/components/structured-data";
import { breadcrumbJsonLd, createPageMetadata } from "@/lib/seo";

export const metadata: Metadata = createPageMetadata("/pricing");

export default function PricingPage() {
  return (
    <>
      <StructuredData
        data={breadcrumbJsonLd([
          { name: "Home", path: "/" },
          { name: "Pricing", path: "/pricing" },
        ])}
      />
      <Suspense fallback={null}>
        <PricingCheckout />
      </Suspense>
    </>
  );
}
