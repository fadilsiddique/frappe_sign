// P1.14: a signer completes a fixture envelope on a 390 px wide phone screen.
import { expect, test, type Page } from "@playwright/test";
import { benchExecute, type EnvelopeState, type GuestEnvelope } from "./bench";
import { drawSignature } from "./signature-pad";

let fixture: GuestEnvelope;

test.beforeAll(() => {
  fixture = benchExecute<GuestEnvelope>("create_guest_envelope");
});

test.afterAll(() => {
  if (fixture)
    benchExecute(
      "purge",
      { envelope: fixture.envelope, started: fixture.started },
      5,
    );
});

async function expectNoHorizontalScroll(page: Page) {
  const overflow = await page.evaluate(
    () => document.documentElement.scrollWidth - window.innerWidth,
  );
  expect(overflow).toBeLessThanOrEqual(0);
}

test("signs a fixture envelope at 390 px width", async ({ page }) => {
  await page.goto(`/s/${fixture.token}`);

  // Review and consent.
  await expect(page.getByTestId("consent")).toBeVisible();
  await expect(page.getByTestId("guest-header")).toBeVisible();
  await expect(
    page.getByRole("heading", { name: "E2E Service Agreement" }),
  ).toBeVisible();
  await expectNoHorizontalScroll(page);
  // The button stays off until the box is ticked.
  await expect(page.getByTestId("start")).toBeDisabled();
  await page.screenshot({ path: "../e2e/test-results/guest-consent-390.png" });
  await page.getByTestId("agree").check();
  await expect(page.getByTestId("start")).toBeEnabled();
  await page.getByTestId("start").click();

  // The document with this signer's fields over it.
  await expect(page.getByTestId("sign")).toBeVisible();
  await expect(page.locator('[data-field="customer_signature"]')).toBeVisible();
  await expect(page.locator('[data-field="company_signature"]')).toHaveCount(0);
  await expect(page.locator("canvas").first()).toBeVisible();
  await expect(page.getByTestId("progress")).toContainText("0 of 1 done");
  await expect(page.getByRole("progressbar")).toHaveAttribute(
    "aria-valuenow",
    "0",
  );
  await expectNoHorizontalScroll(page);

  // Decline and delegate sit behind the More menu.
  await page.getByTestId("more").click();
  await expect(page.getByTestId("open-decline")).toBeVisible();
  await page.keyboard.press("Escape");
  await page.mouse.click(10, 300);

  // "Next: Signature" jumps to the signature and opens the bottom sheet.
  await expect(page.getByTestId("next")).toContainText("Signature");
  await page.getByTestId("next").click();
  await expect(page.getByTestId("signature-sheet")).toBeVisible();
  // A stroke that starts while the sheet slides in must not close it.
  await drawSignature(page);
  await expect(page.getByTestId("signature-sheet")).toBeVisible();
  await page.getByTestId("save-signature").click();
  await expect(page.getByTestId("signature-sheet")).toBeHidden();
  await expect(
    page.locator('[data-field="customer_signature"]'),
  ).toHaveAttribute("data-done", "1");
  await page.screenshot({ path: "../e2e/test-results/guest-sign-390.png" });

  await expect(page.getByRole("progressbar")).toHaveAttribute(
    "aria-valuenow",
    "1",
  );

  // Review what was filled, then finish.
  await page.getByTestId("finish").click();
  await expect(page.getByTestId("review-list")).toContainText("Signature");
  await page.waitForTimeout(800);
  await page.screenshot({ path: "../e2e/test-results/guest-review-390.png" });
  await page.getByTestId("confirm-finish").click();
  await expect(page.getByTestId("terminal")).toHaveAttribute(
    "data-screen",
    "signed",
  );
  await expect(
    page.getByRole("heading", { name: "You signed E2E Service Agreement" }),
  ).toBeVisible();
  await expectNoHorizontalScroll(page);
  await page.screenshot({ path: "../e2e/test-results/guest-done-390.png" });

  const state = benchExecute<EnvelopeState>("envelope_state", {
    envelope: fixture.envelope,
  });
  expect(state.status).toBe("In Progress");
  expect(state.recipients).toEqual({ Customer: "Signed", Company: "Sent" });
  expect(state.fields.customer_signature).toBe(true);
  expect(state.fields.customer_name).toBe(true);

  // The same link now shows the "already signed" screen.
  await page.goto(`/s/${fixture.token}`);
  await expect(page.getByTestId("terminal")).toHaveAttribute(
    "data-screen",
    "already",
  );
});

test("an unknown link shows the expired screen", async ({ page }) => {
  await page.goto("/s/not-a-real-token");
  await expect(page.getByTestId("terminal")).toHaveAttribute(
    "data-screen",
    "expired",
  );
  await expectNoHorizontalScroll(page);
});
