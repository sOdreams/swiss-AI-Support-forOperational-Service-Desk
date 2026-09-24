# Working on this repository

Read `backend/README.md` before changing retrieval. It contains complete build/run
commands, the HTTP/Python contracts, ranking semantics and verification steps.
Read `docs/RETRIEVAL_HANDOFF.md` for filter/routing integration examples.
Read `docs/ANALYSIS_HANDOFF.md` for the implemented parallel clean/filter pipeline,
its API, English output contract, cache/failure behavior and evaluation limits.

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
  retrieval followed by evidence filtering. Default: GPT-5.5 low reasoning.
  `/tickets/analyze` never writes back to Jira or assigns an owner. Preserve all
  original candidates and distinguish active comments from uncertain reserves.
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
