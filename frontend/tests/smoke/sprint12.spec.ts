import { expect, test } from "@playwright/test";

function newShipmentName(): string {
  return `QA Loop Shipment ${Date.now()}`;
}

async function assertAppContext(page: import("@playwright/test").Page) {
  const url = page.url();
  expect(
    url,
    `Auth state not active. Current URL=${url}. Verify PLAYWRIGHT_STORAGE_STATE and FRONTEND_BASE_URL alignment.`,
  ).not.toContain("/sign-in");
}

async function gotoStable(page: import("@playwright/test").Page, path: string) {
  const runtimeFallbackMarkers = [
    "missing required error components",
    "Application error: a client-side exception has occurred",
    "Something went wrong!",
  ];
  let lastMarker = "";

  for (let i = 0; i < 5; i++) {
    await page.goto(path, { waitUntil: "domcontentloaded" });

    let matchedMarker = "";
    for (const marker of runtimeFallbackMarkers) {
      const hasMarker = await page.getByText(marker, { exact: false }).isVisible({ timeout: 1_500 }).catch(() => false);
      if (hasMarker) {
        matchedMarker = marker;
        break;
      }
    }

    if (!matchedMarker) {
      return;
    }

    lastMarker = matchedMarker;
    await page.waitForTimeout(2_000);
  }

  throw new Error(
    `Frontend runtime remained unstable on ${path} after retries (marker: ${lastMarker || "unknown"}). Check frontend env/API base and startup health.`,
  );
}

async function createShipmentAndWaitForRedirect(page: import("@playwright/test").Page, name: string) {
  const nameInput = page.locator("#name");
  const createButton = page.getByRole("button", { name: "Create Shipment" });

  for (let attempt = 1; attempt <= 3; attempt++) {
    await expect(createButton).toBeEnabled({ timeout: 30_000 });
    await nameInput.fill(name);
    await expect(nameInput).toHaveValue(name, { timeout: 10_000 });
    await createButton.click();

    try {
      await expect(page).toHaveURL(/\/app\/shipments\/[0-9a-f-]+/i, { timeout: 10_000 });
      return;
    } catch (error) {
      const currentUrl = page.url();
      if (!currentUrl.includes("/app/shipments/new") || attempt === 3) {
        throw new Error(
          `Create shipment did not redirect after ${attempt} attempt(s). URL=${currentUrl}. Name input may be resetting during auth/runtime hydration.`,
        );
      }
    }
  }
}

test("shipments list loads under authenticated org", async ({ page }) => {
  await gotoStable(page, "/app/shipments");
  await assertAppContext(page);
  await expect(page.getByRole("heading", { name: "Shipments" })).toBeVisible();
  await expect(page.getByRole("button", { name: "New Shipment" })).toBeVisible();
});

test("create shipment redirects to detail page", async ({ page }) => {
  await gotoStable(page, "/app/shipments/new");
  await assertAppContext(page);

  const name = newShipmentName();
  await expect(page.locator("#name")).toBeVisible({ timeout: 30_000 });
  await createShipmentAndWaitForRedirect(page, name);
  // Detail page loads shipment async; wait for heading (shipment name)
  await expect(page.getByRole("heading", { name })).toBeVisible({ timeout: 20_000 });
  await expect(page.getByRole("button", { name: "Overview" })).toBeVisible();
});
