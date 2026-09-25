# Service Desk Copilot — Official Input + AI Triage V8

React + Vite + TypeScript + Tailwind CSS frontend for the Swiss {ai} Weeks / Swiss Life service-desk prototype.

## What changed in V8

This version is adapted to the official blind-evaluation JSON shape:

```json
{
  "fetchedAtUtc": "...",
  "runId": "...",
  "requestedColumns": [],
  "records": [
    { "Summary": "..." }
  ]
}
```

The importer reads only `records` as tickets while preserving every original ticket object unchanged in `ticket.raw`.

### Important UX rule

The **Incoming Tickets** panel does not show the source `Priority`, `Urgency` or `Impact` as the system answer. Those fields can exist in benchmark/reference data, but they are not used as the visual AI classification.

The left card shows only useful original context:

- Work type
- Request type
- Summary
- Reported service
- Business entity
- Status
- Created date
- AI processing state (`AI analyzing`, `AI ready`, `AI unavailable`)

The old orange `High` badge has been removed from incoming cards.

## End-to-end flow

```text
Official JSON
   ↓
records[]
   ↓
Incoming Tickets (original data only)
   ↓
POST /triage/batch
   ↓ fallback if needed
POST /triage per ticket
   ↓
AI analysis
   ↓
AI-Organized Tickets
   ↓
Priority / Work Type / Service / Team / Assignee
   ↓
Click ticket
   ↓
Original Ticket + AI Analysis
   ↓
Recommended Solutions + Affected Areas + RAG Evidence
   ↓
Human Review
   ↓
POST /feedback/rag
   ↓
Processed Tickets
```

## Backend endpoints

### `POST /triage/batch`

Preferred after loading a file.

```json
{
  "tickets": [
    {
      "ticket_id": "TICKET-1",
      "ticket": { "Summary": "..." }
    }
  ]
}
```

Expected response:

```json
{
  "results": [
    {
      "ticket_id": "TICKET-1",
      "status": "success",
      "analysis": {
        "work_type": { "value": "Service Request", "confidence": 0.97 },
        "affected_service": { "value": "Tax Reporting", "confidence": 0.95 },
        "service_team": { "value": "Tax & Reporting", "confidence": 0.91 },
        "assignee": { "value": "agent@example.com", "confidence": 0.82 },
        "urgency": { "value": "Lowest", "confidence": 0.90 },
        "impact": { "value": "No direct impact / Information", "confidence": 0.86 },
        "priority": { "value": "Lowest", "method": "urgency_impact_matrix" },
        "resolution_status": { "value": "done", "confidence": 0.70 }
      },
      "recommended_solutions": [],
      "affected_areas": [],
      "evidence": []
    }
  ]
}
```

If `/triage/batch` is unavailable, the frontend automatically falls back to `POST /triage` for each ticket.

### Flexible response adapter

The frontend also accepts the flatter L2 prompt response:

```json
{
  "work_type": "Incident",
  "affected_service": "Rimes Data Feed",
  "service_team": "Market Data",
  "assignee": "agent@example.com",
  "impact": "Significant / Large",
  "urgency": "High",
  "priority": "High",
  "resolution_status": "done",
  "resolution_text": "..."
}
```

`src/services/api.ts` normalizes both shapes into the same frontend model.

## Human review

For AI recommendations the analyst can rate:

- `highly_relevant`
- `medium_relevant`
- `poor_relevant`

The analyst can select an AI solution or enter the real solution. AI suggested affected areas can also be reviewed. Historical RAG evidence is displayed when returned by the backend.

Feedback is sent to:

```text
POST /feedback/rag
```

If the backend is unavailable during feedback submission, the payload is stored in browser `localStorage` under:

```text
service-desk-copilot-rag-feedback
```

## Layout

- 30% — Incoming Tickets
- 50% — AI-Organized Tickets / Ticket Processing
- 20% — Processed Tickets

Each panel scrolls independently.

## Project areas changed for V8

```text
src/
├── App.tsx                         # automatic triage after upload
├── services/api.ts                 # /triage, /triage/batch + response normalizer
├── types/triage.ts                 # AI analysis contracts
├── types/ticket.ts                 # original ticket model
├── lib/ticketJson.ts               # official records[] parser
├── features/upload/TicketUpload.tsx
└── features/tickets/
    ├── TicketQueue.tsx             # no benchmark priority UI
    ├── TicketListItem.tsx          # relevant original fields only
    └── TicketOverview.tsx          # AI categories + Original vs AI review
```

## Local environment

```text
VITE_API_URL=http://localhost:8000
```

Then:

```bash
npm install
npm run typecheck
npm run lint
npm run build
npm run dev
```

## Data preservation

The parser normalizes fields for display, but the original object is always kept under:

```ts
ticket.raw
```

The frontend never rewrites the official ticket source object.
