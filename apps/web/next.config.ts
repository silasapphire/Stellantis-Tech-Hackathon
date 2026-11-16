import type { NextConfig } from "next";
import path from "path";

const nextConfig: NextConfig = {
  // NEXT_DIST_DIR lets a production build run without clobbering a running `next dev` (.next).
  distDir: process.env.NEXT_DIST_DIR || ".next",
  turbopack: {
    root: path.join(__dirname),
  },
};

export default nextConfig;
