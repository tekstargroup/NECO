#!/usr/bin/env node
/**
 * Dev-auth Playwright storage state setup.
 * Visits /dev-login, clicks "Login as test user", saves cookies to storage state.
 * Requires: Frontend running with NEXT_PUBLIC_DEV_AUTH=true, backend with dev-token.
 */
import { chromium } from "@playwright/test";
import path from "path";
import { fileURLToPath } from "url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const baseUrl = process.env.FRONTEND_BASE_URL || "http://localhost:3001";
const outputPath =
  process.env.OUTPUT_PATH || path.join(__dirname, "../.auth/dev-auth-state.json");

async function main() {
  const headless = process.env.HEADLESS !== "0";
  const browser = await chromium.launch({ headless });
  const context = await browser.newContext({ baseURL: baseUrl });
  const page = await context.newPage();

  await page.goto("/dev-login", { waitUntil: "networkidle" });

  const button = page.getByRole("button", { name: /Login as test user/i });
  await button.waitFor({ state: "visible", timeout: 5000 });
  if (!headless) {
    await new Promise((r) => setTimeout(r, 3000));
  }
  await button.click();

  // Wait for either URL change or Shipments content
  try {
    await Promise.race([
      page.waitForURL(/\/app\/shipments/, { timeout: 25000 }),
      page.getByRole("heading", { name: "Shipments" }).waitFor({ state: "visible", timeout: 25000 }),
    ]);
  } catch (e) {
    const errText = await page.getByRole("alert").textContent().catch(() => null);
    const url = page.url();
    const screenshotPath = path.join(__dirname, "../.auth/dev-auth-failure.png");
    await page.screenshot({ path: screenshotPath }).catch(() => {});
    const hint = errText ? ` Page error: ${errText}` : "";
    if (!headless) {
      console.error("Keeping browser open 10s so you can inspect. Press Ctrl+C to exit early.");
      await new Promise((r) => setTimeout(r, 10000));
    }
    await browser.close();
    throw new Error(
      `Redirect to /app/shipments did not occur. Current URL: ${url}.${hint} Screenshot: ${screenshotPath}`
    );
  }

  await context.storageState({ path: outputPath });
  await browser.close();

  console.log(`Saved dev-auth state to ${outputPath}`);
}

main().catch((e) => {
  console.error("Dev-auth setup failed:", e.message);
  process.exit(1);
});
