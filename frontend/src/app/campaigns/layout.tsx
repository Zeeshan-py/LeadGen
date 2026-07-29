import type { Metadata } from "next";

import { createNoIndexMetadata } from "@/lib/seo";

export const metadata: Metadata = createNoIndexMetadata(
  "Campaigns",
  "Private LeadForge AI campaign history.",
  "/campaigns",
);

export default function CampaignsLayout({ children }: { children: React.ReactNode }) {
  return children;
}
