# SwissLife Triage Workbench

An end-to-end service-desk triage workbench for the SwissLife challenge. The system keeps the original Jira ticket as the source of truth, retrieves historical evidence, proposes deterministic triage values, and requires a human decision before any recommendation is treated as accepted.

## What is included

- Ticket queue with search, filters, upload, raw Jira fields, comments and linked issues.
- Backend API and deterministic triage engine using the bundled historical dataset.
- Classify, prioritize and resolve proposal flow with supporting historical evidence.
- Human review workspace with approve, edit and reject actions.
- Two reviewable resolution paths with prerequisites and expected outcomes.
- Structured processing feedback saved locally for the demo.
- Python unit tests, backend contract tests and frontend CI checks.

The current demo uses the deterministic lexical retrieval engine as the production path. The FAISS/LLM branch was evaluated separately; it is not required to run this end-to-end demo.

## Requirements

- Python 3.10 or newer
- Node.js 20 LTS recommended, Node.js 18+ supported
- npm 9+

No OpenAI API key or Python package installation is required for the default demo backend. The backend uses Python's standard library and the included training data.

## First-time environment setup

The following steps assume Windows with Git Bash. They do not assume that Python, Conda, Node.js or frontend packages are already available.

### 1. Install Python

Install either [Miniconda](https://docs.conda.io/projects/miniconda/en/latest/) / Anaconda or Python 3.10+ from [python.org](https://www.python.org/downloads/). After installation, open a new Git Bash window and verify:

```bash
python --version
conda --version   # only needed if you use Conda
```

Recommended Conda setup:

```bash
conda create -n swisslife-e2e python=3.11 -y
conda activate swisslife-e2e
python --version
```

The default backend has no third-party Python dependencies, so there is no `pip install -r requirements.txt` step. Python's standard library is enough to run the API, triage engine and backend tests.

### 2. Install Node.js and npm

Install Node.js 20 LTS from [nodejs.org](https://nodejs.org/en/download). Open a new Git Bash window and verify:

```bash
node --version
npm --version
```

### 3. Install frontend dependencies

```bash
cd /e/ZurichHack_SwissLife/The-Asians-AI-Support-forOperational-Servide-Desk/frontend
npm ci --include=optional --no-audit --no-fund
```

This installs the exact versions recorded in `frontend/package-lock.json`. The `node_modules` directory is local-only and is ignored by Git.

If the system drive is short on space, move npm's cache to the E: drive:

```bash
npm ci --include=optional --cache E:/npm-cache --no-audit --no-fund
```

Do not commit `.env`, API keys, `node_modules`, `dist` or runtime output files.

## Project layout

```text
backend/                 HTTP API and proposal contract
data/challenge.json      20-ticket demo queue
data/training.json       historical training records
engine/scripts/          triage engine and Python tests
frontend/                React + Vite workbench
runtime/                 local feedback output; ignored by Git
.github/workflows/ci.yml GitHub Actions checks
```

## Run locally

Open two Git Bash terminals from the repository root.

Terminal 1 — backend:

```bash
cd /e/ZurichHack_SwissLife/The-Asians-AI-Support-forOperational-Servide-Desk
python -u -m backend.server
```

Terminal 2 — frontend:

```bash
cd /e/ZurichHack_SwissLife/The-Asians-AI-Support-forOperational-Servide-Desk/frontend
npm ci --include=optional --no-audit --no-fund
npm run dev
```

Open the Vite URL, normally `http://localhost:5173`.

To serve the production build from the Python API:

```bash
cd /e/ZurichHack_SwissLife/The-Asians-AI-Support-forOperational-Servide-Desk/frontend
npm run build
cd ..
python -u -m backend.server
```

Then open `http://localhost:8000`.

## Test locally

```bash
# Backend and engine
python -m py_compile backend/server.py engine/scripts/triage_pipeline.py
(cd engine && python -m unittest discover -s scripts -p "test_*.py" -v)
python -m unittest backend.test_server -v

# Frontend
cd frontend
npm ci --include=optional --no-audit --no-fund
npm run typecheck
npm run lint
npm run build
```

GitHub Actions runs the same checks on pushes and pull requests.

## API endpoints

- `GET /health` — service and dataset health
- `GET /stats` — queue, processing and review counts
- `GET /tickets` — current ticket queue
- `GET /tickets/:id` — one ticket
- `POST /tickets/:id/assist` — evidence-backed triage proposal
- `POST /tickets/import` — import a JSON ticket array
- `POST /feedback` — append a human review decision
- `POST /tickets/process` — append structured processing feedback

## Demo flow

1. Start the backend and frontend.
2. Select a ticket from the queue.
3. Review the original values, AI proposal and historical evidence.
4. Select one of the proposed resolution paths.
5. Approve, edit or reject the proposal in the middle review workspace.
6. Optionally record the actual solution and affected business aspect.

AI output is advisory. The source ticket is never overwritten automatically.

## Repository hygiene

Do not commit `frontend/node_modules`, `frontend/dist`, Python caches, `.env` files, or `runtime/*.json`. API keys should only be supplied through environment variables and must never be placed in tracked files.
