/**
 * Next.js configuration for the LeadForge frontend.
 *
 * The app is exported statically so it can be embedded into the FastAPI
 * production container or hosted separately on static platforms.
 */

import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  output: "export",
  trailingSlash: true,
  images: {
    unoptimized: true,
  },
};

export default nextConfig;
