import type { NextConfig } from "next";
import withPWAInit from "@ducanh2912/next-pwa";

const withPWA = withPWAInit({
  dest: "public",
  disable: process.env.NODE_ENV === "development",
  register: true,
});

// Local backend target for Next.js development proxy rewrites.
// Override in frontend/.env if needed (example: BACKEND_ORIGIN=http://127.0.0.1:8000).
const BACKEND_ORIGIN = (process.env.BACKEND_ORIGIN || "http://localhost:8000").replace(/\/+$/, "");

const nextConfig: NextConfig = {
  // WHY: 'standalone' creates a self-contained build (copies only needed
  // node_modules files into .next/standalone). Required for Docker/ECS
  // deployment where we want a minimal image without full node_modules.
  output: "standalone",
  reactStrictMode: true,
  // WHY: Next.js 16 defaults to Turbopack. The PWA plugin adds webpack
  // config, so we need an explicit empty turbopack config to avoid the
  // "webpack config with no turbopack config" error.
  turbopack: {},
  // Allow images from Google auth avatars
  images: {
    remotePatterns: [
      {
        protocol: "https",
        hostname: "lh3.googleusercontent.com",
      },
    ],
  },
  async rewrites() {
    // WHY: Keep browser API calls same-origin (/api/v1) in local dev, then proxy
    // to FastAPI. This mirrors AWS ALB path routing and avoids CORS/localhost leaks.
    if (process.env.NODE_ENV !== "development") {
      return [];
    }
    return [
      {
        source: "/api/v1/:path*",
        destination: `${BACKEND_ORIGIN}/api/v1/:path*`,
      },
      {
        source: "/health",
        destination: `${BACKEND_ORIGIN}/health`,
      },
    ];
  },
};

export default withPWA(nextConfig);
