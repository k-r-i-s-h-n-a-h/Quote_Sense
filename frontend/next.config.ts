import type { NextConfig } from "next";
import path from "path";

const nextConfig: NextConfig = {
  // Home-dir package-lock.json was confusing Turbopack's workspace root inference.
  turbopack: {
    root: path.join(__dirname),
  },
  // Recharts 3 pulls react-redux, which does `import * as React` then reads
  // React.version. Next 16 webpack does not re-export that named binding.
  transpilePackages: ["recharts", "react-redux"],
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
