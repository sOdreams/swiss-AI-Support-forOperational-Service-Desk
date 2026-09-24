# FAISS retrieval handoff for developers and coding agents

Read the root [AGENTS.md](../AGENTS.md), then follow [backend/README.md](../backend/README.md). Retrieval, cleaning and filtering are implemented on this branch. Use [ANALYSIS_HANDOFF.md](ANALYSIS_HANDOFF.md) for the full pipeline; do not rebuild a separate FAISS wrapper or import research scripts.

## Implemented behavior

- Python package: `service_desk.retrieval`.
- Pinned MiniLM model, title/description/comments (SDC), exact normalized FAISS cosine search.
- Default Top-50 distinct evidence groups, each with a 1-based `rank`, raw `score` and stable `document_id`.
- Individual historical comments retain their own authors, source rows, service/team metadata and source relationships.
- HTTP retrieval, complete source pagination, frontend evidence selection and SQLite human feedback.
- Offline index construction; one retriever loaded at startup. Feedback never mutates the index automatically.

## Existing entry points

```python
from service_desk.retrieval import TicketQuery, TicketRetriever

retriever = TicketRetriever.load("artifacts/retrieval/minilm-sdc-v1")
candidates = retriever.search(TicketQuery(
    summary=ticket_summary,
    description=ticket_description,
    comments=tuple(comment_bodies),
), top_k=50)
```

For cleaning and filtering, use the existing `TicketAnalysis.analyze(TicketInput(...))` Python API or `POST /tickets/analyze`. It returns `clean`, `retrieval` and `filter` together. Filtering already exists; routing and resolution generation remain downstream work.

Search uses only the currently known narrative. Current service/work-type fields can be wrong and do not boost or restrict retrieval. Preserve original ranks and raw cosine values through subsequent processing. If adding a reranker, introduce separate ranking fields; cosine is not confidence.

## Evidence units and source relationships

A candidate is a title/description group, not one historical incident or one unique solution. The Top-50 is therefore 50 groups when enough groups exist. Comments within a group can describe different events.

The filter evaluates group relevance and individual comment applicability independently. A selected group does not make all its comments relevant. A useful comment can survive an unsuitable parent title. Consume `filter.active_comment_ids` and retain each comment's conditions and sources. Empty selections are valid.

Each returned comment includes up to three source examples. Retrieve complete provenance with `retriever.sources(document_id, offset, limit)` or the paginated HTTP source endpoint. Use the same index version while paging.

A future routing consumer may inspect historical author/service/team metadata. Historical assignee and comment author are different fields; neither alone establishes the appropriate current owner. Keep routing output out of the retrieval query.

## Legacy interfaces are not interchangeable

The older `TriageEngine.retrieve()` on `data-exploratory` returns training-row indices and lexical scores. This implementation returns grouped document IDs, cosine scores and evidence.

1. Do not use `training_records[hit.document_id]`. Read the hit's evidence sources or use the provenance endpoint.
2. Do not substitute cosine into legacy formulas such as `min(score, 8) * .12`, score sums or resolution bonuses. Evaluate downstream ranking or calibration separately.
3. The legacy `best_resolution_example()` may search outside the retrieved pool. If retained, label that evidence as an additional fallback rather than a Top-50 result.

The older routing pipeline has not been merged into this backend.

## Frontend and feedback

The active page is `App.tsx → TicketOverview.tsx → TicketProcessor`.

- `useRetrieval.ts` requests `/retrieval/search` and isolates stale responses after ticket switches.
- `useTicketAnalysis.ts` requests `/tickets/analyze` when the analyst clicks **Clean & filter**.
- `TicketAnalysisPanel.tsx` displays corrections and clarification questions.
- `RetrievalEvidencePanel.tsx` displays primary selections, independent historical comments and all original candidates.
- `AiProposalPanel.tsx` is a legacy component, not the current application entry point.

Uploads live in browser state, so send summary, description and comment bodies rather than expecting the backend to look up a ticket by issue ID.

`POST /tickets/process` saves the shown/used document IDs, model/index version and human review. There is no implemented online learning, automatic FAISS update or Jira writeback.

## Verification and evaluation limits

Run backend tests and frontend typecheck/lint/build/browser tests using the commands in [backend/README.md](../backend/README.md).

`backend/scripts/verify_baseline.py` records migration parity in `backend/validation/baseline-parity.json`. Near-tied candidates can exchange order because of floating-point differences; parity reports must preserve those differences.

Earlier 20-ticket comparisons are development diagnostics against assistant review, not official ground-truth accuracy. Migration parity is not model accuracy. Re-evaluate after changing the embedding, grouping or text recipe, and evaluate filtering/routing separately. The latest lightweight latency smoke results are in [lite-latency.json](../backend/validation/lite-latency.json).
