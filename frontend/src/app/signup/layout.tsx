import type { Metadata } from "next";

import { createPageMetadata } from "@/lib/seo";

export const metadata: Metadata = createPageMetadata("/signup");

export default function SignupLayout({ children }: { children: React.ReactNode }) {
  return children;
}
