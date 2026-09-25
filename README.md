# Service Desk Copilot

This branch implements **FAISS retrieval + ticket cleaning + candidate filtering + resolution proposals**, with a React review interface and a Python API.

For a new developer or coding agent, read [AGENTS.md](AGENTS.md), then [the analysis handoff](docs/ANALYSIS_HANDOFF.md). The handoff describes the implemented API, Python entry point, output contract, failure handling and extension boundaries. All code, documentation, UI copy and generated explanations should be in English; preserve original source quotations.

## Current implementation

```text
Original ticket ──→ Clean current facts ────────────┐
                └→ FAISS Top-50 → Filter evidence ─┴→ Resolve → Analyst review
```

- Retrieval uses pinned MiniLM embeddings and FAISS cosine search, returning up to **50 distinct document groups with original ranks and provenance**.
- By default, cleaning and retrieval/filtering run in parallel; cleaning does not rewrite or prefilter the search query.
- Independent Python stage calls allow custom ordering. The optional `analyze_clean_first()` workflow searches a proposed corrected title while filtering against original facts; it does not insert predicted service/team labels. See the [stage interfaces](docs/ANALYSIS_HANDOFF.md#independent-stage-calls-and-explicit-ordering).
- The default model is **GPT-5.5 (`gpt-5.5-2026-04-23`), reasoning disabled**, with one model call per branch, a 1,500-token ceiling per call and no automatic retries.
- The UI shows field suggestions, selected historical references and the original Top-50. A correction preview can be downloaded as a separate copy.
- **Generate next steps** adds one Resolve call: up to three action cards, one critical question when needed and an editable English reply draft. Each card includes current facts, sources, prerequisites and a verification criterion where supported.
- Analysts choose **Use / Edit / Not applicable** and enter the actual action/outcome separately. Suggestions never count as completed work.
- **Situation and known checks** shows the working/failing process steps, preceding changes, business impact, scope, workaround, deadlines and constraints when supported. A cited prerequisite checklist distinguishes established, missing and contradicted details. Coverage labels describe the selected evidence, and historical verification clauses remain tied to their sources. See [ticket signals](docs/TICKET_SIGNALS.md).
- **Priority and routing for review** calculates Priority from cited Urgency/Impact using the challenge matrix, proposes a team from the historical service directory, and exposes relevant historical contributors separately from current assignees.
- **Copy handoff / Download handoff** prepares a local English Markdown draft with facts, triage, missing information, source references, action choices and actual outcomes. It works after analysis even when Resolve is unavailable. See [triage and handoff](docs/TRIAGE_HANDOFF.md).
- Human reviews are stored through `POST /tickets/process` in SQLite. Uploaded tickets remain browser-local.

Automatic assignment remains future work. There is no action execution, message sending, Jira writeback or online model/index training. General review templates remain available when no generated proposal is ready.

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

Open the frontend, upload a Jira-style ticket JSON file, select a ticket, click **Clean & filter**, then **Generate next steps**. A demo file is available at `frontend/public/swisslife_20_tickets.json`. API documentation is at `http://localhost:8000/docs`.

## Entry points

| Purpose | Entry point |
|---|---|
| Full analysis over HTTP | `POST /tickets/analyze` |
| Analysis plus resolution proposals | `POST /tickets/resolve` |
| Retrieval only | `POST /retrieval/search` |
| Complete source pagination | `GET /retrieval/documents/{document_id}/sources` |
| Full analysis in Python | `service_desk.analysis.TicketAnalysis.analyze()` |
| Full analysis plus proposals in Python | `TicketAnalysis.analyze_and_resolve()` |
| Resolve from existing analysis only | `TicketAnalysis.resolve(ticket, analysis)` |
| Retrieval in Python | `service_desk.retrieval.TicketRetriever.search()` |
| Active frontend | `App → TicketOverview → TicketProcessor` |
| Human feedback | `POST /tickets/process` |

The API accepts ticket text directly; an issue ID alone is insufficient. Both model branches receive the original narrative. Current service/work-type metadata is used only to compare suggestions with the input.

## Measurements and checks

Before signals and triage were added, the lightweight configuration completed three live development tickets in **4.86s, 4.08s and 3.85s** (median **4.08s**), including retrieval and both model branches. It used zero reasoning tokens and averaged 273 output tokens per ticket. A repeated-request cache probe took 43ms. These Python-level measurements exclude startup/model loading, HTTP and browser rendering; they do not establish accuracy or describe the current complete workflow.

See [the recorded smoke results](backend/validation/lite-latency.json). The [earlier 20-ticket comparison](docs/PARALLEL_ANALYSIS_BENCHMARK.md) used different configurations and is not the current default's quality score.

Resolve adds one call after cached analysis (three calls total on a cold request). Its separate five-case development smoke check and limits are documented in [the resolution handoff](docs/RESOLUTION_HANDOFF.md); the analysis timings above exclude Resolve.

Priority/routing and handoff add no model calls. The [current triage smoke report](backend/validation/triage-smoke.json) records a complete workflow check; it is not an accuracy comparison.

Backend checks: 48 tests passed. Frontend integration checks: fifteen browser tests, type checking, lint and production build passed. Commands are in [backend/README.md](backend/README.md).

## Handoff map

- [Analysis handoff](docs/ANALYSIS_HANDOFF.md): full pipeline contract, defaults, scheduling, failure behavior and downstream use.
- [Resolution handoff](docs/RESOLUTION_HANDOFF.md): action cards, one-call integration, UI review, feedback and development smoke results.
- [Ticket signals](docs/TICKET_SIGNALS.md): observations, known prerequisites, evidence coverage and their use in Resolve without another model call.
- [Triage and handoff](docs/TRIAGE_HANDOFF.md): priority rules, team catalogue, contributor provenance, local handoff export and feedback.
- [Retrieval handoff](docs/RETRIEVAL_HANDOFF.md): grouping, ranks, comment provenance and legacy integration differences.
- [Backend guide](backend/README.md): artifact build, HTTP/Python contracts and tests.
- [Frontend guide](frontend/README.md): review workflow and local setup.

Use the existing package and endpoints. Research scripts, private local paths and evaluation annotations are not required to run the application.
