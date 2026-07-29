import type { Metadata } from "next";

import { createNoIndexMetadata } from "@/lib/seo";

export const metadata: Metadata = createNoIndexMetadata(
  "Leads",
  "Private LeadForge AI lead records.",
  "/leads",
);

export default function LeadsLayout({ children }: { children: React.ReactNode }) {
  return children;
}
