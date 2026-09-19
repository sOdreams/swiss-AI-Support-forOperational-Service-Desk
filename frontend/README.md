# Service Desk Copilot — Jira-aligned frontend

Frontend prototype for Swiss {ai} Weeks / Swiss Life.

## Core contract

The frontend now uses the shared **22-field Jira ticket model** agreed by the team. It deliberately keeps three layers separate:

1. **Original ticket** — values received from Jira/API. `null` means *not recorded*.
2. **AI proposal** — suggested classification, priority/team changes, reasons, sources and draft response.
3. **Human review** — approve, edit or reject. The review is captured separately so the API can persist it.

This separation prevents the UI from silently replacing recorded values with AI suggestions.

## Jira fields represented

Issue ID, Issue Key, Work type, Request type, Summary, Description, Affected Business or IT Services, Business Entity, Business Critical for Entity, Service Team(s), Reporter, Assignee, Priority, Urgency, Impact, Severity, Created date, Status, Linked issues, Resolution, Due date and All Comments.

## Important semantics

- `Urgency: null` is rendered as **Not recorded**, not Low.
- Status and Resolution are displayed independently.
- Actions in comments are not treated as proof of resolution; observed results remain separate entries.
- AI priority/team suggestions never overwrite the original Jira values until a human decision is saved.

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
