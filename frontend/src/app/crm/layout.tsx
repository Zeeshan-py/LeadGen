import type { Metadata } from "next";

import { createNoIndexMetadata } from "@/lib/seo";

export const metadata: Metadata = createNoIndexMetadata(
  "CRM Workspace",
  "Private LeadForge AI CRM pipeline workspace.",
  "/crm",
);

export default function CrmLayout({ children }: { children: React.ReactNode }) {
  return children;
}
