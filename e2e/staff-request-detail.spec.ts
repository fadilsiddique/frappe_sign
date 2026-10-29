// U.5: the request page: the PDF beside the people, the action for the state, plain activity.
import { expect, test, type Page } from "@playwright/test";
import { benchExecute } from "./bench";

const ADMIN_PASSWORD = process.env.E2E_ADMIN_PASSWORD ?? "admin";

interface SentRequests {
  customer: string;
  team: string;
  draft: string;
  done: string;
  declined: string;
  started: string;
}
let fixture: SentRequests;

test.beforeAll(() => {
  fixture = benchExecute<SentRequests>("create_sent_requests");
});
test.afterAll(() => {
  if (fixture) benchExecute("purge_created", { started: fixture.started }, 5);
});

async function login(page: Page) {
  const response = await page.request.post("/api/method/login", {
    data: { usr: "Administrator", pwd: ADMIN_PASSWORD },
  });
  expect(response.ok()).toBeTruthy();
}

test("a waiting request shows the document, the people and Remind", async ({ page }) => {
  await login(page);
  await page.setViewportSize({ width: 1440, height: 900 });
  await page.goto(`/sign/requests/${fixture.customer}`);

  await expect(page.getByTestId("detail-title")).toHaveText("E2E Supply Quotation");
  await expect(page.getByTestId("detail-pdf").locator("canvas").first()).toBeVisible();
  const people = page.getByTestId("person");
  await expect(people).toHaveCount(2);
  await expect(people.first()).toContainText("Ahmed Khan");
  await expect(people.first()).toContainText("Not opened yet");
  await expect(page.getByTestId("activity")).toContainText("The request was sent");
  await expect(page.getByTestId("chain")).toHaveAttribute("aria-label", "Verified");

  // The PDF sits left of the panel.
  const pdf = await page.getByTestId("detail-pdf").boundingBox();
  const panel = await page.getByLabel("Request details").boundingBox();
  expect(pdf!.x + pdf!.width).toBeLessThanOrEqual(panel!.x);
  await page.screenshot({ path: "../e2e/test-results/detail-waiting.png" });

  // Audit details sit behind a toggle.
  await expect(page.getByTestId("audit")).toHaveCount(0);
  await page.getByRole("button", { name: "Show audit details" }).click();
  await expect(page.getByTestId("audit")).toContainText("Delivered");

  await page.getByTestId("primary-action").click();
  await expect(page.getByText("Reminder sent")).toBeVisible();
});

test("a completed request offers the signed PDF", async ({ page }) => {
  await login(page);
  await page.goto(`/sign/requests/${fixture.done}`);
  await expect(page.getByTestId("detail-title")).toHaveText("E2E Signed Order");
  await expect(page.getByTestId("primary-action")).toContainText("Download signed PDF");
  await expect(page.getByText("Waiting", { exact: true })).toHaveCount(0);
});

test("on a phone the details come first and nothing scrolls sideways", async ({ page }) => {
  await login(page);
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto(`/sign/requests/${fixture.customer}`);
  await expect(page.getByTestId("detail-title")).toBeVisible();
  const title = await page.getByTestId("detail-title").boundingBox();
  const pdf = await page.getByTestId("detail-pdf").boundingBox();
  expect(title!.y).toBeLessThan(pdf!.y);
  const overflow = await page.evaluate(
    () => document.documentElement.scrollWidth - window.innerWidth,
  );
  expect(overflow).toBeLessThanOrEqual(0);
  await page.screenshot({ path: "../e2e/test-results/detail-390.png" });
});
