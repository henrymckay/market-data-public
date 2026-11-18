import { cloudflareTest } from "@cloudflare/vitest-pool-workers";
import { defineConfig } from "vitest/config";

export default defineConfig({
  plugins: [
    cloudflareTest({
      main: "./src/worker.ts",
      wrangler: { configPath: "./wrangler.toml" },
      // The pool bundles a workerd older than wrangler's; 2026-11-18 is beyond its newest date.
      miniflare: { compatibilityDate: "2026-08-15", bindings: { MOTHERDUCK_TOKEN: "test-token" } },
    }),
  ],
});
