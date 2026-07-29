import type { Metadata } from "next";

import { createNoIndexMetadata } from "@/lib/seo";

export const metadata: Metadata = createNoIndexMetadata(
  "AI SDR Workspace",
  "Private LeadForge AI SDR calling workspace.",
  "/ai-sdr",
);

export default function AiSdrLayout({ children }: { children: React.ReactNode }) {
  return children;
}
