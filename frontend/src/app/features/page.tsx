import type { Metadata } from "next";

import { PublicInfoPage } from "@/components/public-info-page";
import { StructuredData } from "@/components/structured-data";
import { breadcrumbJsonLd, createPageMetadata } from "@/lib/seo";

export const metadata: Metadata = createPageMetadata("/features");

const sections = [
  {
    title: "Lead operations in one private workspace",
    body: [
      "LeadForge AI combines lead generation, CRM, Gmail outreach, analytics, Google Sheets export, Twilio calling, Cartesia voice settings, and AI SDR workflows in one account-based SaaS platform.",
      "The product is designed to help teams move from prospect discovery to qualification and follow-up without spreading sensitive lead data across disconnected tools.",
    ],
  },
  {
    title: "Core features",
    body: [
      "AI lead discovery helps identify business prospects, enrich contact records, and surface website opportunities.",
      "CRM tools help manage stages, notes, assignments, follow-up, and pipeline outcomes.",
      "Outreach workflows support Gmail connection, AI-assisted email drafts, campaign sending, reply sync, and engagement tracking.",
      "AI SDR workflows use Twilio and voice settings to support calling, qualification, and follow-up operations.",
    ],
  },
  {
    title: "Built for private SaaS usage",
    body: [
      "Each signed-in user has a private workspace. Leads, campaigns, CRM records, Gmail connections, Twilio settings, voice preferences, and analytics are scoped to that account.",
      "This structure keeps the product simple for founders, agencies, and SDR teams that need focused lead generation and sales automation.",
    ],
  },
];

export default function FeaturesPage() {
  return (
    <>
      <StructuredData
        data={breadcrumbJsonLd([
          { name: "Home", path: "/" },
          { name: "Features", path: "/features" },
        ])}
      />
      <PublicInfoPage
        eyebrow="Features"
        title="LeadForge AI Features"
        description="Explore the lead generation, CRM, outreach, analytics, and AI SDR tools included in LeadForge AI."
        sections={sections}
      />
    </>
  );
}
