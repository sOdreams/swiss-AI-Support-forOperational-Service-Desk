# Priority, advisory routing and handoff export

These three features close gaps between finding useful evidence and deciding what
an analyst should do with the ticket. They reuse the existing pipeline and add no
model calls: Clean assesses urgency/impact in its existing response, deterministic
code computes priority/routing, and the browser formats an English handoff draft.

## Run and use

Follow [the root quick start](../README.md#run-locally), upload tickets and click
**Clean & filter**. The new **Priority and routing for review** panel shows:

- Suggested Priority, Urgency and Impact, with exact current evidence and the
  matrix calculation. Unknown inputs remain unknown.
- A proposed receiving team from the historical service catalogue, with source
  row examples and index version. This is a historical mapping, not a live roster.
- Historical contributors from selected applicable comments, with those comments,
  conditions and original ranks. They are not automatically assigned.

After analysis, **Copy handoff / Download handoff** creates a local Markdown draft.
Resolve is optional. Generating/reviewing action cards or entering actual findings
updates the draft. Copy/download do not contact a team, send a requester reply,
change the imported ticket, or close a Jira issue. Clipboard failure leaves the
download option available. The draft can be edited in any text editor after export.

## Priority contract

`analysis.triage.priority` contains `status`, `value`, `proposed_value`, `urgency`,
`impact`, `reason`, `rule_version`, `rule_source` and `requires_review=true`.
Each dimension contains `value` and literal current `evidence` with Q IDs.

The definitions, critical-service list and 5×5 matrix come from the pinned
[challenge README](https://github.com/Swiss-ai-Weeks/SwissLife-2026/blob/00fea7dbe887454436297d5aa19865dea5553434/README.md).
They live in `analysis/triage.py`; no individual challenge-ticket answers are used.
The supplied historical Priority/Urgency/Impact columns are random and are never
used for neighbor voting or as model inputs.

Clean returns two new nullable classifications and their citation IDs. The model
does not return Priority. `calculate_priority(urgency, impact)` indexes the matrix
only when both dimensions are recognized. A missing citation makes its dimension
unsupported and leaves priority unknown without discarding other clean results.
Service criticality alone is insufficient: an ordinary access request is not an
outage; “ASAP” alone does not establish critical urgency or absent workaround.

| Status | Meaning |
|---|---|
| `suggested` | Both dimensions have current citations; `value` is the matrix result. Human review is still required. |
| `needs_information` | At least one dimension is unknown/unsupported; `value=null`. |
| `needs_review` | Clean/filter service interpretations conflict; `value=null`, with any computed `proposed_value` retained for review. |
| `unavailable` | Clean did not produce usable output; no priority is applied. |

The matrix calculation is deterministic; the urgency/impact interpretation is
model-generated and not validated as business ground truth. The challenge rules
are a pinned prototype policy, not a claim about current production policy.

## Routing contract

`analysis.triage.routing` contains `status`, `service`, `team`, `reason`,
`service_evidence`, `catalogue_evidence`, `historical_contributors`, `index_version`,
`requires_review=true`, `assignee=null` and `assignment_authorized=false`.

`TicketRetriever.service_team_catalog()` reads metadata in the loaded artifact;
it does not search, re-embed or rebuild. It counts each original row once per
service/team mapping, regardless of repeated comments. Multi-service source rows
are excluded because they do not establish a unique mapping. Records without
comment source metadata cannot contribute to this catalogue.

A usable filtered service with exactly one catalogue team produces a suggestion.
Missing/ambiguous catalogue mappings remain `needs_information`; the most frequent
team does not silently win. Unresolved/conflicting service interpretation gives
`needs_review`; unavailable filtering gives `unavailable`. No model receives team
or contributor identities, and neither is inserted into the retrieval query.

Contributors come only from independently active `reference`/`conditional`
comments in the supported service. Reserve comments and arbitrary parent comments
do not count. An author is deduplicated, each cited comment appears once per author,
and at most three authors are returned in source encounter order. This is a bounded
sample from the existing provenance, not an exhaustive expertise ranking. Repeated
synthetic rows do not become success votes. Historical Assignee is never a routing
vote and comment authors do not establish present availability or authorization.

The default catalogue is derived once when constructing `TicketAnalysis`. A caller
can supply an explicit historical catalogue with the same provenance structure:

```python
from service_desk.analysis import TicketAnalysis
from service_desk.analysis.triage import build_triage, calculate_priority

catalogue = {
    "Example Service": [{
        "team": "Example Operations",
        "historical_rows": 1,
        "example_row_indices": [42],
    }]
}
pipeline = TicketAnalysis(retriever, api_key=key, routing_catalog=catalogue)
analysis = await pipeline.analyze(ticket)
triage = analysis["triage"]

# Pure deterministic recomputation from trusted analysis; no API/model call.
triage = build_triage(analysis, catalogue)
assert calculate_priority("High", "Significant / Large") == "High"
```

The example mapping is illustrative. Catalogue values must be trusted application
data. A live directory would need its own provenance contract and UI wording before
being substituted for historical evidence. A custom retriever without the
catalogue method remains compatible and defaults to no team mapping. Standalone
Clean/Filter APIs remain unchanged in ordering; `build_triage` consumes a complete,
reconciled analysis, not a standalone filter result. The composed cache key includes
the routing catalogue and priority-rule version in addition to existing inputs.

## Handoff contents and feedback

The browser's pure `buildHandoff()` function formats current data; it makes no model
or HTTP call. It includes original title/body/comments, linked-issue references,
proposed classifications, priority/routing evidence, selected historical comments,
current observations, prerequisite states, conflicts, missing information, reviewed
action cards with source IDs/ranks, analyst-entered actual outcome and reply draft.
Linked ticket bodies are not fetched or invented. A handoff without Resolve clearly
says no resolution proposal is available.

Every action retains Use / Edit / Not applicable / Unreviewed. Edited text is exported
as the analyst's chosen step; conditions and references remain visible. Proposed
actions are explicitly distinct from the actual-outcome section; selected actions
are never treated as executed. The reply is explicitly a draft that was not sent.
Switching tickets discards the previous panel, preventing stale exports.

`POST /tickets/process` now accepts optional `triage` (up to 100,000 serialized
characters) beside existing resolution/retrieval feedback. SQLite stores the shown
suggestions separately from `real_solution`; no migration is needed. Like the
existing proposal, this is a client-submitted review snapshot, not a cryptographic
server attestation or a confirmed analyst-approved priority/assignment. The exported
Markdown is local and is not automatically uploaded or sent anywhere.

## Implementation map and validation

| File | Responsibility |
|---|---|
| `backend/src/service_desk/analysis/triage.py` | Pinned priority policy, pure calculation, evidence-backed team and contributor proposals. |
| `analysis/contracts.py`, `analysis/prompts.py` | Cited urgency/impact in the existing Clean call; service evidence in Filter output. |
| `analysis/pipeline.py` | Build triage after reconciliation and include policy/catalogue in cache identity. |
| `retrieval/retriever.py` | Read historical service/team mapping from artifact provenance. |
| `frontend/src/features/triage/` | Priority calculation and routing evidence presentation. |
| `frontend/src/features/handoff/` | Deterministic draft assembly, preview, clipboard and Markdown download. |

48 backend tests and 15 browser tests pass, including all 25 matrix cells, unknown
dimensions, missing citations, conflict holds, ambiguous catalogues, independent
comment provenance, row deduplication, no extra inference, feedback persistence,
handoff action/outcome separation and clipboard/stale-ticket handling. Frontend type
checking, lint and production build pass. The [live development smoke](../backend/validation/triage-smoke.json)
uses six selected cases with fresh Clean/FAISS/Filter/Resolve calls; it is not a
held-out accuracy evaluation or a before/after quality comparison.

The run completed in a median 8.53 seconds (7.08–9.85 seconds), excluding model
loading, with 18 calls and zero reasoning tokens. Five cases completed all stages.
In case 4, Filter selected a primary group outside the supported service; validation
rejected that response. The result retained Top-50, withheld routing, and produced
current-fact diagnostics only. It was not retried or removed from the report.
Urgency judgments still need review: case 7 used weak urgency wording but withheld
priority because impact was unknown; case 13's High-versus-Medium urgency depends
on how onerous the recorded workaround is. No priority-accuracy claim is made.
