# Service Desk Copilot

This branch implements the complete **FAISS retrieval + ticket cleaning + candidate filtering** pipeline, with a React review interface and a Python API.

For a new developer or coding agent, read [AGENTS.md](AGENTS.md), then [the analysis handoff](docs/ANALYSIS_HANDOFF.md). The handoff describes the implemented API, Python entry point, output contract, failure handling and extension boundaries. All code, documentation, UI copy and generated explanations should be in English; preserve original source quotations.

## Current implementation

```text
Original ticket ──→ Clean current facts ────────────┐
                └→ FAISS Top-50 → Filter evidence ─┴→ Field suggestions + evidence
```

- Retrieval uses pinned MiniLM embeddings and FAISS cosine search, returning up to **50 distinct document groups with original ranks and provenance**.
- Cleaning and retrieval/filtering run in parallel. Cleaning never rewrites or prefilters the search query.
- The default model is **GPT-5.5 (`gpt-5.5-2026-04-23`), reasoning disabled**, with one model call per branch, a 1,500-token ceiling per call and no automatic retries.
- The UI shows field suggestions, selected historical references and the original Top-50. A correction preview can be downloaded as a separate copy.
- Human reviews are stored through `POST /tickets/process` in SQLite. Uploaded tickets remain browser-local.

Resolution generation and automated routing are future work. The existing general review templates are not generated resolutions. There is no Jira writeback or online model/index training.

## Run locally

Use Python 3.10+ and Node 22.16+.

```sh
python -m venv .venv
source .venv/bin/activate
python -m pip install -e './backend[test]'

# Download the pinned training snapshot and build the index once.
python backend/scripts/download_training.py --output data/training.json
OMP_NUM_THREADS=4 MKL_NUM_THREADS=4 service-desk-build-index \
  --training data/training.json --output artifacts/retrieval/minilm-sdc-v1

# Uses OPENAI_API_KEY or prompts for it without echo.
OMP_NUM_THREADS=4 MKL_NUM_THREADS=4 python backend/scripts/serve.py \
  --artifact artifacts/retrieval/minilm-sdc-v1
```

Skip download/build when the artifact already exists. Data, model downloads and generated indexes are not committed. Leaving the key blank starts retrieval only.

In a second terminal:

```sh
cd frontend
npm ci
cp .env.example .env.local
npm run dev
```

Open the frontend, upload a Jira-style ticket JSON file, select a ticket and click **Clean & filter**. A demo file is available at `frontend/public/swisslife_20_tickets.json`. API documentation is at `http://localhost:8000/docs`.

## Entry points

| Purpose | Entry point |
|---|---|
| Full analysis over HTTP | `POST /tickets/analyze` |
| Retrieval only | `POST /retrieval/search` |
| Complete source pagination | `GET /retrieval/documents/{document_id}/sources` |
| Full analysis in Python | `service_desk.analysis.TicketAnalysis.analyze()` |
| Retrieval in Python | `service_desk.retrieval.TicketRetriever.search()` |
| Active frontend | `App → TicketOverview → TicketProcessor` |
| Human feedback | `POST /tickets/process` |

The API accepts ticket text directly; an issue ID alone is insufficient. Both model branches receive the original narrative. Current service/work-type metadata is used only to compare suggestions with the input.

## Measurements and checks

The latest lightweight configuration completed three live development tickets in **4.86s, 4.08s and 3.85s** (median **4.08s**), including retrieval and both model branches. It used zero reasoning tokens and averaged 273 output tokens per ticket. A repeated-request cache probe took 43ms. These Python-level measurements exclude startup/model loading, HTTP and browser rendering; they do not establish accuracy.

See [the recorded smoke results](backend/validation/lite-latency.json). The [earlier 20-ticket comparison](docs/PARALLEL_ANALYSIS_BENCHMARK.md) used different configurations and is not the current default's quality score.

Backend checks: 23 tests passed. Frontend integration checks: six browser tests, type checking, lint and production build passed. Commands are in [backend/README.md](backend/README.md).

## Handoff map

- [Analysis handoff](docs/ANALYSIS_HANDOFF.md): full pipeline contract, defaults, scheduling, failure behavior and downstream use.
- [Retrieval handoff](docs/RETRIEVAL_HANDOFF.md): grouping, ranks, comment provenance and legacy integration differences.
- [Backend guide](backend/README.md): artifact build, HTTP/Python contracts and tests.
- [Frontend guide](frontend/README.md): review workflow and local setup.

Use the existing package and endpoints. Research scripts, private local paths and evaluation annotations are not required to run the application.
