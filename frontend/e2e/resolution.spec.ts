import { expect, test, type Page } from "@playwright/test";

const tickets = [
  { "Issue ID": "1", "Issue Key": "RESOLVE-1", Summary: "Archive access request", Description: "Please grant the approved Archive role.", "All Comments": [] },
  { "Issue ID": "2", "Issue Key": "RESOLVE-2", Summary: "Another request", Description: "Another description", "All Comments": [] },
];
function analysis() {
  const retrieval = { index_version: "test-index", model: "test-embedding", score_type: "cosine", hits: Array.from({ length: 50 }, (_, i) => ({
    document_id: `doc-${i}`, rank: i + 1, score: .9 - i / 100, summary: `Historical case ${i + 1}`,
    matched_text: "Original indexed text", historical_count: 2, evidence: [],
  })) };
  return { status: "ready", model: "test-model", reasoning_effort: "none", cache_hit: false, elapsed_ms: 4000, compute_ms: 4000,
    timings: { clean_ms: 1000, retrieval_ms: 10, filter_ms: 3900 }, conflicts: [],
    clean: { status: "ready", reason: "A standard access request.", fields: [], questions: [] }, retrieval,
    filter: { status: "ready", candidates: retrieval.hits.map((hit, i) => ({ ...hit, original_rank: hit.rank,
      filter_rank: i === 0 ? 1 : null, role: i === 0 ? "primary" : "not_selected", description: "An access request", services: ["Archive"] })),
      comments: [], primary_document_ids: ["doc-0"], active_comment_ids: [], questions: [], reason: "Same access workflow.", service: "Archive" },
  };
}
function resolved(questionOnly = false) {
  return { ...analysis(), analysis_cache_hit: true, resolution: {
    status: "ready", proposal_id: "proposal-1", mode: questionOnly ? "needs_information" : "action_plan",
    actions: questionOnly ? [] : ["Verify the approved role.", "Provision the approved access.", "Ask the requester to verify access."].map((text, i) => ({
      id: `A${i + 1}`, kind: i === 1 ? "procedure" : "diagnostic", next_step: text, reason: "Related to the current access request.",
      check_first: null, expected_outcome: null, fact_ids: ["Q1"], source_ids: ["E1"],
      sources: [{ id: "E1", kind: "historical_comment", text: "Resolution: Granted the approved role.",
        condition: "Confirm the documented approval before provisioning.", sources: [{ document_id: "doc-8", original_rank: 9, occurrences: 2, examples: [] }] }],
      required_checks: ["Confirm the documented approval before provisioning."], execution_authorized: false,
    })), critical_question: "Which approval record covers the requested role?", reply_draft: "Please share the approval record so the requested access can be checked.",
    model: "test-model", index_version: "test-index", ticket_fingerprint: "test-fingerprint", requires_review: true, execution_authorized: false,
  } };
}
async function openTicket(page: Page) {
  await page.route("**/retrieval/search", (route) => route.fulfill({ json: analysis().retrieval }));
  await page.route("**/tickets/analyze", (route) => route.fulfill({ json: analysis() }));
  await page.goto("/");
  await page.locator('input[type="file"]').setInputFiles({ name: "tickets.json", mimeType: "application/json", buffer: Buffer.from(JSON.stringify(tickets)) });
  await page.getByRole("button", { name: /RESOLVE-1/ }).first().click();
  await expect(page.getByRole("button", { name: "Generate next steps" })).toBeDisabled();
  await page.getByRole("button", { name: "Clean & filter", exact: true }).click();
  await expect(page.getByRole("button", { name: "Generate next steps" })).toBeEnabled();
}

test("action choices, source checks, draft edits and actual outcomes are submitted separately", async ({ page }) => {
  let resolveCalls = 0;
  await page.route("**/tickets/resolve", (route) => {
    resolveCalls++;
    expect(route.request().postDataJSON()).not.toHaveProperty("analysis");
    return route.fulfill({ json: resolved() });
  });
  await page.route("**/tickets/process", (route) => route.fulfill({ status: 201, json: { saved: true } }));
  await openTicket(page);
  await page.getByRole("button", { name: "Generate next steps" }).click();
  const panel = page.getByRole("region", { name: "Resolution assistance" });
  await expect(panel.getByRole("article")).toHaveCount(3);
  const first = panel.getByRole("article", { name: "Action 1", exact: true });
  await expect(first).toContainText("Confirm the documented approval");
  await expect(first).toContainText("A verification criterion is not established");
  await first.locator("summary").click();
  await expect(first).toContainText("Original ranks: 9");
  await first.getByRole("button", { name: "Use", exact: true }).click();
  const second = panel.getByRole("article", { name: "Action 2", exact: true });
  await second.getByRole("button", { name: "Edit", exact: true }).click();
  await second.getByLabel("Edit action 2").fill("Provision only the approved read-only role.");
  await panel.getByRole("article", { name: "Action 3", exact: true }).getByRole("button", { name: "Not applicable" }).click();
  await panel.getByLabel("Reply draft").fill("Please confirm the approval record for read-only access.");
  await page.getByRole("button", { name: /Service continuity/ }).click();
  await expect(page.getByRole("button", { name: "Send", exact: true })).toBeDisabled();
  await expect(panel.getByLabel("Actual action and outcome")).toHaveValue("");
  await panel.getByLabel("Actual action and outcome").fill("Requested approval evidence; access has not been changed.");
  const sent = page.waitForRequest("**/tickets/process");
  await page.getByRole("button", { name: "Send", exact: true }).click();
  const payload = (await sent).postDataJSON();
  expect(resolveCalls).toBe(1);
  expect(payload.resolution.actions.map((item: { decision: string }) => item.decision)).toEqual(["use", "edit", "not_applicable"]);
  expect(payload.resolution.proposal.actions[1].next_step).toBe("Provision the approved access.");
  expect(payload.resolution.proposal.actions[1].required_checks).toHaveLength(1);
  expect(payload.resolution.reply_draft).toContain("read-only access");
  expect(payload.recommended_solution).toContain("read-only role");
  expect(payload.recommended_solution).not.toContain("Ask the requester");
  expect(payload.resolution.actual_outcome).toBe(payload.real_solution);
  expect(payload.retrieval.shown_document_ids).toHaveLength(50);
});

test("insufficient evidence presents one question without fabricating action cards", async ({ page }) => {
  await page.route("**/tickets/resolve", (route) => route.fulfill({ json: resolved(true) }));
  await openTicket(page);
  await page.getByRole("button", { name: "Generate next steps" }).click();
  const panel = page.getByRole("region", { name: "Resolution assistance" });
  await expect(panel).toContainText("Clarification needed");
  await expect(panel).toContainText("Which approval record");
  await expect(panel.getByRole("article")).toHaveCount(0);
  await expect(panel.getByLabel("Reply draft")).toBeEditable();
});

test("resolve failure retains evidence and manual outcome entry", async ({ page }) => {
  await page.route("**/tickets/resolve", (route) => route.fulfill({ json: { ...analysis(), status: "partial", analysis_cache_hit: true,
    resolution: { status: "unavailable", actions: [], critical_question: null, reply_draft: "", reason: "Next-step suggestions unavailable." } } }));
  await openTicket(page);
  await page.getByRole("button", { name: "Generate next steps" }).click();
  await expect(page.getByRole("region", { name: "Resolution assistance" })).toContainText("Next-step suggestions unavailable");
  await expect(page.getByLabel("1.2 Real solution")).toBeEditable();
  const evidence = page.getByRole("region", { name: "Historical evidence", exact: true });
  await evidence.getByRole("button", { name: "Show all 50 candidates" }).click();
  await expect(evidence.locator(":scope > details")).toHaveCount(50);
});

test("a late resolve response cannot attach a proposal to another ticket", async ({ page }) => {
  let release: () => void = () => {};
  const pending = new Promise<void>((resolve) => { release = resolve; });
  await page.route("**/tickets/resolve", async (route) => { await pending; await route.fulfill({ json: resolved() }).catch(() => {}); });
  await openTicket(page);
  const started = page.waitForRequest("**/tickets/resolve");
  await page.getByRole("button", { name: "Generate next steps" }).click();
  await started;
  await page.getByRole("button", { name: /RESOLVE-2/ }).first().click();
  release();
  await expect(page.locator(".processor-ticket-hero h2")).toHaveText("Another request");
  await expect(page.getByRole("region", { name: "Resolution assistance" })).not.toContainText("Which approval record");
  await expect(page.getByRole("button", { name: "Generate next steps" })).toBeDisabled();
});
