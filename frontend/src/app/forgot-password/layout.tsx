import type { Metadata } from "next";

import { createNoIndexMetadata } from "@/lib/seo";

export const metadata: Metadata = createNoIndexMetadata(
  "Forgot Password",
  "Request a secure password reset link for a LeadForge AI account.",
  "/forgot-password",
);

export default function ForgotPasswordLayout({ children }: { children: React.ReactNode }) {
  return children;
}
