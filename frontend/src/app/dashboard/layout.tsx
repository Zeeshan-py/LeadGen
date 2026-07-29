import type { Metadata } from "next";

import { createNoIndexMetadata } from "@/lib/seo";

export const metadata: Metadata = createNoIndexMetadata(
  "Dashboard",
  "Private LeadForge AI workspace dashboard.",
  "/dashboard",
);

export default function DashboardLayout({ children }: { children: React.ReactNode }) {
  return children;
}
