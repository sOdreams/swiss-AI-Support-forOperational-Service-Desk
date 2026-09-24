import { expect, test, type Page } from "@playwright/test";

const tickets = [
  { "Issue ID": "1", "Issue Key": "TEST-1", Summary: "First ticket", Description: "First description", "All Comments": ["alice@example.com: First note"] },
  { "Issue ID": "2", "Issue Key": "TEST-2", Summary: "Second ticket", Description: "Second description", "All Comments": [] },
];

function response(prefix: string) {
  return { index_version: "test-index", model: "test-model", score_type: "cosine", hits: Array.from({ length: 50 }, (_, i) => ({
    document_id: `${prefix}-${i}`, rank: i + 1, score: 0.9 - i / 100,
    summary: `${prefix} evidence ${i + 1}`, matched_text: `Historical text ${i + 1}`, historical_count: 20,
    evidence: [{ body: "Resolution: A historical action", occurrences: 5, sources: [{ row_index: 10, ticket_id: "HISTORY-10", comment_index: 0, author: "alice@example.com", services: ["Email"], teams: ["Support"] }] }],
  })) };
}

async function upload(page: Page) {
  await page.goto("/");
  await page.locator('input[type="file"]').setInputFiles({ name: "tickets.json", mimeType: "application/json", buffer: Buffer.from(JSON.stringify(tickets)) });
  await page.getByRole("button", { name: /TEST-1/ }).first().click();
}

test("shows 50 ranked groups and submits selected evidence provenance", async ({ page }) => {
  await page.route("**/retrieval/search", async (route) => {
    expect(route.request().postDataJSON()).toEqual({ summary: "First ticket", description: "First description", comments: ["First note"], top_k: 50 });
    await route.fulfill({ json: response("first") });
  });
  await page.route("**/tickets/process", (route) => route.fulfill({ status: 201, json: { saved: true } }));
  await upload(page);
  const panel = page.getByRole("region", { name: "Historical evidence" });
  await expect(panel.locator(":scope > details")).toHaveCount(50);
  await expect(panel.locator(":scope > details").last().locator("summary").first()).toContainText("50. first evidence 50");
  await panel.locator(":scope > details").first().locator("summary").first().click();
  await panel.getByRole("checkbox").first().check();
  await page.getByLabel("1.2 Real solution").fill("Verified the actual fix");
  await page.getByRole("button", { name: /Service continuity/ }).click();
  const sent = page.waitForRequest("**/tickets/process");
  await page.getByRole("button", { name: "Send", exact: true }).click();
  const payload = (await sent).postDataJSON();
  expect(payload.retrieval.selected_document_ids).toEqual(["first-0"]);
  expect(payload.retrieval.shown_document_ids).toHaveLength(50);
  expect(payload.retrieval.index_version).toBe("test-index");
});

test("late response for the previous ticket cannot replace current evidence", async ({ page }) => {
  let releaseFirst: () => void = () => {};
  const firstGate = new Promise<void>((resolve) => { releaseFirst = resolve; });
  await page.route("**/retrieval/search", async (route) => {
    const first = route.request().postDataJSON().summary === "First ticket";
    if (first) await firstGate;
    await route.fulfill({ json: response(first ? "first" : "second") }).catch(() => {});
  });
  const firstStarted = page.waitForRequest("**/retrieval/search");
  await upload(page);
  await firstStarted;
  await page.getByRole("button", { name: /TEST-2/ }).first().click();
  const panel = page.getByRole("region", { name: "Historical evidence" });
  await expect(panel).toContainText("second evidence 1");
  releaseFirst();
  await expect(panel).not.toContainText("first evidence");
  await expect(panel.locator(":scope > details")).toHaveCount(50);
});

test("retrieval errors still allow an actual solution to be recorded", async ({ page }) => {
  await page.route("**/retrieval/search", (route) => route.fulfill({ status: 503, json: { detail: "Unavailable" } }));
  await upload(page);
  await expect(page.getByRole("alert")).toContainText("Historical evidence unavailable");
  await expect(page.getByLabel("1.2 Real solution")).toBeEditable();
});
