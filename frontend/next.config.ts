import type { NextConfig } from "next";
import path from "path";

const nextConfig: NextConfig = {
  // Home-dir package-lock.json was confusing Turbopack's workspace root inference.
  turbopack: {
    root: path.join(__dirname),
  },
  images: {
    remotePatterns: [
      {
        protocol: "https",
        hostname: "tatvaops.com",
        pathname: "/**",
      },
    ],
  },
  // iCloud / network drives: polling watchers + lighter source maps avoid hung compiles.
  webpack: (config, { dev }) => {
    if (dev) {
      config.watchOptions = {
        poll: 2000,
        aggregateTimeout: 500,
        ignored: ["**/node_modules/**", "**/.git/**"],
      };
      config.devtool = "eval-cheap-module-source-map";
    }
    return config;
  },
};

export default nextConfig;
