/**
 * Root Next.js layout for LeadForge.
 *
 * Wires global CSS, fonts, toast notifications, and the shared AppShell around
 * all application routes.
 */

import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import { RouteShell } from "@/components/route-shell";
import { Toaster } from "@/components/ui/sonner";
import { TooltipProvider } from "@/components/ui/tooltip";
import { AuthProvider } from "@/lib/auth";
import "./globals.css";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "LeadForge AI",
  description: "Private AI lead generation workspace",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" className="dark">
      <body
        className={`${geistSans.variable} ${geistMono.variable} antialiased`}
      >
        <TooltipProvider>
          <AuthProvider>
            <RouteShell>{children}</RouteShell>
          </AuthProvider>
          <Toaster richColors position="top-right" />
        </TooltipProvider>
      </body>
    </html>
  );
}
