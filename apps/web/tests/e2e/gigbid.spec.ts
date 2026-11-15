import { expect, test, type APIRequestContext, type Page } from "@playwright/test";

const API = "http://localhost:8000/api";
let n = 0;

/** A fresh user per test, created through the API and signed in by placing the session in the browser. */
async function freshUser(page: Page, request: APIRequestContext, onboard = true) {
  const username = `e2e-${Date.now().toString(36)}-${n++}`;
  const r = await request.post(`${API}/auth/signup`, { data: { username, password: "e2e-password" } });
  expect(r.ok()).toBeTruthy();
  const s = await r.json();
  const headers = { Authorization: `Bearer ${s.token}` };
  if (onboard) {
    const p = await request.put(`${API}/me/profile`, { headers, data: { persona: "ml", min_budget: 400 } });
    expect(p.ok()).toBeTruthy();
  }
  await page.addInitScript((value) => window.localStorage.setItem("gigbid_session", value), JSON.stringify({ ...s, onboarded: onboard }));
  return { username, headers };
}

/** From the inbox, analyse new jobs until one has a draft waiting, then open it in the studio. */
async function openADraft(page: Page) {
  await page.goto("/inbox");
  await expect(page.getByTestId("job-row").first()).toBeVisible();
  const review = page.getByTestId("open-studio").first();
  for (let round = 0; round < 3 && !(await review.isVisible()); round++) {
    await page.getByTestId("analyse-new").click();
    await review.waitFor({ state: "visible", timeout: 15_000 }).catch(() => undefined);
  }
  await review.click();
  await expect(page.getByRole("heading", { name: "Proposal studio" })).toBeVisible();
  await expect(page.getByTestId("draft-view")).toBeVisible();
}

test("onboarding: sign up, pick a persona, land in an inbox with jobs @phone", async ({ page }) => {
  await page.goto("/inbox");
  await expect(page).toHaveURL(/\/login/);
  await page.getByTestId("switch-auth").click();
  await page.getByLabel("User name").fill(`e2e-new-${Date.now().toString(36)}`);
  await page.getByLabel("Password").fill("e2e-password");
  await page.getByTestId("submit-auth").click();
  await expect(page).toHaveURL(/\/onboarding/);
  await expect(page.getByTestId("save-profile")).toBeDisabled();
  await page.getByTestId("persona-ml").check();
  await page.getByTestId("save-profile").click();
  await expect(page).toHaveURL(/\/inbox/);
  await expect(page.getByTestId("job-row").first()).toBeVisible();
});

test("approving a proposal: evidence on hover, dry run, approve, card on the pipeline", async ({ page, request }) => {
  await freshUser(page, request);
  await openADraft(page);
  const claim = page.getByTestId("claim").first();
  await claim.hover();
  await expect(claim.getByRole("tooltip")).toBeVisible();
  await expect(page.getByText("Connects cost")).toBeVisible();
  await page.reload(); // a refresh never loses the pending approval
  await expect(page.getByTestId("approve")).toBeVisible();
  await page.getByTestId("approve").click();
  await expect(page.getByTestId("submitted-note")).toBeVisible({ timeout: 20_000 });
  await page.goto("/pipeline");
  await expect(page.getByTestId("pipeline-card").first()).toBeVisible();
});

test("rejecting with a reason: the reason is required and nothing is sent", async ({ page, request }) => {
  await freshUser(page, request);
  await openADraft(page);
  await page.getByTestId("reject").click();
  await expect(page.getByTestId("confirm-reject")).toBeDisabled();
  await page.getByTestId("reject-reason").fill("the price is too low for this scope");
  await page.getByTestId("confirm-reject").click();
  await expect(page.getByTestId("rejected-note")).toBeVisible({ timeout: 20_000 });
  await page.goto("/pipeline");
  await expect(page.getByTestId("pipeline-card")).toHaveCount(0);
  await page.goto("/analytics");
  await expect(page.getByText("the price is too low for this scope")).toBeVisible();
});

test("editing a draft: the edited text is what gets submitted", async ({ page, request }) => {
  await freshUser(page, request);
  await openADraft(page);
  await page.getByTestId("edit").click();
  const box = page.getByTestId("edit-text");
  const original = await box.inputValue();
  const edited = original.split(". ").slice(1).join(". ");
  await box.fill(edited);
  await page.getByTestId("send-edit").click();
  await expect(page.getByTestId("submitted-note")).toBeVisible({ timeout: 20_000 });
  await expect(page.getByTestId("draft-view")).toContainText(edited.slice(0, 40));
  await expect(page.getByTestId("draft-view")).not.toContainText(original.split(". ")[0]);
});

test("degraded mode: a banner appears when the marketplace is down and goes when it is back @phone", async ({ page, request }) => {
  await freshUser(page, request);
  await page.goto("/inbox");
  await expect(page.getByTestId("job-row").first()).toBeVisible();
  await expect(page.getByTestId("degraded-banner")).toHaveCount(0);
  try {
    await request.post(`${API}/dev/marketplace?down=true`);
    await expect(page.getByTestId("degraded-banner")).toBeVisible({ timeout: 20_000 });
    await expect(page.getByTestId("degraded-banner")).toContainText("Marketplace unavailable");
  } finally {
    await request.post(`${API}/dev/marketplace?down=false`);
  }
  await expect(page.getByTestId("degraded-banner")).toHaveCount(0, { timeout: 20_000 });
});
