import type { TicketAnalysisResponse } from "../../types/analysis";
import type { ResolutionEdits, ResolutionProposal } from "../../types/resolution";
import type { Ticket } from "../../types/ticket";

const quote = (text: string) => text.split(/\r?\n/).map((line) => `> ${line}`).join("\n");

export function buildHandoff(ticket: Ticket, analysis: TicketAnalysisResponse,
  proposal: ResolutionProposal | null, review: ResolutionEdits | null, actualOutcome: string) {
  const lines = [`# Service desk handoff — ${ticket.issue_key}`, "", "Draft for analyst review. This export does not send a message, assign an owner or establish resolution.", "",
    "## Original ticket", "", quote(ticket.summary), "", quote(ticket.description ?? "No description recorded.")];
  for (const comment of ticket.all_comments) lines.push("", "Current comment:", quote(comment.body));
  if (ticket.linked_issues.length) lines.push("", `Linked references: ${ticket.linked_issues.map((item) => item.issue_key).join(", ")}. Linked ticket bodies have not been fetched.`);
  const triage = analysis.triage;
  lines.push("", "## Triage suggestions", "");
  for (const field of analysis.clean.fields) lines.push(`${field.field}: ${Array.isArray(field.suggested) ? field.suggested.join(", ") : field.suggested ?? "Unresolved"} (${field.state}; proposal only).`);
  if (triage) {
    lines.push(`Priority: ${triage.priority.value ?? "Not established"} (${triage.priority.status}).`,
      `Urgency: ${triage.priority.urgency.value ?? "Unknown"}. Impact: ${triage.priority.impact.value ?? "Unknown"}.`,
      `Matrix: ${triage.priority.rule_source}`, `Service: ${triage.routing.service ?? "Unresolved"}. Suggested team: ${triage.routing.team ?? "Needs ownership review"}.`,
      triage.routing.reason, "Assignee: not assigned by this workflow.");
    for (const dimension of [triage.priority.urgency, triage.priority.impact])
      for (const e of dimension.evidence) lines.push("", `${e.fact_id} (${e.source}):`, quote(e.text));
    for (const e of triage.routing.service_evidence) lines.push("", `${e.fact_id} (service evidence):`, quote(e.text));
    for (const e of triage.routing.catalogue_evidence) lines.push(`Catalogue: ${e.team}; example source rows ${e.example_row_indices.join(", ")}; index ${triage.routing.index_version}.`);
  } else lines.push("Triage suggestions are unavailable in this analysis.");
  if (analysis.conflicts.length) lines.push("", "Interpretation conflicts:", ...analysis.conflicts.map((c) => `- ${c.field}: ${c.clean ?? "Unknown"} / ${c.filter ?? "Unknown"}. ${c.action}`));
  const filtered = analysis.filter;
  lines.push("", "## Selected historical evidence", "");
  for (const group of filtered?.candidates.filter((g) => g.role === "primary") ?? [])
    lines.push(`- Original rank ${group.original_rank}: ${group.summary} (document ${group.document_id}).`);
  for (const comment of filtered?.comments.filter((c) => filtered.active_comment_ids.includes(c.id) && ["reference", "conditional"].includes(c.status)) ?? []) {
    lines.push("", `${comment.id} (${comment.status}):`, quote(comment.text));
    if (comment.condition) lines.push(`Check first: ${comment.condition}`);
    for (const source of comment.sources) lines.push(`Document ${source.document_id}; original rank ${source.original_rank}.`);
  }
  lines.push("", "## Current observations and prerequisites", "");
  for (const item of filtered?.signals?.observations ?? []) {
    lines.push(`- ${item.kind.replaceAll("_", " ")}: ${item.text}`);
    for (const e of item.evidence) lines.push(`  ${e.fact_id} (${e.source}):`, quote(e.text));
  }
  for (const item of filtered?.signals?.prerequisites ?? []) {
    lines.push(`- [${item.state}] ${item.check}`);
    for (const e of item.evidence) lines.push(`  ${e.fact_id} (${e.source}):`, quote(e.text));
  }
  if (filtered?.status === "needs_review") lines.push("These interpretations are on hold for review; they were not confirmed by the analyst.");
  const questions = [...new Set([...(proposal?.critical_question ? [proposal.critical_question] : []),
    ...analysis.clean.questions, ...(filtered?.questions ?? []),
    ...(filtered?.signals?.prerequisites.filter((p) => p.state === "missing").map((p) => p.check) ?? [])])];
  lines.push("", "## Open questions / missing information", "", ...(questions.length ? questions.map((q) => `- ${q}`) : ["No additional questions were generated; this does not establish completeness."]));
  lines.push("", "## Proposed actions — not a record of completed work", "");
  if (proposal) for (const action of proposal.actions) {
    const choice = review?.actions.find((r) => r.action_id === action.id);
    const decision = choice?.decision ?? "unreviewed";
    lines.push(`### ${action.id} · ${decision.replaceAll("_", " ")}`, "", quote(decision === "edit" ? choice?.edited_next_step ?? "" : action.next_step),
      "", `Why: ${action.reason}`, `Check first: ${[action.check_first, ...action.required_checks].filter(Boolean).join("; ") || "Not established"}`,
      `Expected outcome: ${action.expected_outcome ?? "Not established"}`);
    for (const source of action.sources) {
      lines.push("", `Source ${source.id} (${source.kind}):`, quote(source.text));
      for (const ref of source.sources ?? []) lines.push(`Document ${ref.document_id}; original rank ${ref.original_rank}.`);
    }
  } else lines.push("No resolution proposal is available.");
  lines.push("", "## Actual action and outcome — analyst-entered", "", quote(actualOutcome.trim() || "Not recorded."),
    "", "## Evidence coverage", "", filtered?.evidence_support?.reason ?? "Coverage was not assessed.",
    `Retrieval index: ${analysis.retrieval?.index_version ?? "Unavailable"}. Original candidates retained: ${analysis.retrieval?.hits.length ?? 0}.`);
  if (proposal) lines.push("", "## Reply draft — not sent", "", quote(review?.reply_draft ?? proposal.reply_draft));
  return lines.join("\n") + "\n";
}
