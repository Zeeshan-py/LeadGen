import type { Metadata } from "next";

import { createNoIndexMetadata } from "@/lib/seo";

export const metadata: Metadata = createNoIndexMetadata(
  "Reset Password",
  "Set a new password for a LeadForge AI account.",
  "/reset-password",
);

export default function ResetPasswordLayout({ children }: { children: React.ReactNode }) {
  return children;
}
