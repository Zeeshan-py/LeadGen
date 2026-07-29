import type { MetadataRoute } from "next";

import { absoluteUrl, privateAppPaths } from "@/lib/seo";

export const dynamic = "force-static";

const privateRoutes = privateAppPaths.flatMap((path) => [path, `${path}/`]);

const backendRoutes = [
  "/api",
  "/api/",
  "/auth",
  "/auth/",
  "/gmail",
  "/gmail/",
  "/twilio",
  "/twilio/",
  "/generate-leads",
  "/generate-leads/",
  "/get-leads",
  "/get-leads/",
  "/get-campaigns",
  "/get-campaigns/",
  "/send-email",
  "/send-email/",
  "/health",
  "/health/",
  "/static/screenshots",
  "/static/screenshots/",
];

export default function robots(): MetadataRoute.Robots {
  return {
    rules: [
      {
        userAgent: "*",
        allow: "/",
        disallow: [
          ...privateRoutes,
          "/reset-password/",
          ...backendRoutes,
        ],
      },
    ],
    sitemap: absoluteUrl("/sitemap.xml"),
    host: "https://leadforage.pro",
  };
}
