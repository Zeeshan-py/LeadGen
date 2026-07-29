import type { Metadata } from "next";

import { createNoIndexMetadata } from "@/lib/seo";

export const metadata: Metadata = createNoIndexMetadata(
  "Outreach Workspace",
  "Private LeadForge AI Gmail outreach workspace.",
  "/outreach",
);

export default function OutreachLayout({ children }: { children: React.ReactNode }) {
  return children;
}
