# Resolve: next steps for analyst review

Resolve turns the current ticket and selected historical evidence into up to three
action cards, one critical question when needed, and an editable English reply.
The analyst chooses Use / Edit / Not applicable and records the actual outcome.
This feature is implemented in the existing backend and frontend.
Resolve also consumes [current signals and known prerequisites](TICKET_SIGNALS.md)
from the existing filter call, and preserves that context in the saved proposal.

```text
Original facts → Clean ───────────────────────┐
              → FAISS Top-50 → Filter ────────┴→ Resolve → Analyst review
```

Resolve makes one additional model call. There is no agent loop, second index,
automatic retry, action execution, reply sending or Jira writeback. Existing clean,
retrieval and filter APIs remain independent. [Advisory routing and handoff](TRIAGE_HANDOFF.md)
are now separate downstream features; automatic assignment remains future work.
The [latency experiment](LATENCY_EXPERIMENT.md) documents concise output targets
and `analyze_and_resolve_fast()` / `/tickets/resolve-fast`, an explicit two-call
alternative with post-reconciliation draft validation. It is not the UI default.

## Run the demo

Follow [the root quick start](../README.md#run-locally) to build/load the index and
start the API and frontend. Upload `frontend/public/swisslife_20_tickets.json`,
select a ticket, click **Clean & filter**, then **Generate next steps**.

Each action shows **Recommended next step**, its reason, **Check first**,
**Expected outcome** and expandable **Source** quotations. Unknown prerequisites
or verification criteria remain explicitly unknown. A clarification-only result
may contain no cards. All original Top-50 candidates remain available below.

Choose **Use / Edit / Not applicable**, edit the **Reply draft**, and fill in
**Actual action and outcome** plus the business aspect before **Send**. Use selects
a suggestion; it does not assert that an action happened. Send saves the review
and moves the ticket to the browser's Processed Tickets list, not a resolved Jira
state. API failures leave the existing manual review flow available.

## Python API

```python
import asyncio
import os

from service_desk.analysis import TicketAnalysis, TicketInput
from service_desk.retrieval import TicketRetriever

async def main():
    retriever = TicketRetriever.load("artifacts/retrieval/minilm-sdc-v1")
    pipeline = TicketAnalysis(retriever, api_key=os.environ["OPENAI_API_KEY"])
    ticket = TicketInput(
        summary="Email outage for shared mailbox creation",
        description="Please create a shared mailbox and distribution list. No outage occurred.",
        current_services=("Outlook & Email",),
        current_work_type="Incident",
    )
    try:
        result = await pipeline.analyze_and_resolve(ticket)
        print(result["resolution"])
    finally:
        await pipeline.close()

if __name__ == "__main__":
    asyncio.run(main())
```

If an analysis already exists, use:

```python
resolved = await pipeline.resolve(ticket, analysis)
proposal = resolved["resolution"]
provider_result = resolved["model_result"]  # Python diagnostics, not for the UI.
```

The independent call does not retrieve, clean, filter, reconcile or cache. It
requires an analysis containing matching original `facts`, the reconciled `filter`
and `conflicts` fields; passing another ticket's facts raises `ValueError` before
calling the model. It also works after `analyze_clean_first()`. Use trusted outputs
from the existing pipeline, not client-written candidate lists. A standalone
Resolve consumer can construct `TicketAnalysis(service_catalog=[], api_key=...)`
without loading FAISS when it already has a complete saved analysis.

`analyze_and_resolve()` calls the default `analyze()` composition and then Resolve.
Successful results use the existing shared 64-entry, five-minute process cache and
in-flight deduplication. A cold request makes two analysis calls plus one Resolve
call; warm analysis needs just Resolve; a repeated complete result needs no call.
An expired cache or another server process may require analysis again. Resolve
shares the six-call concurrency limit, 45-second per-stage deadline, GPT-5.5 model,
reasoning `none` and 1,500-output-token limit. There are no automatic retries.

## HTTP API

```sh
curl http://localhost:8000/tickets/resolve \
  -H 'Content-Type: application/json' \
  -d '{"summary":"Shared mailbox request","description":"Create a shared mailbox and distribution list; no outage.","comments":[],"current_services":["Outlook & Email"],"current_work_type":"Incident"}'
```

The request schema is identical to `/tickets/analyze`: raw ticket fields only.
The server obtains/reuses its own analysis; an extra `analysis` field is rejected.
The response preserves the analysis, original Top-50 and provenance, and adds:

| Field | Meaning |
|---|---|
| `resolution.status` | `ready` means validated structure and citation membership, not proven correctness; otherwise `unavailable`. |
| `resolution.mode` | `action_plan` or `needs_information`. The latter permits diagnostic cards only and requires a question. |
| `resolution.actions` | Up to three cards with stable IDs within this proposal, kind, next step, reason, prerequisites, expected outcome, fact/source IDs, exact sources and `required_checks`. |
| `resolution.critical_question` | One focused question or `null`; the prompt requests a single missing decision variable. |
| `resolution.reply_draft` | Editable English draft, distinct from a sent message. |
| `resolution.proposal_id` | Content hash identifying the original proposal, not a signature. |
| `resolution.ticket_fingerprint` | Hash of the original `TicketInput`. |
| `resolution.context_signals` | Snapshot of the usable filter observations/prerequisites, with original quotations. Empty for unavailable/conflicting filtering or older analyses without signals. |
| `resolution.evidence_support` | Server-derived selected-evidence coverage, not answer confidence. |
| `resolution.requires_review` / `execution_authorized` | Always `true` / `false`. |
| `analysis_cache_hit` | Whether analysis was cached when this proposal was computed. |
| `cache_hit` | Whether the complete proposal response was reused on this request. |
| `timings.resolve_ms` | Resolve duration at original computation, not current cache lookup time. |
| `stage_status.resolve` | Success or a sanitized failure type; raw provider text/usage is omitted. |

Without a configured key, the endpoint returns 503. Provider/schema/validation
failure gives `resolution.status="unavailable"`, no cards and no invented reply;
the analysis and retrieved evidence remain available. Service conflict, unresolved
service or unavailable filtering excludes historical procedures and forces the
clarification mode. A usable current-fact diagnostic remains possible.

Python `stages` includes original provider usage. Cached analysis stage records
describe earlier calls; do not add them to a fresh Resolve request's token usage.

## Evidence contract

- Original current facts are authoritative. Clean suggestions are explicitly
  unverified; an outage-like title cannot override an explicit "no outage" fact.
- Resolve receives at most five primary case narratives and eight active,
  independently selected `reference`/`conditional` comments. No reserve comments
  or unselected siblings are included. Active comments may come from a parent
  group that was not selected as primary.
- Every card needs current-fact IDs and source IDs. A procedure must cite an
  active historical comment; a similar title or description alone is insufficient.
- Source IDs are constrained by the JSON schema. Exact quotations, document IDs,
  original ranks and comment provenance are materialized by the server.
- The server copies source conditions into `required_checks` even if model prose
  omits them. The UI shows these checks and preserves them when editing a step.
- Historical authors/team identities are not sent in the Resolve prompt. They
  remain available in the original provenance, separate from routing decisions.

Citation membership and retained conditions do not establish semantic entailment
or applicability. The model can still phrase a weak check, overstate a historical
detail, or ask a suboptimal question. The single-question prompt is not a semantic
guarantee: the validator checks presence and punctuation, not the number of
underlying information requests. Analyst review is part of this contract.

## Feedback contract

`POST /tickets/process` accepts the existing fields plus optional `resolution`:

```typescript
{
  proposal: originalResolutionProposal,
  actions: [
    { action_id: "A1", decision: "use", edited_next_step: null },
    { action_id: "A2", decision: "edit", edited_next_step: "The analyst's replacement step." }
  ],
  reply_draft: "The analyst's edited reply draft.",
  actual_outcome: "Checked the listener; it is running. No restart performed."
}
```

Include exactly one decision per proposed card (`unreviewed`, `use`, `edit` or
`not_applicable`). Edited steps require nonempty replacement text. The original
proposal is retained unchanged; edits and actual observations are separate.
`actual_outcome` is required and must match `real_solution`; neither is filled
automatically from a suggestion. It can record an unresolved observation.
`recommended_solution` contains only selected/edited steps in the frontend.

SQLite stores this in the existing feedback JSON; no migration is required and
identical submissions remain idempotent. The stored proposal is a client-supplied
review record, not a cryptographically verified server attestation. The existing
browser-local fallback retains the same payload when saving to the API fails.

## Verification and development evaluation

Run the commands in [the backend guide](../backend/README.md#verification).
The integrated suite has 56 backend tests and fifteen browser tests. It covers one
additional call, cache reuse, citations, prerequisite retention, clarification,
feedback persistence, action/draft edits, failure fallback and stale responses.
Type checking, lint and the production build also pass.

The [recorded development smoke](../backend/validation/resolution-smoke.json) uses
five selected public development cases and fresh Resolve calls over saved
clean/filter outputs from the earlier low-reasoning experiment. It isolates this
stage; clean/filter were not rerun. Those cases informed development, and an initial
run led to tightening the question prompt before the recorded run. There is no
held-out ground truth or automatic resolution-success score. Provider latency
excludes analysis, model loading, HTTP and rendering. Raw outputs remain in local
ignored artifacts; the committed report contains aggregate usage and review notes.

All five outputs passed schema/contract validation. Resolve took **2.49–4.73s**
(median **3.61s**), averaging **250 output tokens** with **zero reasoning tokens**.
The mailbox case followed the request/approval path; the queue case retained the
stalled-listener prerequisite; ambiguous cases asked for clarification. Remaining
quality issues include an ETA used as a weak prerequisite and wording that
overstates a historical diagnostic check. These are analyst-review findings,
not an operational success metric.
This five-case report predates current signals. The newer complete-workflow smoke
is recorded in [ticket-signals-smoke.json](../backend/validation/ticket-signals-smoke.json).

## Implementation map

| File | Responsibility |
|---|---|
| `backend/src/service_desk/analysis/resolution.py` | Prompt, bounded evidence input, schema, validation, sources and proposal identity. |
| `backend/src/service_desk/analysis/pipeline.py` | Independent Resolve call and cached composition. |
| `backend/src/service_desk/api.py` | Raw-ticket HTTP endpoint. |
| `backend/src/service_desk/feedback.py` | Original proposal, edits and actual outcome persistence. |
| `frontend/src/features/resolution/` | Request lifecycle, action cards and editable review. |
| `frontend/src/features/tickets/TicketOverview.tsx` | Existing ticket workflow and feedback integration. |
| `backend/tests/test_resolution.py`, `frontend/e2e/resolution.spec.ts` | Contract and browser regression checks. |

Offline resolution-card indexing remains a separate future experiment. It is not
needed to run this implementation.
