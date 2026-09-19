# Service Desk Copilot — Ticket Processing Workflow V6

React + Vite + TypeScript + Tailwind CSS frontend for the Swiss {ai} Weeks / Swiss Life service-desk prototype.

## Current workflow

1. Upload a JSON file containing Jira-style tickets.
2. Search, filter, sort and paginate active tickets in **Ticket Queue**.
3. Browse **Ticket Categories** horizontally (Work type, Request type, Priority, Status, Service team, Business entity).
4. Click a ticket from either the queue or a category card.
5. Review ticket information and complete:
   - **Recommended Solutions** — select one of 3 recommendations, OR write the **Real solution**.
   - **Affected Business Aspect** — select one of 3 structured impact options.
6. **Send** is enabled only when the required information is complete.
7. The processed ticket is removed from the active Ticket Queue and category overview and added to **Processed Tickets**.
8. The processing payload is posted to `POST /tickets/process`. If the backend is unavailable, the payload is stored in browser `localStorage` for later synchronization.

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
npm install
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
