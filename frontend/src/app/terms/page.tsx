import { PublicInfoPage } from "@/components/public-info-page";

const sections = [
  {
    title: "Use of LeadForge AI",
    body: [
      "LeadForge AI provides lead generation, CRM, outreach, analytics, and AI SDR tools for business users. You are responsible for using the platform lawfully and for ensuring your campaigns, calls, messages, and imported data comply with applicable rules.",
      "You may not use LeadForge AI to send unlawful spam, impersonate others, violate third-party rights, bypass service restrictions, or attempt to access another user's private workspace.",
    ],
  },
  {
    title: "Account responsibility",
    body: [
      "You are responsible for maintaining access to your account and keeping connected third-party credentials secure. If you connect Gmail, Twilio, Cartesia, Google Sheets, or other services, you confirm that you have permission to use those accounts with LeadForge AI.",
      "LeadForge AI may restrict or disable access if usage appears abusive, unlawful, insecure, or harmful to the platform or other services.",
    ],
  },
  {
    title: "Third-party services",
    body: [
      "LeadForge AI integrates with providers such as Google, Gmail, Google Sheets, Twilio, Cartesia, Apify, Gemini, and PostgreSQL hosting. Your use of those services may also be governed by their own terms and policies.",
      "LeadForge AI is not responsible for outages, policy changes, or behavior of third-party services outside the application's control.",
    ],
  },
  {
    title: "No guaranteed results",
    body: [
      "LeadForge AI helps automate business workflows, but it does not guarantee lead quality, outreach performance, reply rates, revenue, deliverability, call outcomes, or compliance results.",
      "AI-generated content should be reviewed before use, especially when sent to prospects or customers.",
    ],
  },
  {
    title: "Contact",
    body: [
      "For questions about these terms, contact Zeeshan Ahmad at Zeeshanahmad0159@gmail.com.",
      "Last updated: July 29, 2026.",
    ],
  },
];

export default function TermsPage() {
  return (
    <PublicInfoPage
      eyebrow="Terms of Service"
      title="Terms of Service"
      description="These terms describe the basic rules for using LeadForge AI and its connected SaaS workflows."
      sections={sections}
    />
  );
}
