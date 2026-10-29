// U.11: the verify page takes a dropped PDF or a request ID and shows a result card.
import { expect, test, type Page } from "@playwright/test";

const BLANK_PDF = `%PDF-1.4
1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj
2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj
3 0 obj<</Type/Page/Parent 2 0 R/MediaBox[0 0 200 200]>>endobj
trailer<</Root 1 0 R/Size 4>>
%%EOF`;

async function expectNoHorizontalScroll(page: Page) {
  const overflow = await page.evaluate(
    () => document.documentElement.scrollWidth - window.innerWidth,
  );
  expect(overflow).toBeLessThanOrEqual(0);
}

test("an unknown request ID shows a clear 'nothing found' card", async ({ page }) => {
  await page.goto("/sign-verify");
  await expect(page.getByRole("heading", { name: "Verify a signed document" })).toBeVisible();
  await page.getByLabel("Request ID").fill("SIGN-1999-99999");
  await page.getByRole("button", { name: "Verify" }).click();
  await expect(page.getByTestId("verify-bad")).toContainText("Nothing found");
  await expectNoHorizontalScroll(page);
  await page.screenshot({ path: "../e2e/test-results/verify-not-found-390.png", fullPage: true });
});

test("an empty submit asks for a file or an ID", async ({ page }) => {
  await page.goto("/sign-verify");
  await page.getByRole("button", { name: "Verify" }).click();
  await expect(page.getByTestId("verify-bad")).toContainText("Drop the signed PDF");
});

test("a PDF without a seal is reported as not sealed", async ({ page }) => {
  await page.goto("/sign-verify");
  await page.setInputFiles("#sign-verify-file", {
    name: "contract.pdf",
    mimeType: "application/pdf",
    buffer: Buffer.from(BLANK_PDF),
  });
  await expect(page.locator("#sv-file")).toContainText("contract.pdf");
  await page.getByRole("button", { name: "Verify" }).click();
  await expect(page.getByTestId("verify-bad")).toContainText("Not sealed");
  await page.screenshot({ path: "../e2e/test-results/verify-unsealed-390.png", fullPage: true });
  await page.setViewportSize({ width: 1440, height: 900 });
  await page.screenshot({ path: "../e2e/test-results/verify-unsealed-1440.png", fullPage: true });
  await page.getByRole("button", { name: "Remove" }).click();
  await expect(page.locator("#sv-file")).toBeHidden();
});
