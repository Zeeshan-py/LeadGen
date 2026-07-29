import type { Metadata } from "next";

import { PublicInfoPage } from "@/components/public-info-page";
import { StructuredData } from "@/components/structured-data";
import { breadcrumbJsonLd, createPageMetadata } from "@/lib/seo";

export const metadata: Metadata = createPageMetadata("/pricing");

const sections = [
  {
    title: "Private SaaS workspace",
    body: [
      "LeadForge AI pricing is designed around private workspaces that include lead generation, CRM, Gmail outreach, analytics, Google Sheets support, and AI SDR workflows.",
      "The product is currently configured for account-based access. Contact support for current availability, usage limits, and plan information.",
    ],
  },
  {
    title: "What plans can include",
    body: [
      "Plans may include AI lead discovery, CRM pipeline management, campaign and outreach tools, Gmail connection, reply sync, Google Sheets export, Twilio connection, Cartesia voice settings, and analytics reporting.",
      "Usage may vary by lead volume, email volume, calling configuration, connected providers, and operational requirements.",
    ],
  },
  {
    title: "Contact",
    body: [
      "For pricing, account access, or business questions, email support@leadforage.pro.",
    ],
  },
];

export default function PricingPage() {
  return (
    <>
      <StructuredData
        data={breadcrumbJsonLd([
          { name: "Home", path: "/" },
          { name: "Pricing", path: "/pricing" },
        ])}
      />
      <PublicInfoPage
        eyebrow="Pricing"
        title="LeadForge AI Pricing"
        description="Learn how LeadForge AI plans support private lead generation, CRM, outreach, analytics, and AI SDR workspaces."
        sections={sections}
      />
    </>
  );
}
