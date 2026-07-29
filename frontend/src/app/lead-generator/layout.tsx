import type { Metadata } from "next";

import { createNoIndexMetadata } from "@/lib/seo";

export const metadata: Metadata = createNoIndexMetadata(
  "Lead Generator Workspace",
  "Private LeadForge AI lead generation workspace.",
  "/lead-generator",
);

export default function LeadGeneratorLayout({ children }: { children: React.ReactNode }) {
  return children;
}
