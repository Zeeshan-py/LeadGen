import type { Metadata } from "next";

import { createNoIndexMetadata } from "@/lib/seo";

export const metadata: Metadata = createNoIndexMetadata(
  "Analytics Workspace",
  "Private LeadForge AI sales analytics workspace.",
  "/analytics",
);

export default function AnalyticsLayout({ children }: { children: React.ReactNode }) {
  return children;
}
