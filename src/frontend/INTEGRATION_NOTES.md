# Integration Notes — Swiss AI official blind-eval format

## Incoming queue

Do not use these raw fields to visually pre-classify a ticket:

- `Priority`
- `Urgency`
- `Impact`
- `Severity`

They stay preserved in `ticket.raw`, but the visible priority in the AI-organized section must come from:

```text
analysis.priority.value
```

## Official wrapper

The importer explicitly supports:

```json
{
  "fetchedAtUtc": "...",
  "runId": "...",
  "records": [ ... ]
}
```

Non-ticket wrapper metadata is ignored by the ticket list.

## Minimum backend response for useful organization

The frontend can organize tickets once these fields are returned:

```json
{
  "ticket_id": "TICKET-1",
  "analysis": {
    "work_type": { "value": "..." },
    "affected_service": { "value": "..." },
    "service_team": { "value": "..." },
    "assignee": { "value": "..." },
    "urgency": { "value": "..." },
    "impact": { "value": "..." },
    "priority": { "value": "..." }
  },
  "recommended_solutions": [],
  "affected_areas": [],
  "evidence": []
}
```
