import type { NextConfig } from "next";

// NEXT_PUBLIC_STATIC=1 → fully static export for GitHub Pages (no backend; TS engine + bundled snapshot).
const isStatic = process.env.NEXT_PUBLIC_STATIC === "1";
// GitHub project pages are served under /<repo>; override with NEXT_PUBLIC_BASE_PATH if needed.
const basePath = isStatic ? (process.env.NEXT_PUBLIC_BASE_PATH ?? "/market-risk-toolkit") : "";

const nextConfig: NextConfig = {
  reactStrictMode: true,
  ...(isStatic
    ? { output: "export", basePath, trailingSlash: true, images: { unoptimized: true } }
    : {}),
};

export default nextConfig;
