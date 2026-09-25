# SwissLife Triage Workbench frontend

React + Vite + TypeScript frontend for the local SwissLife service-desk API.

## Workflow

1. The app loads the active challenge queue from `GET /tickets`.
2. Selecting a ticket shows its original Jira fields and comments.
3. The middle review workspace compares the original values with the AI suggestion and captures the analyst's final decision.
4. The middle workspace offers two resolution paths: an evidence-backed recommendation and a safe clarification/escalation alternative.
5. The right-hand panel calls `POST /tickets/:id/assist` and displays the case summary, routing snapshot, confidence, draft response, and historical evidence.
6. Approve, edit, or reject sends the decision to `POST /feedback`; processing outcomes are sent to `POST /tickets/process`.
7. The analyst can capture the real solution and affected business aspect. Processing feedback falls back to browser storage if the API is temporarily unavailable.

## Run

```powershell
npm install
npm run dev
```

The backend must be running from the parent directory with `python -m backend.server`. The API base defaults to `http://localhost:8000` and can be changed with `VITE_API_BASE_URL`.

The upload control accepts one ticket object, an array, or common wrappers such as `{ "tickets": [...] }`, `{ "issues": [...] }`, `{ "data": [...] }`, `{ "items": [...] }`, and `{ "results": [...] }`.
