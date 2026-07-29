import { PublicInfoPage } from "@/components/public-info-page";

const sections = [
  {
    title: "What LeadForge AI does",
    body: [
      "LeadForge AI is a SaaS workspace for finding business leads, enriching contact records, managing CRM follow-up, preparing email outreach, tracking analytics, and running AI SDR workflows.",
      "The platform combines FastAPI, Next.js, PostgreSQL, Docker, Railway, Gmail OAuth, Google Sheets, Twilio, Cartesia, and AI services into one private account-based workspace.",
    ],
  },
  {
    title: "Private workspace model",
    body: [
      "Each LeadForge AI account owns one private workspace. Leads, campaigns, CRM records, outreach, analytics, Gmail connections, Twilio connections, and voice settings are scoped to the signed-in user.",
      "This simple account model is designed for founders, agencies, and SDR teams who need focused lead operations without shared workspace complexity.",
    ],
  },
  {
    title: "Core workflows",
    body: [
      "Users can discover leads, review website opportunities, generate outreach drafts, send email through a connected Gmail account, sync replies, manage CRM stages, and review performance analytics.",
      "AI SDR calling uses the user's connected Twilio account and preferred Cartesia voice settings, so calls run from that user's own phone number and voice configuration.",
    ],
  },
  {
    title: "Operator",
    body: [
      "LeadForge AI is operated by the LeadForge team.",
      "For contact, support, or verification questions, email support@leadforage.pro.",
    ],
  },
];

export default function AboutPage() {
  return (
    <PublicInfoPage
      eyebrow="About"
      title="About LeadForge AI"
      description="LeadForge AI helps small teams turn market research into organized lead pipelines, outreach, analytics, and AI SDR workflows."
      sections={sections}
    />
  );
}
