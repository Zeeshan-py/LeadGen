import type { MetadataRoute } from "next";

import { absoluteUrl, publicPages } from "@/lib/seo";

export const dynamic = "force-static";

const lastModified = new Date("2026-07-29T00:00:00.000Z");

export default function sitemap(): MetadataRoute.Sitemap {
  return publicPages.map((page) => ({
    url: absoluteUrl(page.path),
    lastModified,
    changeFrequency: page.changeFrequency,
    priority: page.sitemapPriority,
  }));
}
