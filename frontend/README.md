# Service Desk Copilot — Jury Demo V4

Frontend for the Swiss {ai} Weeks / Swiss Life **AI Support Agent for Operational Service Desks** challenge.

## Core layout

The workspace is intentionally split into three visually distinct zones:

1. **Ticket Queue — 30%**: warm sand/orange family for incoming work and JSON import.
2. **Ticket Detail — 50%**: clean white/soft blue reading workspace for the original Jira data.
3. **AI Proposal — 20%**: soft mint/green family for AI recommendations, evidence and the human decision.

Desktop sizing uses `grid-template-columns: 3fr 5fr 2fr` so the proportions stay 30 / 50 / 20 across the usable workspace.

The centered header explains the product flow at a glance:

`Ticket queue → Original case → Evidence-backed AI → Human decision`

## What changed in V4

- stronger jury-first header and product story,
- clearer 30 / 50 / 20 visual hierarchy,
- large-queue controls designed around a ~20,000-ticket hackathon dataset,
- search across key / summary / team / business entity,
- priority + status filters,
- priority/newest/oldest sorting,
- queue counters for matching / critical / unassigned tickets,
- only 50 ticket cards rendered per page,
- confidence meter in the AI panel,
- explicit **Why this recommendation?** section,
- visible evidence / RAG sources,
- missing-information warning when confidence is insufficient,
- critical-case attention warning,
- copyable draft response,
- sticky Approve / Edit / Reject human decision bar,
- visible feedback-loop state after a human decision,
- original ticket, AI proposal and human review remain separate data layers.

## JSON import

Use **Upload ticket JSON** in the left panel. The parser accepts:

- one ticket object,
- an array of ticket objects,
- wrapper objects containing `tickets`, `issues`, `data`, `items` or `results`.

It supports the agreed Jira-style fields including Issue ID/Key, work/request type, summary, description, affected services, business context, teams, reporter/assignee, priority/urgency/impact/severity, dates, status, linked issues, resolution and all comments.

`null` means **Not recorded**. It is never silently interpreted as low/no/false.

A ready-to-use example is included at:

```text
public/demo-tickets.json
```

## AI behavior

The frontend does **not** fabricate AI output. Existing mock proposals are shown only for matching demo ticket IDs/keys. Other imported tickets show an honest “Ready for AI analysis” state until the backend `/assist` endpoint returns a proposal.

The intended production flow is:

`selected ticket → classification → knowledge retrieval → proposal → human review → feedback API`

## Large queue note

For the hackathon JSON demo, the browser can parse the complete dataset but only 50 matching tickets are rendered per page. Search uses `useDeferredValue` to keep typing responsive.

For production scale, search, filters, sorting and pagination should move server-side so the frontend does not download the full 20,000-ticket dataset on every load.

## Run locally

```bash
npm install
npm run dev
```

Validation:

```bash
npm run typecheck
npm run lint
npm run build
```
