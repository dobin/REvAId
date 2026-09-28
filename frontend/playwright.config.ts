import { defineConfig } from "@playwright/test";

export default defineConfig({
  testDir: "./e2e",
  fullyParallel: true,
  reporter: "list",
  use: {
    baseURL: process.env.GRAPHREV_E2E_BASE_URL ?? "http://127.0.0.1:5173",
    trace: "on-first-retry",
  },
  ...(process.env.GRAPHREV_E2E_EXTERNAL === "1"
    ? {}
    : {
        webServer: {
          command: "npm run dev",
          url: "http://127.0.0.1:5173",
          reuseExistingServer: true,
        },
      }),
});
