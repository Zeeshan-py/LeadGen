import type { Metadata } from "next";

import { PublicInfoPage } from "@/components/public-info-page";
import { StructuredData } from "@/components/structured-data";
import { breadcrumbJsonLd, createPageMetadata } from "@/lib/seo";

export const metadata: Metadata = createPageMetadata("/features/lead-generator");

const sections = [
  {
    title: "AI lead discovery",
    body: [
      "The LeadForge AI lead generator helps businesses search markets, discover prospects, enrich records, and organize lead data for sales follow-up.",
      "Teams can focus searches by country, city, business type, and website status so lead generation campaigns match the intended market.",
    ],
  },
  {
    title: "Lead enrichment",
    body: [
      "Lead records can include business names, websites, emails, phone numbers, social profiles, locations, industries, and website opportunity signals.",
      "Generated leads flow into CRM, outreach, campaign history, analytics, and AI SDR workflows so sales activity stays connected.",
    ],
  },
  {
    title: "Use cases",
    body: [
      "Founders use it to build early customer lists. Agencies use it to research prospects for client campaigns. SDR teams use it to prepare targeted outreach and qualification workflows.",
    ],
  },
];

export default function LeadGeneratorFeaturePage() {
  return (
    <>
      <StructuredData
        data={breadcrumbJsonLd([
          { name: "Home", path: "/" },
          { name: "Features", path: "/features" },
          { name: "AI Lead Generator", path: "/features/lead-generator" },
        ])}
      />
      <PublicInfoPage
        eyebrow="Feature"
        title="AI Lead Generator"
        description="Generate and enrich business leads with focused market filters and AI-assisted sales context."
        sections={sections}
      />
    </>
  );
}
