import { PublicInfoPage } from "@/components/public-info-page";

const sections = [
  {
    title: "Information we collect",
    body: [
      "LeadForge AI collects account information such as name, email address, authentication provider, and login metadata. When you use the platform, we also store workspace data you create or import, including leads, campaigns, CRM notes, analytics events, outreach drafts, and integration settings.",
      "If you connect third-party services, LeadForge AI may store the minimum credentials needed to operate that connection, such as encrypted Gmail refresh tokens, encrypted Twilio auth tokens, encrypted Cartesia API keys, and service configuration values.",
    ],
  },
  {
    title: "How we use information",
    body: [
      "We use your information to provide lead generation, CRM, outreach, analytics, AI SDR calling, authentication, account security, and support. We do not sell your personal data.",
      "Workspace data is scoped to your signed-in account. LeadForge AI is designed so one account has one private workspace, and users cannot access another user's leads, campaigns, CRM records, Gmail connection, Twilio connection, or voice settings.",
    ],
  },
  {
    title: "Google user data",
    body: [
      "Google Login is used only to authenticate your LeadForge AI account. Gmail OAuth is separate and is used only when you choose to connect Gmail for outreach sending and reply sync.",
      "LeadForge AI uses Google data only to provide the feature you requested, such as signing in, connecting Gmail, sending outreach from your Gmail account, syncing replies, or writing configured lead records to Google Sheets.",
    ],
  },
  {
    title: "Data protection",
    body: [
      "Sensitive integration credentials are stored encrypted where supported by the application. Authentication cookies are HttpOnly, refresh tokens are stored server-side, and unsafe API writes use CSRF protection.",
      "No internet service can guarantee perfect security, but LeadForge AI is built with account isolation, least-necessary credential use, and production deployment controls in mind.",
    ],
  },
  {
    title: "Contact",
    body: [
      "For privacy questions or data requests, contact Zeeshan Ahmad at Zeeshanahmad0159@gmail.com.",
      "Last updated: July 29, 2026.",
    ],
  },
];

export default function PrivacyPage() {
  return (
    <PublicInfoPage
      eyebrow="Privacy Policy"
      title="Privacy Policy"
      description="This policy explains how LeadForge AI collects, uses, protects, and scopes information for private SaaS workspaces."
      sections={sections}
    />
  );
}
