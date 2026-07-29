import type { Metadata } from "next";

import { PublicInfoPage } from "@/components/public-info-page";
import { StructuredData } from "@/components/structured-data";
import { breadcrumbJsonLd, createPageMetadata } from "@/lib/seo";

export const metadata: Metadata = createPageMetadata("/features/ai-sdr");

const sections = [
  {
    title: "AI SDR calling workflows",
    body: [
      "LeadForge AI supports AI SDR workflows for qualifying prospects, managing call context, and connecting calling activity with CRM and analytics.",
      "Users can connect their own Twilio account and configure voice settings so AI SDR activity uses their preferred telephony and voice setup.",
    ],
  },
  {
    title: "Voice configuration",
    body: [
      "Voice settings include provider, voice selection, speaking speed, language, AI greeting, business name, assistant name, and Cartesia API key.",
      "These settings are stored per user so each workspace can operate with its own calling identity and voice preferences.",
    ],
  },
  {
    title: "Sales operations context",
    body: [
      "AI SDR activity connects with lead records, CRM stages, outreach history, and analytics so qualification data remains available for follow-up.",
    ],
  },
];

export default function AiSdrFeaturePage() {
  return (
    <>
      <StructuredData
        data={breadcrumbJsonLd([
          { name: "Home", path: "/" },
          { name: "Features", path: "/features" },
          { name: "AI SDR", path: "/features/ai-sdr" },
        ])}
      />
      <PublicInfoPage
        eyebrow="Feature"
        title="AI SDR Calling Workflows"
        description="Use connected Twilio accounts and voice settings to support AI SDR calling and lead qualification workflows."
        sections={sections}
      />
    </>
  );
}
