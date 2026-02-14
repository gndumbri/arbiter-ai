import type { NextConfig } from "next";

const withPWA = require("@ducanh2912/next-pwa").default({
  dest: "public",
  disable: process.env.NODE_ENV === "development",
  register: true,
  skipWaiting: true,
});

const nextConfig: NextConfig = {
  output: "standalone",
  reactStrictMode: true,
  // Ensure images from Google/etc are allowed if using Auth avatars
  images: {
    domains: ["lh3.googleusercontent.com"], 
  },
};

export default withPWA(nextConfig);
