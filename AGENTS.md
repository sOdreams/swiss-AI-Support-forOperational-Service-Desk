# Working on this repository

Read `backend/README.md` before changing retrieval. It contains complete build/run
commands, the HTTP/Python contracts, ranking semantics and verification steps.
Read `docs/RETRIEVAL_HANDOFF.md` for filter/routing integration examples.
Read `docs/ANALYSIS_HANDOFF.md` for the implemented parallel clean/filter pipeline,
its API, English output contract, cache/failure behavior and evaluation limits.
Read `docs/RESOLUTION_HANDOFF.md` for action cards, the single-call Resolve stage,
analyst decisions and outcome feedback.
Read `docs/TICKET_SIGNALS.md` for current-fact observations, prerequisite states,
historical verification excerpts and candidate-pool coverage.

Use English for code comments, documentation, UI text and generated explanations.
Preserve original ticket text and literal evidence quotations. The latest lightweight
latency smoke results are in `backend/validation/lite-latency.json`.
FAISS, clean, filter and reviewable resolution proposals are implemented. Routing
remains future work. General review templates are the manual fallback, not generated fixes.

## Agent entry points

Use `from service_desk.analysis import TicketAnalysis, TicketInput` and
`from service_desk.retrieval import TicketQuery, TicketRetriever`.

| Task | Existing call |
|---|---|
| Full default workflow | `await pipeline.analyze(ticket)` |
| Check ticket fields only | `await pipeline.clean(ticket)` |
| Retrieve a reusable candidate snapshot | `await pipeline.retrieve(query)` |
| Filter an existing snapshot only | `await pipeline.filter(ticket, candidates)` |
| Full clean-first workflow | `await pipeline.analyze_clean_first(ticket)` |
| Next steps from an existing analysis | `await pipeline.resolve(ticket, analysis)` |
| Cached analysis plus next steps | `await pipeline.analyze_and_resolve(ticket)` |

`ticket` is a `TicketInput`; `query` is a `TicketQuery`. Create one pipeline with
the loaded retriever and reuse it; call `await pipeline.close()` at shutdown.
The analysis handoff includes a runnable Python example and exact return fields.
Clean may run before or after retrieval/filtering. Filter requires candidates,
but never performs retrieval itself. Keep the complete Python retrieval snapshot,
including `documents`; the HTTP `/retrieval/search` response alone is insufficient
for the standalone Python filter. Direct stage calls do not perform cross-stage
reconciliation or caching; use a complete workflow when those behaviors are needed.

## Architecture

- The active frontend is `App → TicketOverview → TicketProcessor`.
- `frontend/src/features/retrieval/` calls `POST /retrieval/search` with the selected
  ticket's summary, description and comment bodies; uploaded tickets are browser-local.
- `backend/src/service_desk/retrieval/` owns the pinned MiniLM encoder, SDC text
  recipe, normalized FAISS IndexFlatIP, chunk grouping and provenance.
- Default retrieval is **Top-50 unique document groups**, with **1-based rank**.
  A document group is NOT a historical row or a resolution/owner prediction.
- `api.py` loads one retriever at startup. `feedback.py` stores human feedback in
  SQLite separately; feedback does not rebuild or mutate the search index.
- Routing/filtering are downstream consumers. Do not put predicted service/team/
  assignee into search inputs or turn cosine similarity into confidence.
- `analysis/` runs current-fact cleaning in parallel with original-narrative
  retrieval followed by evidence filtering. Default: GPT-5.5, reasoning disabled,
  one call per branch, no automatic retries.
  `/tickets/analyze` never writes back to Jira or assigns an owner. Preserve all
  original candidates and distinguish active comments from uncertain reserves.
- `TicketAnalysis.clean()`, `.retrieve()` and `.filter()` are independent Python
  stage calls. Filter consumes a self-contained candidate snapshot; it never
  triggers retrieval. An explicit `service_catalog` supports clean/filter without
  loading FAISS. `.analyze_clean_first()` is an opt-in composition that uses only
  proposed title corrections for search and preserves original facts for filtering.
  The default HTTP/UI workflow remains parallel. Compare workflows before changing
  defaults; a corrected title is not verified current evidence.
- `analysis/resolution.py` builds proposals from original facts and active filtered
  comments. `/tickets/resolve` reuses server-side analysis and adds one model call;
  a cold request runs analysis first. Keep source conditions, original ranks and
  the full Top-50. Unknown/conflicting service evidence allows clarification and
  diagnostics only. A matching citation ID does not prove semantic correctness.
- Filter also extracts bounded, cited `signals` in its existing call. These are
  reviewable interpretations, not verified facts or new search/routing inputs.
  Server-derived `evidence_support` describes only the selected candidate pool.
  Recompute it after disagreement holds; never treat repeated comments as independent
  successes. Historical verification excerpts are literal quotes, not current outcomes.
- `frontend/src/features/resolution/` supports Use / Edit / Not applicable, an
  editable reply and a separately entered actual outcome. Feedback preserves the
  original proposal and edits; it does not execute actions, send replies or close Jira tickets.
- `data-exploratory` is a separate remote branch with an older `TriageEngine`.
  It is not imported by this backend. Its lexical score weights and row indices
  are incompatible with cosine scores and grouped document IDs.

## Safe extension points

Use `from service_desk.retrieval import TicketQuery, TicketRetriever` in Python,
or `/retrieval/search` over HTTP. Preserve document IDs, original rank, raw score,
model/index version and per-comment source relationships through filtering.
For hybrid retrieval, use rank fusion or an explicitly calibrated scheme; do not
add BM25/legacy lexical scores directly to cosine.

Do not copy research scripts or their evaluation annotations into serving code.
Do not commit training JSON, downloaded models, generated FAISS artifacts, or
feedback databases. Build artifacts offline; never rebuild during a request.
Changing text/grouping/chunking/model semantics requires rebuilding and evaluation.

## Checks

From repository root:

```sh
python -m pip install -e './backend[test]'
python -m pytest backend/tests -q
```

From `frontend/`:

```sh
npm ci
npm run typecheck
npm run lint
npm run build
npx playwright install chromium
npm run test:e2e
```

`backend/scripts/verify_baseline.py` compares against the prior local experiment
artifacts, if available. Those external experiment files are not required to run
this application. Committed parity results are migration checks, not GT accuracy.
