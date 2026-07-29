import type { Metadata } from "next";

import { PublicInfoPage } from "@/components/public-info-page";
import { StructuredData } from "@/components/structured-data";
import { breadcrumbJsonLd, createPageMetadata } from "@/lib/seo";

export const metadata: Metadata = createPageMetadata("/features/outreach");

const sections = [
  {
    title: "Gmail outreach automation",
    body: [
      "LeadForge AI helps users prepare personalized outreach drafts, send email through their own connected Gmail account, and keep outreach tied to each lead record.",
      "Gmail OAuth for outreach is separate from Google Login, so authentication and email sending credentials remain independent.",
    ],
  },
  {
    title: "Campaign workflow",
    body: [
      "Users can generate cold email and follow-up drafts, send messages, sync replies, and review outreach status across leads and campaigns.",
      "Campaign activity flows into analytics and CRM context so teams can understand which markets and messages are producing responses.",
    ],
  },
  {
    title: "Responsible sending",
    body: [
      "LeadForge AI is designed for business outreach workflows where users control connected email accounts and are responsible for lawful, permission-aware campaign usage.",
    ],
  },
];

export default function OutreachFeaturePage() {
  return (
    <>
      <StructuredData
        data={breadcrumbJsonLd([
          { name: "Home", path: "/" },
          { name: "Features", path: "/features" },
          { name: "Outreach", path: "/features/outreach" },
        ])}
      />
      <PublicInfoPage
        eyebrow="Feature"
        title="Gmail Outreach Automation"
        description="Create AI-assisted email drafts, send campaigns through Gmail, sync replies, and track outreach engagement."
        sections={sections}
      />
    </>
  );
}
