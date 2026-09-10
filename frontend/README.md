# Service Desk Copilot — Frontend F0-F2

Hackathon prototype frontend for the Swiss Life AI Support Agent challenge.

## Implemented scope

- F0: React/Vite/TypeScript/Tailwind project shell
- F1: mocked ticket queue and ticket selection
- F2: original ticket detail view and non-AI Analyze Ticket interaction

No AI panel, backend integration, RAG, authentication, routing, or priority logic is implemented yet.

## Local setup

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

## Structure

- `src/types/ticket.ts` — stable ticket contract
- `src/data/mockTickets.ts` — demo data
- `src/features/tickets/` — queue, list item, ticket detail
- `src/components/` — reusable UI primitives/status display
- `src/App.tsx` — layout and selected-ticket orchestration only
