/**
 * Root Next.js layout for LeadForge.
 *
 * Wires global CSS, fonts, toast notifications, and the shared AppShell around
 * all application routes.
 */

import type { Metadata, Viewport } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import { AnalyticsProvider } from "@/components/analytics-provider";
import { RouteShell } from "@/components/route-shell";
import { Toaster } from "@/components/ui/sonner";
import { TooltipProvider } from "@/components/ui/tooltip";
import { AuthProvider } from "@/lib/auth";
import { absoluteUrl, indexableRobots, siteConfig } from "@/lib/seo";
import "./globals.css";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
  display: "swap",
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
  display: "swap",
});

export const metadata: Metadata = {
  metadataBase: new URL(siteConfig.url),
  applicationName: siteConfig.name,
  title: {
    default: `${siteConfig.name} | AI Lead Generation, CRM & Outreach SaaS`,
    template: `%s | ${siteConfig.name}`,
  },
  description: siteConfig.description,
  keywords: siteConfig.keywords,
  authors: [{ name: siteConfig.name, url: siteConfig.url }],
  creator: siteConfig.name,
  publisher: siteConfig.name,
  category: "BusinessApplication",
  referrer: "strict-origin-when-cross-origin",
  alternates: {
    canonical: "./",
  },
  robots: indexableRobots,
  formatDetection: {
    telephone: false,
    email: false,
    address: false,
  },
  icons: {
    icon: [
      { url: "/favicon.ico", sizes: "256x256", type: "image/x-icon" },
      { url: "/brand/icon.svg", type: "image/svg+xml" },
    ],
    shortcut: "/favicon.ico",
    apple: [{ url: "/brand/icon-192.png", sizes: "192x192", type: "image/png" }],
    other: [{ rel: "mask-icon", url: "/brand/mask-icon.svg", color: siteConfig.themeColor }],
  },
  manifest: "/manifest.webmanifest",
  openGraph: {
    title: `${siteConfig.name} | AI Lead Generation, CRM & Outreach SaaS`,
    description: siteConfig.description,
    url: siteConfig.url,
    siteName: siteConfig.name,
    locale: siteConfig.locale,
    type: "website",
    images: [
      {
        url: absoluteUrl("/brand/leadforge-og.png"),
        width: 1200,
        height: 630,
        alt: "LeadForge AI lead generation, CRM, outreach, analytics, and AI SDR platform",
      },
    ],
  },
  twitter: {
    card: "summary_large_image",
    title: `${siteConfig.name} | AI Lead Generation, CRM & Outreach SaaS`,
    description: siteConfig.description,
    images: [absoluteUrl("/brand/leadforge-og.png")],
  },
  verification: {
    google: "XCzXxICk5sRK6h6NsADijuzFcVDwrpCzPxYjv5Bwr5U",
  },
  other: {
    "msapplication-TileColor": siteConfig.themeColor,
  },
};

export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
  colorScheme: "dark",
  themeColor: [
    { media: "(prefers-color-scheme: dark)", color: siteConfig.backgroundColor },
    { media: "(prefers-color-scheme: light)", color: siteConfig.themeColor },
  ],
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
        <AnalyticsProvider />
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
