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
};

export default nextConfig;
