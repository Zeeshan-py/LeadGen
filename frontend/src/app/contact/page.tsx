import type { Metadata } from "next";

import { PublicInfoPage } from "@/components/public-info-page";
import { StructuredData } from "@/components/structured-data";
import { breadcrumbJsonLd, createPageMetadata } from "@/lib/seo";

export const metadata: Metadata = createPageMetadata("/contact");

const sections = [
  {
    title: "Support email",
    body: [
      "For product support, account questions, Google OAuth verification questions, privacy requests, or business inquiries, email support@leadforage.pro.",
      "Please include the email address connected to your LeadForge AI account and a short description of the issue so support can review it quickly.",
    ],
  },
  {
    title: "Product",
    body: [
      "LeadForge AI is a private workspace SaaS for lead generation, CRM, Gmail outreach, analytics, and AI SDR calling workflows.",
      "Production website: https://leadforage.pro",
    ],
  },
  {
    title: "Location",
    body: [
      "LeadForge AI is operated online and supports users through email-based support.",
      "Typical support response times vary by request complexity and operational availability.",
    ],
  },
];

export default function ContactPage() {
  return (
    <>
      <StructuredData
        data={breadcrumbJsonLd([
          { name: "Home", path: "/" },
          { name: "Contact", path: "/contact" },
        ])}
      />
      <PublicInfoPage
        eyebrow="Contact"
        title="Contact LeadForge AI"
        description="Use this page for support, privacy, OAuth verification, and general business inquiries."
        sections={sections}
      />
    </>
  );
}
