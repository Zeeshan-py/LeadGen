import type { Metadata } from "next";

import { PublicInfoPage } from "@/components/public-info-page";
import { StructuredData } from "@/components/structured-data";
import { breadcrumbJsonLd, createPageMetadata } from "@/lib/seo";

export const metadata: Metadata = createPageMetadata("/refund");

const sections = [
  {
    title: "Subscription billing",
    body: [
      "LeadForge AI offers monthly SaaS subscriptions for private lead generation, CRM, outreach, analytics, and AI SDR workspaces. Payments, payment methods, taxes, VAT, invoices, and card security are handled by Paddle as merchant of record.",
      "Paid workspace access starts after a successful checkout or subscription update. Subscription details, billing history, invoices, payment method updates, and cancellations are available from the Billing area or Paddle customer portal.",
    ],
  },
  {
    title: "Cancellations",
    body: [
      "You may cancel your subscription from the Billing area or Paddle customer portal. Cancellation stops future renewals, and your paid features remain available until the end of the current paid billing period unless a different written agreement or applicable law requires otherwise.",
      "After the paid period ends, LeadForge AI may restrict access to paid workspace features until a new paid subscription is active.",
    ],
  },
  {
    title: "Refund requests",
    body: [
      "To request a refund, email support@leadforage.pro with the account email, Paddle transaction or invoice details if available, and a short explanation of the issue.",
      "Refunds are reviewed case by case for issues such as duplicate charges, accidental renewals, unresolved technical access problems, or any refund rights required by applicable law.",
    ],
  },
  {
    title: "Non-refundable usage",
    body: [
      "Completed billing periods, consumed lead generation, outreach sending, campaign activity, AI SDR usage, and other metered workspace usage are generally not refundable except where required by law or approved by LeadForge AI support.",
      "Plan changes may create prorated charges or credits through Paddle. The next renewal reflects the active plan after Paddle processes the subscription change.",
    ],
  },
  {
    title: "Contact",
    body: [
      "For billing, cancellation, invoice, payment, or refund questions, contact support@leadforage.pro.",
      "Last updated: August 12, 2026.",
    ],
  },
];

export default function RefundPage() {
  return (
    <>
      <StructuredData
        data={breadcrumbJsonLd([
          { name: "Home", path: "/" },
          { name: "Refund and Cancellation Policy", path: "/refund" },
        ])}
      />
      <PublicInfoPage
        eyebrow="Refund and Cancellation Policy"
        title="Refund and Cancellation Policy"
        description="This policy explains how LeadForge AI handles subscription cancellations, renewals, refund requests, billing support, and Paddle-managed payments."
        sections={sections}
      />
    </>
  );
}
