import type { Metadata } from "next";

import { PublicInfoPage } from "@/components/public-info-page";
import { StructuredData } from "@/components/structured-data";
import { breadcrumbJsonLd, createPageMetadata } from "@/lib/seo";

export const metadata: Metadata = createPageMetadata("/features/analytics");

const sections = [
  {
    title: "Sales analytics",
    body: [
      "LeadForge AI analytics help teams review lead volume, campaign performance, email activity, CRM funnel health, and AI SDR productivity.",
      "The analytics workspace is built to show which markets, campaigns, and sales actions are moving prospects forward.",
    ],
  },
  {
    title: "Operational reporting",
    body: [
      "Users can monitor generated leads, saved records, sent emails, replies, open rates, conversion rates, top niches, top cities, and performance trends.",
      "Analytics views support better decisions for targeting, messaging, follow-up, and AI SDR workflows.",
    ],
  },
  {
    title: "Private reporting",
    body: [
      "Analytics are scoped to the signed-in account so each user sees reporting for their own private LeadForge AI workspace.",
    ],
  },
];

export default function AnalyticsFeaturePage() {
  return (
    <>
      <StructuredData
        data={breadcrumbJsonLd([
          { name: "Home", path: "/" },
          { name: "Features", path: "/features" },
          { name: "Analytics", path: "/features/analytics" },
        ])}
      />
      <PublicInfoPage
        eyebrow="Feature"
        title="Sales Analytics and Reporting"
        description="Track lead generation, outreach, CRM funnel progress, conversion rates, and AI SDR activity."
        sections={sections}
      />
    </>
  );
}
