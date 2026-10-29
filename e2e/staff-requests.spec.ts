// U.4: the Sent page: tabs and counts, search, the preview and its actions, the old path, phones.
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

const rowOf = (page: Page, title: string) =>
  page.getByTestId("request-row").filter({ hasText: title });

test("the old path leads to Sent, with counts on the tabs", async ({
  page,
}) => {
  await login(page);
  await page.goto("/sign/envelopes");
  await expect(page).toHaveURL(/\/sign\/requests/);
  await expect(page.getByTestId("count-open")).toHaveText("3");
  await expect(page.getByTestId("count-completed")).toHaveText("1");
  await expect(page.getByTestId("count-closed")).toHaveText("1");
  await expect(page.getByTestId("count-all")).toHaveText("5");
  await page.screenshot({ path: "../e2e/test-results/sent-open.png" });

  // Waiting requests are grouped by who to chase; the draft has its own group.
  const list = page.getByTestId("request-list");
  await expect(list.locator('[data-group="outside"]')).toContainText(
    "E2E Supply Quotation",
  );
  await expect(list.locator('[data-group="team"]')).toContainText(
    "E2E Lease for Unit 4B",
  );
  await expect(list.locator('[data-group="draft"]')).toContainText(
    "E2E Draft Terms",
  );
  await expect(list.locator('[data-group="done"]')).toHaveCount(0);

  // The progress lane lines up from row to row.
  const lanes = await page
    .getByTestId("lane-progress")
    .evaluateAll((nodes) =>
      nodes.map((node) => Math.round(node.getBoundingClientRect().right)),
    );
  expect(new Set(lanes).size).toBe(1);

  await page.getByTestId("pill-completed").click();
  await expect(rowOf(page, "E2E Signed Order")).toBeVisible();
  await expect(page).toHaveURL(/status=completed/);
  await page.getByTestId("pill-closed").click();
  await expect(rowOf(page, "E2E Declined Offer")).toBeVisible();
});

test("search finds a request by its title or by a person, and clears", async ({
  page,
}) => {
  await login(page);
  await page.goto("/sign/requests?status=all");
  await expect(page.getByTestId("request-row")).toHaveCount(5);

  await page.getByTestId("search").fill("Lease");
  await expect(page.getByTestId("request-row")).toHaveCount(1);
  await expect(page.getByTestId("count-all")).toHaveText("1");

  await page.getByTestId("search").fill("ahmed@example.com");
  await expect(page.getByTestId("request-row")).toHaveCount(4);

  await page.getByTestId("search").fill("nobody at all");
  await expect(page.getByText("No requests match")).toBeVisible();
  await page.getByRole("button", { name: "Clear search" }).click();
  await expect(page.getByTestId("request-row")).toHaveCount(5);
});

test("the preview shows people and activity, reminds, and voids with a reason", async ({
  page,
}) => {
  await login(page);
  await page.goto("/sign/requests");
  await rowOf(page, "E2E Supply Quotation").click();

  const preview = page.getByTestId("request-preview");
  await expect(preview.getByTestId("preview-title")).toHaveText(
    "E2E Supply Quotation",
  );
  await expect(preview.getByTestId("person")).toHaveCount(2);
  await expect(preview.getByTestId("person").first()).toContainText(
    "Ahmed Khan",
  );
  await expect(preview.getByTestId("person").first()).toContainText(
    "Not opened yet",
  );
  await expect(preview.getByTestId("activity")).toContainText(
    "The request was sent",
  );
  await page.screenshot({ path: "../e2e/test-results/sent-preview.png" });

  // Audit details sit behind a toggle.
  await preview.getByRole("button", { name: "Show audit details" }).click();
  await expect(preview.getByTestId("audit")).toContainText("Delivered");
  await preview.getByRole("button", { name: "Hide audit details" }).click();

  await preview.getByTestId("primary-action").click();
  await expect(page.getByText("Reminder sent")).toBeVisible();

  // Void needs a reason; then the request moves to Closed.
  await preview.getByTestId("more-actions").click();
  await page.getByRole("menuitem", { name: "Void request" }).click();
  const dialog = page.getByRole("dialog");
  await dialog.getByRole("button", { name: "Void request" }).click();
  await expect(dialog).toContainText(/required|reason/i);
  await dialog.getByLabel("Reason").fill("Prices changed");
  await dialog.getByRole("button", { name: "Void request" }).click();
  await expect(page.getByText("Request voided")).toBeVisible();
  await expect(rowOf(page, "E2E Supply Quotation")).toHaveCount(0);
  await expect(page.getByTestId("count-closed")).toHaveText("2");
});

test("a completed request offers the signed PDF, a draft offers Send", async ({
  page,
}) => {
  await login(page);
  await page.goto("/sign/requests?status=completed");
  await rowOf(page, "E2E Signed Order").click();
  await expect(page.getByTestId("primary-action")).toContainText(
    "Download signed PDF",
  );

  await page.goto("/sign/requests");
  await rowOf(page, "E2E Draft Terms").click();
  await expect(page.getByTestId("primary-action")).toHaveText(/Send/);
});

test("on a phone a tap opens the request, and nothing scrolls sideways", async ({
  page,
}) => {
  await login(page);
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto("/sign/requests");
  await expect(page.getByTestId("request-list")).toBeVisible();
  await expect(page.getByTestId("request-preview")).toHaveCount(0);
  const overflow = await page.evaluate(
    () => document.documentElement.scrollWidth - window.innerWidth,
  );
  expect(overflow).toBeLessThanOrEqual(0);
  await page.screenshot({ path: "../e2e/test-results/sent-390.png" });

  await rowOf(page, "E2E Lease for Unit 4B").click();
  await expect(page).toHaveURL(/\/sign\/requests\/SIGN-/);
  await expect(page.getByTestId("envelope-detail")).toBeVisible();
});
