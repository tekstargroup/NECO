import { defineConfig, devices } from "@playwright/test";

const frontendBaseUrl = process.env.FRONTEND_BASE_URL || "http://localhost:3001";
const storageState = process.env.PLAYWRIGHT_STORAGE_STATE || ".auth/clerk-state.json";

export default defineConfig({
  testDir: "./tests/smoke",
  timeout: 60_000,
  expect: {
    timeout: 15_000,
  },
  fullyParallel: false,
  workers: 1,
  reporter: [["list"], ["html", { outputFolder: "../output/playwright-report", open: "never" }]],
  use: {
    baseURL: frontendBaseUrl,
    headless: true,
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
    video: "retain-on-failure",
    storageState,
  },
  projects: [
    {
      name: "chromium",
      use: { ...devices["Desktop Chrome"] },
    },
  ],
});
