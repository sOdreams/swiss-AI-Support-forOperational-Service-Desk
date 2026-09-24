import { expect, test, type Page } from "@playwright/test";
import { readFile } from "node:fs/promises";

const tickets = [
  { "Issue ID": "1", "Issue Key": "ANALYSIS-1", Summary: "First outage", Description: "First access request; no outage.", "Work type": "Incident", "Affected Business or IT Services": ["Payments"], "All Comments": [] },
  { "Issue ID": "2", "Issue Key": "ANALYSIS-2", Summary: "Second ticket", Description: "Second request", "All Comments": [] },
];
function retrieval() {
  return { index_version: "test-index", model: "test-model", score_type: "cosine", hits: Array.from({ length: 50 }, (_, i) => ({
    document_id: `doc-${i}`, rank: i + 1, score: .9 - i / 100, summary: `Historical case ${i + 1}`,
    matched_text: "Unfiltered text with unselected remedies", historical_count: 3, evidence: [],
  })) };
}
function analysis(partial = false) {
  const original = retrieval();
  return { status: partial ? "partial" : "ready", model: "test-model", reasoning_effort: "low", cache_hit: false,
    elapsed_ms: 5000, compute_ms: 5000, timings: { clean_ms: 2000, retrieval_ms: 10, filter_ms: 4900 }, conflicts: [],
    clean: { status: "ready", reason: "The body requests access and explicitly denies an outage.", questions: [], fields: [
      { field: "summary", current: "First outage", suggested: "First access request", state: "propose_correction", evidence: [{ fact_id: "Q2", source: "description", text: "First access request; no outage." }] },
      { field: "work_type", current: "Incident", suggested: "Service Request", state: "propose_correction", evidence: [] },
    ] }, retrieval: original,
    filter: { status: partial ? "unfiltered_fallback" : "ready", reason: "Only the access-request analogue is primary.", service: "Archive", questions: [],
      candidates: original.hits.map((hit, i) => ({ ...hit, original_rank: hit.rank, filter_rank: !partial && i === 8 ? 1 : null,
        description: "Exact historical description", services: ["Archive"], role: partial ? "reserve" : i === 8 ? "primary" : "not_selected" })),
      primary_document_ids: partial ? [] : ["doc-8"], active_comment_ids: partial ? [] : ["E1"], comments: partial ? [] : [
        { id: "E1", text: "Resolution: Granted the approved role.", services: ["Archive"], status: "conditional",
          condition: "Verify the approved role before granting access.", reason: "Related provisioning procedure.", evidence: [],
          requires_current_verification: true, execution_authorized: false,
          sources: [{ document_id: "doc-4", original_rank: 5, occurrences: 3, examples: [] }] },
      ],
    },
  };
}
async function upload(page: Page) {
  await page.route("**/retrieval/search", (route) => route.fulfill({ json: retrieval() }));
  await page.goto("/");
  await page.locator('input[type="file"]').setInputFiles({ name: "tickets.json", mimeType: "application/json", buffer: Buffer.from(JSON.stringify(tickets)) });
  await page.getByRole("button", { name: /ANALYSIS-1/ }).first().click();
}

test("parallel analysis presents corrections, independent comments, all ranks and a copy-only preview", async ({ page }) => {
  await page.route("**/tickets/analyze", async (route) => {
    expect(route.request().postDataJSON()).toEqual({ summary: "First outage", description: "First access request; no outage.", comments: [], current_services: ["Payments"], current_work_type: "Incident" });
    await route.fulfill({ json: analysis() });
  });
  await upload(page);
  await page.getByRole("button", { name: "Clean & filter", exact: true }).click();
  const clean = page.getByRole("region", { name: "Ticket cleaning and filtering" });
  await expect(clean).toContainText("First access request");
  await expect(clean).toContainText("Service Request");
  const evidence = page.getByRole("region", { name: "Historical evidence", exact: true });
  await expect(evidence.locator(":scope > details")).toHaveCount(1);
  await expect(evidence).toContainText("9. Historical case 9");
  await expect(page.getByRole("region", { name: "Selected historical comments" })).toContainText("Verify the approved role");
  await expect(evidence).not.toContainText("Unfiltered text with unselected remedies");
  await evidence.getByRole("button", { name: "Show all 50 candidates" }).click();
  await expect(evidence.locator(":scope > details")).toHaveCount(50);
  const downloadStarted = page.waitForEvent("download");
  await page.getByRole("button", { name: "Download correction preview" }).click();
  const download = await downloadStarted;
  const preview = JSON.parse(await readFile((await download.path())!, "utf8"));
  expect(preview.ticket_preview.Summary).toBe("First access request");
  expect(preview.ticket_preview["Work type"]).toBe("Service Request");
  await expect(page.locator(".processor-ticket-hero h2")).toHaveText("First outage");
});

test("late analysis cannot replace a newly selected ticket", async ({ page }) => {
  let release: () => void = () => {};
  const gate = new Promise<void>((resolve) => { release = resolve; });
  await page.route("**/tickets/analyze", async (route) => {
    await gate;
    await route.fulfill({ json: analysis() }).catch(() => {});
  });
  await upload(page);
  const started = page.waitForRequest("**/tickets/analyze");
  await page.getByRole("button", { name: "Clean & filter", exact: true }).click();
  await started;
  await page.getByRole("button", { name: /ANALYSIS-2/ }).first().click();
  release();
  await expect(page.locator(".processor-ticket-hero h2")).toHaveText("Second ticket");
  const clean = page.getByRole("region", { name: "Ticket cleaning and filtering" });
  await expect(clean).not.toContainText("The body requests access");
  await expect(clean.getByRole("button", { name: "Clean & filter", exact: true })).toBeEnabled();
});

test("filter failure preserves corrections and the original 50 candidates", async ({ page }) => {
  await page.route("**/tickets/analyze", (route) => route.fulfill({ json: analysis(true) }));
  await upload(page);
  await page.getByRole("button", { name: "Clean & filter", exact: true }).click();
  const evidence = page.getByRole("region", { name: "Historical evidence", exact: true });
  await expect(evidence).toContainText("Filtering unavailable");
  await expect(evidence.locator(":scope > details")).toHaveCount(50);
  await expect(page.getByRole("region", { name: "Ticket cleaning and filtering" })).toContainText("Suggested correction");
});
