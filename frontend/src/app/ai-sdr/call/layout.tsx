import type { Metadata } from "next";

import { createNoIndexMetadata } from "@/lib/seo";

export const metadata: Metadata = createNoIndexMetadata(
  "AI SDR Call",
  "Private LeadForge AI SDR call workspace.",
  "/ai-sdr/call",
);

export default function AiSdrCallLayout({ children }: { children: React.ReactNode }) {
  return children;
}
