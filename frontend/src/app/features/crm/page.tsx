import type { Metadata } from "next";

import { PublicInfoPage } from "@/components/public-info-page";
import { StructuredData } from "@/components/structured-data";
import { breadcrumbJsonLd, createPageMetadata } from "@/lib/seo";

export const metadata: Metadata = createPageMetadata("/features/crm");

const sections = [
  {
    title: "Private CRM pipeline",
    body: [
      "LeadForge AI includes a private CRM workspace for tracking prospect stages, notes, assignments, tags, follow-up dates, and sales outcomes.",
      "CRM records are connected to lead generation, outreach history, analytics, and AI SDR activity so every prospect has context.",
    ],
  },
  {
    title: "Pipeline management",
    body: [
      "Teams can review leads in table and kanban-style workflows, update CRM stages, add notes, schedule follow-up, and mark opportunities won or lost.",
      "CRM usage is scoped to the signed-in account, helping each user manage their own sales pipeline securely.",
    ],
  },
  {
    title: "Better follow-up",
    body: [
      "A connected CRM keeps outreach, reply sync, call outcomes, and lead qualification visible in one place so follow-up decisions are easier to make.",
    ],
  },
];

export default function CrmFeaturePage() {
  return (
    <>
      <StructuredData
        data={breadcrumbJsonLd([
          { name: "Home", path: "/" },
          { name: "Features", path: "/features" },
          { name: "CRM", path: "/features/crm" },
        ])}
      />
      <PublicInfoPage
        eyebrow="Feature"
        title="CRM Pipeline Management"
        description="Manage lead stages, notes, assignments, and follow-up in a private CRM workspace."
        sections={sections}
      />
    </>
  );
}
