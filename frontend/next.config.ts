import type { NextConfig } from "next";
import withPWAInit from "@ducanh2912/next-pwa";

const withPWA = withPWAInit({
  dest: "public",
  disable: process.env.NODE_ENV === "development",
  register: true,
});

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
};

export default withPWA(nextConfig);
