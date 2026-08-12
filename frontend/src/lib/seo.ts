import type { Metadata, MetadataRoute } from "next";

export const siteConfig = {
  name: "LeadForge AI",
  url: process.env.NEXT_PUBLIC_SITE_URL?.replace(/\/+$/, "") || "https://leadforage.pro",
  supportEmail: "support@leadforage.pro",
  locale: "en_US",
  language: "en",
  themeColor: "#34d399",
  backgroundColor: "#020617",
  shortDescription: "AI-powered lead generation, CRM, outreach, analytics, and AI SDR automation.",
  description:
    "LeadForge AI is an AI-powered SaaS platform that helps businesses generate leads, manage CRM, automate outreach campaigns, track analytics, and operate AI SDR workflows.",
  keywords: [
    "AI lead generation",
    "lead generation SaaS",
    "CRM automation",
    "email outreach software",
    "AI SDR",
    "sales automation",
    "Gmail outreach",
    "Twilio AI calling",
    "B2B lead generation",
  ],
};

export type PublicPage = {
  path: string;
  title: string;
  description: string;
  sitemapPriority: number;
  changeFrequency: MetadataRoute.Sitemap[number]["changeFrequency"];
};

export const publicPages = [
  {
    path: "/",
    title: "AI Lead Generation, CRM & Outreach SaaS",
    description: siteConfig.description,
    sitemapPriority: 1,
    changeFrequency: "weekly",
  },
  {
    path: "/features",
    title: "LeadForge AI Features",
    description:
      "Explore LeadForge AI features for lead discovery, CRM follow-up, Gmail outreach, analytics, Google Sheets export, Twilio calling, and AI SDR workflows.",
    sitemapPriority: 0.9,
    changeFrequency: "monthly",
  },
  {
    path: "/features/lead-generator",
    title: "AI Lead Generator",
    description:
      "Find business prospects, enrich lead records, identify website opportunities, and organize qualified leads with LeadForge AI.",
    sitemapPriority: 0.85,
    changeFrequency: "monthly",
  },
  {
    path: "/features/crm",
    title: "CRM Pipeline Management",
    description:
      "Manage lead stages, sales notes, follow-up tasks, assignments, and pipeline activity in a private LeadForge AI CRM workspace.",
    sitemapPriority: 0.85,
    changeFrequency: "monthly",
  },
  {
    path: "/features/outreach",
    title: "Gmail Outreach Automation",
    description:
      "Create AI-assisted outreach drafts, send campaigns through connected Gmail accounts, sync replies, and track prospect engagement.",
    sitemapPriority: 0.85,
    changeFrequency: "monthly",
  },
  {
    path: "/features/ai-sdr",
    title: "AI SDR Calling Workflows",
    description:
      "Operate AI SDR workflows with user-connected Twilio accounts, Cartesia voice settings, call tracking, and lead qualification workflows.",
    sitemapPriority: 0.85,
    changeFrequency: "monthly",
  },
  {
    path: "/features/analytics",
    title: "Sales Analytics and Reporting",
    description:
      "Review campaign performance, conversion trends, lead sources, CRM funnel health, and AI SDR activity inside LeadForge AI analytics.",
    sitemapPriority: 0.85,
    changeFrequency: "monthly",
  },
  {
    path: "/pricing",
    title: "Pricing",
    description:
      "Review LeadForge AI pricing information for private SaaS workspaces, lead generation, outreach automation, CRM, analytics, and AI SDR workflows.",
    sitemapPriority: 0.8,
    changeFrequency: "monthly",
  },
  {
    path: "/about",
    title: "About",
    description:
      "Learn about LeadForge AI, a private SaaS workspace for lead generation, CRM, outreach, analytics, Gmail, Twilio, Cartesia, and AI SDR workflows.",
    sitemapPriority: 0.7,
    changeFrequency: "monthly",
  },
  {
    path: "/contact",
    title: "Contact",
    description:
      "Contact LeadForge AI for product support, account help, privacy requests, OAuth verification questions, and business inquiries.",
    sitemapPriority: 0.7,
    changeFrequency: "monthly",
  },
  {
    path: "/privacy",
    title: "Privacy Policy",
    description:
      "Read the LeadForge AI privacy policy covering account data, workspace data, Google Login, Gmail OAuth, Twilio, and integration credentials.",
    sitemapPriority: 0.6,
    changeFrequency: "yearly",
  },
  {
    path: "/terms",
    title: "Terms of Service",
    description:
      "Read the LeadForge AI terms of service for using lead generation, CRM, outreach, analytics, and AI SDR automation workflows.",
    sitemapPriority: 0.6,
    changeFrequency: "yearly",
  },
  {
    path: "/refund",
    title: "Refund and Cancellation Policy",
    description:
      "Read the LeadForge AI refund and cancellation policy for monthly SaaS subscriptions, renewals, cancellations, and billing support.",
    sitemapPriority: 0.6,
    changeFrequency: "yearly",
  },
  {
    path: "/login",
    title: "Login",
    description:
      "Log in to your LeadForge AI account to access your private lead generation, CRM, outreach, analytics, and AI SDR workspace.",
    sitemapPriority: 0.4,
    changeFrequency: "monthly",
  },
  {
    path: "/signup",
    title: "Sign Up",
    description:
      "Create a LeadForge AI account to start using AI-powered lead generation, CRM, outreach, analytics, and AI SDR automation.",
    sitemapPriority: 0.5,
    changeFrequency: "monthly",
  },
] satisfies PublicPage[];

export const privateAppPaths = [
  "/dashboard",
  "/lead-generator",
  "/leads",
  "/crm",
  "/campaigns",
  "/outreach",
  "/analytics",
  "/settings",
  "/ai-sdr",
  "/ai-sdr/call",
];

export function absoluteUrl(path = "/") {
  const url = new URL(path.startsWith("/") ? path : `/${path}`, `${siteConfig.url}/`);
  const leaf = url.pathname.split("/").filter(Boolean).at(-1) || "";
  const isFilePath = leaf.includes(".");

  if (url.pathname !== "/" && !url.pathname.endsWith("/") && !isFilePath) {
    url.pathname = `${url.pathname}/`;
  }

  return url.toString();
}

export function pageFor(path: string) {
  const normalizedPath = path === "/" ? "/" : path.replace(/\/+$/, "");
  const page = publicPages.find((item) => item.path === normalizedPath);
  if (!page) {
    throw new Error(`No SEO page configured for ${path}`);
  }
  return page;
}

export function createPageMetadata(path: string): Metadata {
  const page = pageFor(path);
  const isHome = page.path === "/";
  const canonical = absoluteUrl(page.path);
  const title = isHome ? `${siteConfig.name} | ${page.title}` : page.title;
  const image = absoluteUrl("/brand/leadforge-og.png");

  return {
    title,
    description: page.description,
    keywords: siteConfig.keywords,
    alternates: {
      canonical,
    },
    openGraph: {
      title: isHome ? `${siteConfig.name} | ${page.title}` : `${page.title} | ${siteConfig.name}`,
      description: page.description,
      url: canonical,
      siteName: siteConfig.name,
      locale: siteConfig.locale,
      type: "website",
      images: [
        {
          url: image,
          width: 1200,
          height: 630,
          alt: "LeadForge AI lead generation and CRM automation platform",
        },
      ],
    },
    twitter: {
      card: "summary_large_image",
      title: isHome ? `${siteConfig.name} | ${page.title}` : `${page.title} | ${siteConfig.name}`,
      description: page.description,
      images: [image],
    },
    robots: indexableRobots,
  };
}

export function createNoIndexMetadata(title: string, description: string, path: string): Metadata {
  return {
    title,
    description,
    alternates: {
      canonical: absoluteUrl(path),
    },
    robots: {
      index: false,
      follow: false,
      googleBot: {
        index: false,
        follow: false,
      },
    },
  };
}

export const indexableRobots = {
  index: true,
  follow: true,
  googleBot: {
    index: true,
    follow: true,
    "max-snippet": -1,
    "max-image-preview": "large",
    "max-video-preview": -1,
  },
} satisfies Metadata["robots"];

export function organizationJsonLd() {
  return {
    "@context": "https://schema.org",
    "@type": "Organization",
    "@id": absoluteUrl("/#organization"),
    name: siteConfig.name,
    url: siteConfig.url,
    logo: absoluteUrl("/brand/leadforge-icon.png"),
    email: siteConfig.supportEmail,
    contactPoint: [
      {
        "@type": "ContactPoint",
        contactType: "customer support",
        email: siteConfig.supportEmail,
        availableLanguage: ["en"],
      },
    ],
    sameAs: [siteConfig.url],
  };
}

export function softwareApplicationJsonLd() {
  return {
    "@context": "https://schema.org",
    "@type": "SoftwareApplication",
    "@id": absoluteUrl("/#software"),
    name: siteConfig.name,
    applicationCategory: "BusinessApplication",
    operatingSystem: "Web",
    url: siteConfig.url,
    description: siteConfig.description,
    offers: {
      "@type": "AggregateOffer",
      lowPrice: "15",
      highPrice: "50",
      priceCurrency: "USD",
      offerCount: "3",
      availability: "https://schema.org/OnlineOnly",
      url: absoluteUrl("/pricing"),
    },
    publisher: {
      "@id": absoluteUrl("/#organization"),
    },
  };
}

export function websiteJsonLd() {
  return {
    "@context": "https://schema.org",
    "@type": "WebSite",
    "@id": absoluteUrl("/#website"),
    name: siteConfig.name,
    url: siteConfig.url,
    description: siteConfig.description,
    publisher: {
      "@id": absoluteUrl("/#organization"),
    },
    inLanguage: "en-US",
  };
}

export function breadcrumbJsonLd(items: Array<{ name: string; path: string }>) {
  return {
    "@context": "https://schema.org",
    "@type": "BreadcrumbList",
    itemListElement: items.map((item, index) => ({
      "@type": "ListItem",
      position: index + 1,
      name: item.name,
      item: absoluteUrl(item.path),
    })),
  };
}
