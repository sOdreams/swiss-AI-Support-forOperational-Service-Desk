import { expect, test, type Page } from "@playwright/test";
import { readFile } from "node:fs/promises";

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

test("current observations and known prerequisites retain quotations and survive in the review", async ({ page }) => {
  const signal = { observations: [
    { kind: "scope", text: "The approved Archive role", evidence_ids: ["Q2"], evidence: [{ fact_id: "Q2", source: "description", text: tickets[0].Description }] },
  ], prerequisites: [
    { check: "Approval for the requested role", state: "satisfied", evidence_ids: ["Q2"], evidence: [{ fact_id: "Q2", source: "description", text: tickets[0].Description }] },
    { check: "Identity of the user requiring access", state: "missing", evidence_ids: ["Q2"], evidence: [{ fact_id: "Q2", source: "description", text: tickets[0].Description }] },
  ] };
  const support = { state: "procedure_reference", reason: "Check current applicability before using the historical procedure.", active_comment_count: 1 };
  const base = analysis();
  const generated = resolved();
  const source = generated.resolution.actions[1].sources[0];
  source.text = "Resolution: Granted the approved role and confirmed access to the workspace.";
  const response = { ...generated, filter: { ...base.filter, signals: signal, evidence_support: support }, resolution: {
    ...generated.resolution, critical_question: "Which user needs the approved role?", context_signals: signal, evidence_support: support,
    actions: generated.resolution.actions.map((action, i) => i === 1 ? { ...action, sources: [{ ...source, verification_excerpt: "confirmed access to the workspace." }] } : action),
  } };
  await page.route("**/tickets/resolve", (route) => route.fulfill({ json: response }));
  await page.route("**/tickets/process", (route) => route.fulfill({ status: 201, json: { saved: true } }));
  await openTicket(page);
  await page.getByRole("button", { name: "Generate next steps" }).click();
  const situation = page.getByRole("region", { name: "Situation and known checks" });
  await expect(situation).toContainText("Already established in the ticket");
  await expect(situation).toContainText("Not established; confirm if needed");
  await expect(situation).toContainText("Historical procedure references available");
  const scope = situation.getByRole("article", { name: "Affected scope" });
  await scope.locator("summary").click();
  await expect(scope).toContainText(tickets[0].Description);
  const panel = page.getByRole("region", { name: "Resolution assistance" });
  const action = panel.getByRole("article", { name: "Action 2", exact: true });
  await action.locator("summary").click();
  await expect(action).toContainText("Historical verification: confirmed access to the workspace.");
  await expect(action).toContainText("Past evidence, not confirmation of the current outcome.");
  await panel.getByLabel("Actual action and outcome").fill("Requested the user identity; no access change made.");
  await page.getByRole("button", { name: /Service continuity/ }).click();
  const submitted = page.waitForRequest("**/tickets/process");
  await page.getByRole("button", { name: "Send", exact: true }).click();
  const payload = (await submitted).postDataJSON();
  expect(payload.resolution.proposal.context_signals).toEqual(signal);
  expect(payload.resolution.proposal.evidence_support).toEqual(support);
});

test("an empty knowledge selection is distinct from unavailable filtering", async ({ page }) => {
  const base = analysis();
  let ready = true;
  await openTicket(page);
  await page.route("**/tickets/analyze", (route) => route.fulfill({ json: { ...base, filter: { ...base.filter,
    status: ready ? "ready" : "unfiltered_fallback", signals: { observations: [], prerequisites: [] },
    evidence_support: ready ? { state: "no_selected_evidence", reason: "Nothing applicable was selected from this candidate pool.", active_comment_count: 0 }
      : { state: "unavailable", reason: "Filtering was unavailable; coverage has not been assessed.", active_comment_count: 0 },
  } } }));
  await page.getByRole("button", { name: "Clean & filter", exact: true }).click();
  const situation = page.getByRole("region", { name: "Situation and known checks" });
  await expect(situation).toContainText("No applicable evidence selected");
  ready = false;
  await page.getByRole("button", { name: "Clean & filter", exact: true }).click();
  await expect(situation).toContainText("Evidence assessment unavailable");
  await expect(situation).not.toContainText("No applicable evidence selected");
});

function triage(held = false) {
  const evidence = [{ fact_id: "Q2", source: "description", text: tickets[0].Description }];
  return {
    priority: { status: held ? "needs_review" : "suggested", urgency: { value: "Low", evidence },
      impact: { value: "Minor / Localized", evidence }, value: held ? null : "Low", proposed_value: "Low",
      rule_version: "test-rules", rule_source: "https://example.com/matrix", reason: held ? "Review the service disagreement." : "Calculated from urgency and impact.", requires_review: true },
    routing: { status: held ? "needs_review" : "suggested", service: held ? null : "Archive", team: held ? null : "Access Operations",
      reason: held ? "Review the service interpretation." : "Historical catalogue maps Archive to Access Operations.", service_evidence: evidence,
      catalogue_evidence: held ? [] : [{ team: "Access Operations", historical_rows: 5, example_row_indices: [1, 2, 3] }],
      historical_contributors: held ? [] : [{ author: "expert@example.com", evidence: [{ comment_id: "E1", text: "Resolution: Granted approved access.",
        condition: "Verify the target account.", document_id: "doc-0", original_rank: 1, row_index: 3 }] }],
      index_version: "test-index", assignee: null, assignment_authorized: false, requires_review: true },
  };
}

test("priority and routing show cited proposals while handoff preserves choices and actual findings", async ({ page }) => {
  const generated = { ...resolved(), triage: triage() };
  await page.route("**/tickets/resolve", (route) => route.fulfill({ json: generated }));
  await page.route("**/tickets/process", (route) => route.fulfill({ status: 201, json: { saved: true } }));
  await openTicket(page);
  await page.getByRole("button", { name: "Generate next steps" }).click();
  const assessment = page.getByRole("region", { name: "Priority and routing suggestions" });
  await expect(assessment).toContainText("Access Operations");
  await assessment.getByText("Evidence and calculation", { exact: true }).click();
  await expect(assessment).toContainText("Low × Minor / Localized → Low");
  await expect(assessment).toContainText(tickets[0].Description);
  await assessment.getByText("Historical contributors for this scenario", { exact: true }).click();
  await expect(assessment).toContainText("expert@example.com");
  await expect(assessment).toContainText("not verified current assignees");
  const panel = page.getByRole("region", { name: "Resolution assistance" });
  await panel.getByRole("article", { name: "Action 1", exact: true }).getByRole("button", { name: "Use", exact: true }).click();
  await panel.getByRole("article", { name: "Action 2", exact: true }).getByRole("button", { name: "Edit", exact: true }).click();
  await panel.getByLabel("Edit action 2").fill("Check the user's target account before granting the approved role.");
  await panel.getByRole("article", { name: "Action 3", exact: true }).getByRole("button", { name: "Not applicable" }).click();
  await panel.getByLabel("Actual action and outcome").fill("Asked for the target account. No access change was performed.");
  const downloadStarted = page.waitForEvent("download");
  await page.getByRole("button", { name: "Download handoff" }).click();
  const download = await downloadStarted;
  expect(download.suggestedFilename()).toBe("RESOLVE-1-handoff.md");
  const text = await readFile((await download.path())!, "utf8");
  expect(text).toContain("Suggested team: Access Operations");
  expect(text).toContain("Assignee: not assigned by this workflow");
  expect(text).toContain("A1 · use");
  expect(text).toContain("A2 · edit");
  expect(text).toContain("A3 · not applicable");
  expect(text).toContain("Check the user's target account");
  expect(text).toContain("Actual action and outcome — analyst-entered");
  expect(text).toContain("No access change was performed");
  expect(text).toContain("Reply draft — not sent");
  expect(text).toContain("Original candidates retained: 50");
  await page.getByRole("button", { name: /Service continuity/ }).click();
  const submitted = page.waitForRequest("**/tickets/process");
  await page.getByRole("button", { name: "Send", exact: true }).click();
  expect((await submitted).postDataJSON().triage).toEqual(generated.triage);
});

test("handoff is available without Resolve and cannot carry a previous ticket's suggestions", async ({ page }) => {
  await openTicket(page);
  const downloadStarted = page.waitForEvent("download");
  await page.getByRole("button", { name: "Download handoff" }).click();
  const text = await readFile((await (await downloadStarted).path())!, "utf8");
  expect(text).toContain("No resolution proposal is available");
  expect(text).toContain("Not recorded.");
  expect(text).toContain("Selected historical evidence");
  await page.getByRole("button", { name: /RESOLVE-2/ }).first().click();
  await expect(page.getByRole("region", { name: "Handoff package" })).toHaveCount(0);
  await expect(page.getByRole("region", { name: "Priority and routing suggestions" })).toHaveCount(0);
});

test("service disagreement holds priority and routing and clipboard failure leaves download available", async ({ page }) => {
  await page.addInitScript(() => Object.defineProperty(navigator, "clipboard", { value: { writeText: async () => { throw new Error("Unavailable"); } } }));
  await openTicket(page);
  await page.route("**/tickets/analyze", (route) => route.fulfill({ json: { ...analysis(), triage: triage(true) } }));
  await page.getByRole("button", { name: "Clean & filter", exact: true }).click();
  const assessment = page.getByRole("region", { name: "Priority and routing suggestions" });
  await expect(assessment).toContainText("Review disagreement");
  await expect(assessment).toContainText("Needs ownership review");
  await expect(assessment).not.toContainText("Access Operations");
  await page.getByRole("button", { name: "Copy handoff" }).click();
  await expect(page.getByRole("region", { name: "Handoff package" })).toContainText("Clipboard unavailable");
  await expect(page.getByRole("button", { name: "Download handoff" })).toBeEnabled();
});
