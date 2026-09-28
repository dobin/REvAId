import { expect, test } from "@playwright/test";

test("SPA uses the viewer origin to explore analysis data", async ({ page }) => {
  const browserApiOrigins = new Set<string>();
  page.on("request", (request) => {
    if (new URL(request.url()).pathname.startsWith("/api/")) {
      browserApiOrigins.add(new URL(request.url()).origin);
    }
  });

  await page.goto("/");
  await expect(page.getByRole("heading", { name: "Binaries" })).toBeVisible();
  const binaryRow = page.getByRole("row").filter({ hasText: "acme.exe" });
  await expect(binaryRow).toBeVisible();
  await binaryRow.getByRole("button", { name: "Open" }).click();

  const search = page.getByRole("textbox", { name: "Search functions" });
  await expect(search).toBeVisible();
  await search.fill("main");
  const result = page.getByRole("option").filter({ hasText: "main" });
  await expect(result).toBeVisible();
  await result.click();
  await expect(page.getByRole("button", { name: "Hide details for main" })).toBeVisible();

  expect([...browserApiOrigins]).toEqual([new URL(page.url()).origin]);
});
