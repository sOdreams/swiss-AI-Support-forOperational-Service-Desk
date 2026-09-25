# FAISS retrieval: build, run, call

The retrieval endpoint returns **50 ranked, distinct evidence groups** by default.
A separate `POST /tickets/analyze` endpoint runs narrative cleaning concurrently
with FAISS retrieval and candidate filtering, using GPT-5.5 with reasoning disabled.
The frontend's **Clean & filter** button shows reviewable field corrections and
selected evidence while preserving the original Top-50. See the complete English
[analysis handoff](../docs/ANALYSIS_HANDOFF.md) for setup, contracts, measured
latency and limitations. Routing and feedback remain separate.
`POST /tickets/resolve` reuses analysis and adds one model call for reviewable
action cards, a critical question and a reply draft. See the
[resolution handoff](../docs/RESOLUTION_HANDOFF.md) for its Python/HTTP contracts.
Filter's existing call also produces cited current observations and prerequisite
states. Resolve uses these alongside the original facts. See
[ticket signals](../docs/TICKET_SIGNALS.md); no additional call or index rebuild is needed.

## Quick start (from the repository root)

Use Python 3.10+ and Node 22.16+ (or another version supported by the frontend's Vite).
A CPU is sufficient. Initial model loading needs Hugging Face access; later loads
can use the local cache. The model revision is pinned in `retrieval/documents.py`.

```sh
python -m venv .venv
source .venv/bin/activate
python -m pip install -e './backend[test]'

# Download the exact public training snapshot, checking its SHA-256.
python backend/scripts/download_training.py --output data/training.json

# Offline operation. Destination must not already exist.
OMP_NUM_THREADS=4 MKL_NUM_THREADS=4 service-desk-build-index \
  --training data/training.json \
  --output artifacts/retrieval/minilm-sdc-v1

# Uses OPENAI_API_KEY or prompts without echo; blank enables retrieval only.
# Keep this terminal running. Paths below are relative to the current directory.
FEEDBACK_DB=data/feedback.sqlite3 \
OMP_NUM_THREADS=4 MKL_NUM_THREADS=4 \
python backend/scripts/serve.py --artifact artifacts/retrieval/minilm-sdc-v1 \
  --host 127.0.0.1 --port 8000
```

Windows: activate `.venv\Scripts\Activate.ps1` and set environment variables with
PowerShell syntax, for example `$env:OMP_NUM_THREADS = "4"`, before running the
commands without their shell variable prefixes. The launcher sets the artifact path.

In another terminal:

```sh
cd frontend
npm ci
# .env.example uses VITE_API_BASE_URL=http://localhost:8000
cp .env.example .env.local
npm run dev
```

Upload `frontend/public/swisslife_20_tickets.json`, select a ticket, and inspect
**Historical evidence · Top 50**. Click **Clean & filter** to run both model branches
and review field suggestions and the selected evidence. Click **Generate next steps**
for resolution proposals. Choose **Use / Edit / Not applicable**, edit the reply if
needed, and record the actual action/outcome plus business aspect before saving.
General review templates remain the manual fallback. Feedback is saved in SQLite; the existing frontend
local-storage fallback still applies if the API is unavailable.

API docs: <http://localhost:8000/docs>. Health: `GET /health`.
If Vite runs on a different origin, set `FRONTEND_ORIGINS` to comma-separated origins
before starting the API. This is a local prototype; use the application's deployment
authentication/access controls before exposing source evidence remotely.

## HTTP contract

```sh
curl http://localhost:8000/retrieval/search \
  -H 'Content-Type: application/json' \
  -d '{"summary":"Shared mailbox request","description":"Create a shared mailbox and distribution list; no outage.","comments":[],"top_k":50}'
```

Inputs: `summary` (string, optional), `description` (string/null, optional),
`comments` (array of bodies, optional), `top_k` (integer 1–50, default **50**).
At least one text field must be nonempty. Excessively long queries return 422 instead
of silently truncating the model input. Supplied routing fields are rejected.

Response structure (illustrative values):

```json
{
  "index_version": "artifact-version",
  "model": "sentence-transformers/all-MiniLM-L6-v2",
  "score_type": "cosine",
  "hits": [{
    "document_id": "stable-content-hash",
    "rank": 1,
    "score": 0.73,
    "summary": "Historical title",
    "matched_text": "Best-matching indexed chunk",
    "historical_count": 100,
    "evidence": [{
      "body": "Resolution: Original comment body",
      "occurrences": 12,
      "sources": [{
        "row_index": 42,
        "ticket_id": "row-42",
        "comment_index": 2,
        "author": "original.author@example.com",
        "services": ["Historical service"],
        "teams": ["Historical team"],
        "assignee": "historical assignee",
        "resolution_date": null
      }]
    }]
  }]
}
```

- `rank`: 1-based order of distinct groups, descending cosine. It is not a routing
  priority. If fewer groups exist, fewer hits are returned.
- `score`: raw cosine, possibly negative; **not a probability**.
- `document_id`: stable hash of title/description. It is **not a training-row index**.
- `matched_text`: the winning chunk; group score is the maximum over its chunks.
- `evidence`: all distinct comment bodies in the group, each with up to three exact
  source examples. These are aggregate historical patterns, not a single incident.
- Full source provenance is paginated at
  `GET /retrieval/documents/{document_id}/sources?offset=0&limit=50` (limit 1–100).
  Use the same artifact version while paging; source row indices refer to the
  manifest's training snapshot. Titles/descriptions also retain all `row_indices`
  in the on-disk document metadata, including groups with no comments.

## Python use (no HTTP required)

```python
from service_desk.retrieval import TicketQuery, TicketRetriever

retriever = TicketRetriever.load("artifacts/retrieval/minilm-sdc-v1")  # once
hits = retriever.search(TicketQuery(
    summary="Shared mailbox request",
    description="Create a shared mailbox; no outage.",
    comments=("Please provision the standard permissions.",),
), top_k=50)

for hit in hits:
    print(hit.rank, hit.document_id, hit.score, hit.matched_text)
```

Reuse the retriever across requests. Its encoder call is serialized for predictable
shared use; FAISS is read-only. Each API worker loads its own model and artifact.
Imports do not download models or build indexes. Load only locally trusted build
artifacts. Missing/incompatible artifacts cause startup to fail explicitly.

## Artifact and algorithm

`all-MiniLM-L6-v2`, pinned revision, 384-dimensional normalized float32 embeddings
and `faiss.IndexFlatIP`. Both query and document vectors are normalized. No IVF/HNSW
training or GPU FAISS dependency is needed for this corpus.

The SDC recipe uses title + description + frequency-ordered distinct comment bodies;
email author prefixes are removed from indexed text and retained in provenance.
Historical rows are grouped by title/description in sorted order. Long documents
use 248-token windows and 32-token overlap; the query is guarded at the model limit.
The evaluated snapshot yields 173 groups / 178 chunks. Search all chunks, aggregate
maximum score per group, sort descending with group-order tie breaking, return 50.

Each immutable artifact directory contains:

- `index.faiss`: normalized chunk vectors.
- `chunks.json`: text and chunk→group mapping.
- `documents.jsonl`: group text, original row indices and full comment provenance.
- `manifest.json`: model/revision, dataset SHA, recipe, dimensions, counts, package
  versions, file checksums and index version.

Build to a new destination when inputs change; then restart with the new directory.
Do not overwrite a live index. Published feedback never mutates it automatically.

## Feedback

`POST /tickets/process` accepts the existing frontend payload, plus optional
`retrieval: {index_version, model, shown_document_ids, selected_document_ids}`.
Selected IDs must be a subset of shown IDs. SQLite stores the complete payload;
identical retries are deduplicated. This endpoint records human reviews, not model
training or ticket writeback to Jira. It does not implement the legacy `/assist`
or `/feedback` routes from the older frontend API scaffold.
Optional `resolution` feedback stores the original proposal, one decision per card,
the edited reply draft and the actual outcome. The latter must match `real_solution`.
See the [feedback contract](../docs/RESOLUTION_HANDOFF.md#feedback-contract).

## Verification

```sh
python -m pytest backend/tests -q
cd frontend
npm run typecheck
npm run lint
npm run build
npx playwright install chromium
npm run test:e2e
```

The twelve browser tests use a mocked API to check Top-50 display, feedback provenance,
field corrections, independent comment selection, correction-preview export,
late-response isolation after ticket switching, action choices, source conditions,
reply edits, separate actual outcomes, clarification-only proposals and error handling.
They also check known prerequisites, exact current quotations, historical verification,
context snapshots in feedback and the distinction between missing evidence and unavailable filtering.

Tests use a deterministic fake encoder to exercise grouping, ranking, provenance,
artifact validation, query errors, HTTP defaults and feedback persistence without
network/model downloads. Real-model parity is checked separately:

```sh
python backend/scripts/verify_baseline.py \
  --artifact artifacts/retrieval/minilm-sdc-v1 \
  --experiment /path/to/swisslife-retrieval/results/field_combinations \
  --examples /path/to/jira_hackathon_blind_eval_challenge_20260923083915-1141.json \
  --output backend/validation/baseline-parity.json
```

See `validation/baseline-parity.json` for the recorded migration comparison. These
20 examples informed development; this comparison is **not ground-truth accuracy**.
See `../docs/RETRIEVAL_HANDOFF.md` for downstream integration guidance.
