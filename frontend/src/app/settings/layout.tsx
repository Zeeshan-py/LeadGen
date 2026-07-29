import type { Metadata } from "next";

import { createNoIndexMetadata } from "@/lib/seo";

export const metadata: Metadata = createNoIndexMetadata(
  "Settings",
  "Private LeadForge AI account and integration settings.",
  "/settings",
);

export default function SettingsLayout({ children }: { children: React.ReactNode }) {
  return children;
}
