> This branch includes FAISS + clean + filter + resolution proposals. Follow [backend/README.md](../backend/README.md) to build the index and start the API, then read [ANALYSIS_HANDOFF.md](../docs/ANALYSIS_HANDOFF.md) and [RESOLUTION_HANDOFF.md](../docs/RESOLUTION_HANDOFF.md) for the contracts. Set `VITE_API_BASE_URL` (not `VITE_API_URL`). General review templates are the manual fallback.

# Service Desk Copilot — Ticket Processing Workflow V6

React + Vite + TypeScript + Tailwind CSS frontend for the Swiss {ai} Weeks / Swiss Life service-desk prototype.

## Current workflow

1. Upload a JSON file containing Jira-style tickets.
2. Search, filter, sort and paginate active tickets in **Ticket Queue**.
3. Browse **Ticket Categories** horizontally (Work type, Request type, Priority, Status, Service team, Business entity).
4. Click a ticket from either the queue or a category card.
5. Review ticket information and complete:
   - **Clean & filter** — run ticket checks and evidence filtering in parallel, inspect the primary candidates or all original Top-50, and review selected historical comments and their conditions.
   - **Download correction preview** — export suggested changes to a separate copy; the imported ticket is not modified.
   - **Generate next steps** — prepare action cards from the filtered evidence, one critical question when needed, and an editable English reply draft.
   - Choose **Use / Edit / Not applicable** for each card. Inspect its **Check first**, **Expected outcome** and expandable **Source** references.
   - Enter **Actual action and outcome** yourself. A selected suggestion never fills this in or establishes success. Without a generated proposal, general review steps and the **Real solution** field remain available.
   - **Affected Business Aspect** — select one of 3 structured impact options.
6. **Send** is enabled only when the required information is complete.
7. The processed ticket is removed from the active Ticket Queue and category overview and added to **Processed Tickets**.
8. The processing payload is posted to `POST /tickets/process`. If the backend is unavailable, the payload is stored in browser `localStorage` for later synchronization.

**Send** saves the human review. It does not send the reply draft, perform an action,
or change the ticket in Jira. Resolution feedback preserves the original proposal,
the analyst's decisions/edits and the actual outcome as separate fields.

## Important AI-learning behavior

Human-entered real solutions and selected business-impact labels are captured as structured feedback for evaluation and future learning/fine-tuning. The browser does **not** instantly retrain the model.

## Layout

Desktop uses the fixed split:

- 30% — Ticket Queue
- 50% — Ticket Categories / Process Ticket
- 20% — Processed Tickets

Each panel has independent vertical scrolling. Category cards scroll horizontally in the middle panel.

## Run locally

```bash
npm ci
npm run typecheck
npm run lint
npm run build
npm run dev
```

## JSON support

The importer accepts:
- one ticket object,
- an array of ticket objects,
- wrapper objects such as `{ "tickets": [...] }`, `{ "issues": [...] }`, `{ "data": [...] }`, `{ "items": [...] }`, or `{ "results": [...] }`.

Missing values remain `Not recorded`; they are not silently inferred.
