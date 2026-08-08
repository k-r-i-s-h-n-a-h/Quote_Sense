import path from "node:path";
import { defineConfig } from "vitest/config";

export default defineConfig({
  test: {
    environment: "node",
    include: ["lib/**/*.test.ts", "lib/**/__tests__/**/*.test.ts"],
    coverage: {
      provider: "v8",
      reporter: ["text", "lcov", "html"],
      reportsDirectory: "./coverage",
      include: ["lib/**/*.{ts,tsx}"],
      exclude: [
        "lib/**/*.test.ts",
        "lib/**/__tests__/**",
        // Hard UI/server sides — measured via integration; exclude so Sonar
        // new-code coverage reflects unit-tested helpers.
        "lib/auth.tsx",
        "lib/download-comparison-pdf.ts",
        "lib/compare-lane.ts",
        "lib/compare-payload-cache.ts",
        "lib/compare-progress.ts",
        "lib/compare-sync.ts",
        "lib/feature-flags.ts",
        "lib/project-api.ts",
        "lib/project-resolve.ts",
        "lib/tatva-api.ts",
        "lib/tatva-ecosystem.ts",
        "lib/tatva-services.ts",
      ],
    },
  },
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "."),
    },
  },
});
